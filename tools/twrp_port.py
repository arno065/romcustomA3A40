#!/usr/bin/env python3
"""Stage and validate the Acer TWRP probe. Offline, no tablet commands."""
import argparse
import gzip
import hashlib
import json
import posixpath
import shutil
import stat
import struct
import zlib
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

from boot_image import BootImage, MTK_MAGIC, align

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / 'recovery/twrp'
DEVICE = 'device/acer/acer_jetfirefhd'
MAX_CPIO = 128 * 1024 * 1024


def settings():
    return json.loads((PORT / 'sources.json').read_text())


def stock_image(path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != settings()['stock_recovery_sha256']:
        raise ValueError('Expected the documented Acer 0.013.00 recovery; SHA-256 differs')
    image = BootImage(raw)
    if (image.kernel_addr, image.ramdisk_addr, image.tags_addr, image.page) != (
            0x40080000, 0x44000000, 0x4e000000, 2048):
        raise ValueError('Unexpected Acer recovery geometry')
    return image


def read_newc(compressed):
    """Read bounded newc CPIO in memory; never extract archive paths to disk."""
    dec = zlib.decompressobj(31)
    raw = dec.decompress(compressed, MAX_CPIO + 1)
    if len(raw) > MAX_CPIO or dec.unconsumed_tail:
        raise ValueError('Recovery CPIO exceeds 128 MiB')
    if not dec.eof or dec.unused_data:
        raise ValueError('Truncated gzip or unexpected trailing compressed data')
    entries = {}
    pos = 0
    while pos + 110 <= len(raw):
        if raw[pos:pos + 6] != b'070701':
            raise ValueError('Expected newc CPIO (070701)')
        try:
            fields = [int(raw[pos + 6 + i * 8:pos + 14 + i * 8], 16) for i in range(13)]
        except ValueError as exc:
            raise ValueError('Invalid CPIO header') from exc
        if any(value < 0 for value in fields):
            raise ValueError('Negative CPIO field')
        mode, size, namesize = fields[1], fields[6], fields[11]
        start = pos + 110
        end = start + namesize
        if namesize < 1 or end > len(raw) or raw[end - 1] != 0:
            raise ValueError('Truncated CPIO filename')
        name = raw[start:end - 1].decode('utf-8')
        if '\x00' in name or name.startswith('/') or '..' in PurePosixPath(name).parts:
            raise ValueError('Unsafe CPIO filename')
        name = str(PurePosixPath(name))
        data_start = (end + 3) & ~3
        next_pos = (data_start + size + 3) & ~3
        if next_pos > len(raw):
            raise ValueError('Truncated CPIO payload')
        if name == 'TRAILER!!!':
            if size or any(raw[next_pos:]):
                raise ValueError('Unexpected data after CPIO trailer')
            return entries
        if name in entries:
            raise ValueError('Duplicate CPIO filename: ' + name)
        entries[name] = (mode, raw[data_start:data_start + size])
        pos = next_pos
    raise ValueError('Missing CPIO trailer')


def resolve(entries, name):
    for _ in range(32):
        if name not in entries:
            raise ValueError('Missing ramdisk file: ' + name)
        mode, payload = entries[name]
        if not stat.S_ISLNK(mode):
            return mode, payload
        target = payload.decode('utf-8')
        name = posixpath.normpath(target if target.startswith('/') else
                                 posixpath.join(posixpath.dirname(name), target)).lstrip('/')
        if name == '..' or name.startswith('../'):
            raise ValueError('Ramdisk symlink escapes root')
    raise ValueError('Ramdisk symlink loop')


def check_ramdisk(compressed):
    entries = read_newc(compressed)
    for name in ('init', 'sbin/recovery', 'sbin/adbd'):
        mode, payload = resolve(entries, name)
        if (not stat.S_ISREG(mode) or not mode & 0o111 or len(payload) < 64 or
                payload[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', payload, 18)[0] != 183):
            raise ValueError('Expected executable AArch64 ELF: ' + name)
    for name in ('twres/ui.xml', 'twres/splash.xml'):
        mode, payload = resolve(entries, name)
        if not stat.S_ISREG(mode):
            raise ValueError('Expected regular XML file: ' + name)
        ET.fromstring(payload)
    _, fstab = resolve(entries, 'etc/recovery.fstab')
    expected = (PORT / DEVICE / 'recovery.fstab').read_bytes()
    if fstab != expected:
        raise ValueError('Ramdisk must use the reviewed probe fstab exactly')
    for name in ('init.recovery.mt8163.rc', 'ueventd.mt8163.rc'):
        _, payload = resolve(entries, name)
        if payload != (PORT / DEVICE / 'recovery/root' / name).read_bytes():
            raise ValueError('Unexpected Acer recovery init configuration: ' + name)
    _, initrc = resolve(entries, 'init.rc')
    if b'import /init.recovery.${ro.hardware}.rc' not in initrc:
        raise ValueError('Recovery init must import its hardware-specific rc')
    _, usb = resolve(entries, 'init.recovery.usb.rc')
    if b'/sys/class/android_usb/android0/functions' not in usb:
        raise ValueError('Missing legacy android_usb initialization')
    properties = {}
    for line in resolve(entries, 'default.prop')[1].decode().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.split('=', 1)
            properties[k.strip()] = v.strip()
    for key, value in {'ro.hardware': 'mt8163', 'ro.debuggable': '1', 'ro.adb.secure': '0'}.items():
        if properties.get(key) != value:
            raise ValueError('Unexpected recovery property: ' + key)
    return {'entries': len(entries), 'architecture': 'AArch64', 'profile': 'probe',
            'ramdisk_sha256': hashlib.sha256(compressed).hexdigest(),
            'checked': ['CPIO structure', 'main executable ELF headers', 'TWRP XML',
                        'probe fstab', 'hardware init', 'legacy USB', 'ADB properties'],
            'not_checked': ['ELF dependency closure', 'SELinux policy compatibility',
                            'touch coordinates', 'framebuffer rendering', 'hardware boot']}


def prepare(stock, destination):
    image = stock_image(stock)
    if destination.exists():
        raise ValueError('Destination must not exist; refusing to overwrite a device tree')
    shutil.copytree(PORT / DEVICE, destination)
    shutil.copy2(ROOT / DEVICE / 'BoardConfig.stock.mk', destination / 'BoardConfig.stock.mk')
    shutil.copy2(ROOT / 'tools/slim_twrp_resources.py', destination / 'slim_twrp_resources.py')
    prebuilt = destination / 'prebuilt'
    prebuilt.mkdir()
    (prebuilt / 'stock-kernel.gz-dtb').write_bytes(image.unwrap_mtk(image.sections[0], 'kernel'))
    (prebuilt / 'recovery-stock.img').write_bytes(image.data)
    report = {'status': 'staged, NOT compiled', 'source_stock': settings()['stock_build'],
              'stock_sha256': hashlib.sha256(image.data).hexdigest(),
              'stock_kernel_kept_unchanged': True, 'geometry': image.metadata()}
    (destination / 'PREPARATION.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def built_ramdisk(product_out):
    """Prefer recoveryimage's actual payload; accept raw/compressed CPIO fallbacks."""
    recovery = product_out / 'recovery.img'
    if recovery.is_file():
        raw = recovery.read_bytes()
        if len(raw) < 608 or raw[:8] != b'ANDROID!':
            raise ValueError('Invalid built recovery.img header')
        fields = struct.unpack_from('<10I', raw, 8)
        page, version = fields[7:9]
        if page not in (2048, 4096, 8192, 16384) or version != 0:
            raise ValueError('Expected a legacy Android v0 recovery.img')
        sections, pos = [], page
        for size in (fields[0], fields[2], fields[4]):
            end = pos + align(size, page)
            if end > len(raw):
                raise ValueError('Truncated built recovery.img section')
            sections.append(raw[pos:pos + size])
            pos = end
        # Omni's Android 9 mkbootimg hashes a fourth length for --dt even
        # when no DT image is supplied. Acer's historical tool hashes only
        # kernel/ramdisk/second. Header v0 above guarantees DT size is zero.
        # Accept these two defined formats, never a missing/mismatched hash.
        valid_ids = {BootImage.digest(sections), BootImage.digest(sections + [b''])}
        if raw[576:596] not in valid_ids:
            raise ValueError('Built recovery.img header SHA-1 mismatch')
        payload = sections[1]
        if payload[:4] == struct.pack('<I', MTK_MAGIC):
            payload = BootImage.unwrap_mtk(payload, 'ramdisk')
        name = 'recovery.img:ramdisk'
    else:
        candidate = next((product_out / name for name in
                          ('ramdisk-recovery.cpio', 'ramdisk-recovery.img')
                          if (product_out / name).is_file()), None)
        if candidate is None:
            raise ValueError('No built recovery.img or recovery ramdisk found')
        if candidate.stat().st_size > MAX_CPIO:
            raise ValueError('Built recovery ramdisk exceeds 128 MiB')
        payload, name = candidate.read_bytes(), candidate.name
    if payload.startswith(b'070701'):
        payload = gzip.compress(payload, mtime=0)
    # Also reject unknown compression, truncation and malformed CPIO before packing.
    read_newc(payload)
    return payload, name


def pack(stock, ramdisk, output):
    return pack_compressed(stock, ramdisk.read_bytes(), output)


def size_report(stock, product_out):
    image = stock_image(stock)
    compressed, source = built_ramdisk(product_out)
    entries = read_newc(compressed)
    fixed_bytes = image.page + align(len(image.sections[0]), image.page) + align(len(image.sections[2]), image.page)
    limit = 16777216
    final_bytes = fixed_bytes + align(512 + len(compressed), image.page)
    files = [{'path': name, 'bytes': len(data)} for name, (mode, data) in entries.items()
             if stat.S_ISREG(mode)]
    return {'ramdisk_source': source, 'compressed_ramdisk_bytes': len(compressed),
            'maximum_compressed_ramdisk_bytes': limit - fixed_bytes - 512,
            'expected_mtk_image_bytes': final_bytes, 'partition_bytes': limit,
            'fits_partition': final_bytes <= limit, 'remaining_partition_bytes': limit - final_bytes,
            'largest_uncompressed_files': sorted(files, key=lambda item: (-item['bytes'], item['path']))[:30],
            'note': 'Exact final geometry with original Acer kernel/wrappers; not a hardware boot test.'}


def pack_built(stock, product_out, output):
    compressed, source = built_ramdisk(product_out)
    return pack_compressed(stock, compressed, output, source)


def pack_compressed(stock, compressed, output, source=None):
    image = stock_image(stock)
    if output.exists():
        raise ValueError('Output exists; refusing to overwrite it')
    report = check_ramdisk(compressed)
    if source is not None:
        report['built_ramdisk_source'] = source
    built = image.development_recovery(compressed)
    parsed = BootImage(built)
    if parsed.sections[0] != image.sections[0]:
        raise ValueError('Stock kernel changed unexpectedly')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        stream.write(built)
    report.update({'image_sha256': hashlib.sha256(built).hexdigest(), 'image_bytes': len(built),
                   'stock_kernel_kept_unchanged': True, 'oem_signature': 'omitted',
                   'status': 'UNTESTED unsigned TWRP probe; not validated for flashing'})
    output.with_suffix(output.suffix + '.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def preflight(source, free_bytes=None):
    problems = []
    available = shutil.disk_usage(source).free if free_bytes is None else free_bytes
    if available < 20 * 1024**3:
        problems.append('At least 20 GiB free required after source sync before building')
    for name in ('build/envsetup.sh', 'bootable/recovery/Android.mk', 'vendor/omni/config/common.mk'):
        if not (source / name).is_file():
            problems.append('Missing source: ' + name)
    return {'free_bytes': available, 'minimum_free_bytes': 20 * 1024**3,
            'problems': problems, 'ready': not problems}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('stock', type=Path)
    p.add_argument('destination', type=Path)
    p = sub.add_parser('check-ramdisk')
    p.add_argument('ramdisk', type=Path)
    p = sub.add_parser('pack')
    p.add_argument('stock', type=Path)
    p.add_argument('ramdisk', type=Path)
    p.add_argument('output', type=Path)
    p = sub.add_parser('pack-built')
    p.add_argument('stock', type=Path)
    p.add_argument('product_out', type=Path)
    p.add_argument('output', type=Path)
    p = sub.add_parser('size-report')
    p.add_argument('stock', type=Path)
    p.add_argument('product_out', type=Path)
    p.add_argument('output', type=Path)
    p = sub.add_parser('preflight')
    p.add_argument('source', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            result = prepare(args.stock, args.destination)
        elif args.command == 'check-ramdisk':
            result = check_ramdisk(args.ramdisk.read_bytes())
        elif args.command == 'pack':
            result = pack(args.stock, args.ramdisk, args.output)
        elif args.command == 'pack-built':
            result = pack_built(args.stock, args.product_out, args.output)
        elif args.command == 'size-report':
            result = size_report(args.stock, args.product_out)
            args.output.write_text(json.dumps(result, indent=2) + '\n')
        else:
            result = preflight(args.source)
        print(json.dumps(result, indent=2))
        if result.get('ready') is False:
            raise SystemExit(2)
    except (ValueError, OSError, zlib.error, ET.ParseError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
