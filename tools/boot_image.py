#!/usr/bin/env python3
"""Acer A3-A40 Android-v0/MTK image inspector and unsigned development packer.

Never communicates with a tablet. Never flashes. Stock signatures are retained
only for an exact stock round trip. Modified development images are unsigned.
"""
import argparse
import gzip
import hashlib
import json
import struct
from pathlib import Path

MTK_MAGIC = 0x58881688


def align(size, page):
    return (size + page - 1) // page * page


class BootImage:
    def __init__(self, data):
        if len(data) < 608 or data[:8] != b'ANDROID!':
            raise ValueError('Not an Android boot image')
        self.data = data
        v = struct.unpack_from('<10I', data, 8)
        self.kernel_size, self.kernel_addr, self.ramdisk_size, self.ramdisk_addr = v[:4]
        self.second_size, self.second_addr, self.tags_addr, self.page, version, reserved = v[4:]
        if version != 0 or self.page not in (2048, 4096, 8192, 16384):
            raise ValueError('Only legacy v0 images with a supported page size are accepted')
        self.header = data[:self.page]
        pos = self.page
        self.sections = []
        self.padded_sections = []
        for size in (self.kernel_size, self.ramdisk_size, self.second_size):
            end = pos + align(size, self.page)
            if end > len(data):
                raise ValueError('Truncated boot section')
            self.sections.append(data[pos:pos + size])
            self.padded_sections.append(data[pos:end])
            pos = end
        self.trailer = data[pos:]
        if self.digest(self.sections) != data[576:596]:
            raise ValueError('Boot header SHA-1 does not match image contents')
        for name, section in zip(('kernel', 'ramdisk'), self.sections[:2]):
            self.unwrap_mtk(section, name)

    @staticmethod
    def digest(sections):
        digest = hashlib.sha1()
        for section in sections:
            digest.update(section)
            digest.update(struct.pack('<I', len(section)))
        return digest.digest()

    @staticmethod
    def unwrap_mtk(section, name):
        if len(section) < 512:
            raise ValueError(f'Truncated MTK {name}')
        magic, size = struct.unpack_from('<II', section)
        if magic != MTK_MAGIC or size != len(section) - 512:
            raise ValueError(f'Invalid MTK {name} header or payload length')
        return section[512:]

    def metadata(self):
        return {
            'format': 'Android-v0 with MTK component wrappers',
            'page_size': self.page,
            'kernel_addr': hex(self.kernel_addr),
            'ramdisk_addr': hex(self.ramdisk_addr),
            'tags_addr': hex(self.tags_addr),
            'kernel_size': self.kernel_size,
            'ramdisk_size': self.ramdisk_size,
            'cmdline': self.header[64:576].split(b'\0')[0].decode(),
            'trailer_bytes': len(self.trailer),
            'sha256': hashlib.sha256(self.data).hexdigest(),
            'header_sha1_verified': True,
            'trailer_signature_cryptographically_verified': False,
        }

    def stock_roundtrip(self):
        return self.header + b''.join(self.padded_sections) + self.trailer

    def development_recovery(self, ramdisk_gzip):
        cpio = gzip.decompress(ramdisk_gzip)
        if not cpio.startswith((b'070701', b'070702')):
            raise ValueError('Recovery ramdisk must contain a newc CPIO archive')
        mtk_header = bytearray(self.sections[1][:512])
        struct.pack_into('<I', mtk_header, 4, len(ramdisk_gzip))
        mtk_header[8:40] = b'RECOVERY'.ljust(32, b'\0')
        sections = [self.sections[0], bytes(mtk_header) + ramdisk_gzip, self.sections[2]]
        header = bytearray(self.header)
        struct.pack_into('<I', header, 16, len(sections[1]))
        header[576:608] = self.digest(sections).ljust(32, b'\0')
        result = bytes(header) + b''.join(s.ljust(align(len(s), self.page), b'\0') for s in sections)
        if len(result) > 16 * 1024 * 1024:
            raise ValueError('Development image exceeds the Acer 16 MiB recovery partition')
        # An OEM signature for old contents is invalid for new contents.
        # No stock signature is appended to this development image.
        BootImage(result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect')
    inspect.add_argument('image', type=Path)
    inspect.add_argument('--extract', type=Path)
    check = sub.add_parser('roundtrip')
    check.add_argument('image', type=Path)
    pack = sub.add_parser('pack-recovery')
    pack.add_argument('image', type=Path, help='Original Acer recovery.img')
    pack.add_argument('ramdisk', type=Path, help='New recovery CPIO compressed with gzip')
    pack.add_argument('output', type=Path)
    pack.add_argument('--unsigned-development', action='store_true', required=True)
    args = parser.parse_args()
    image = BootImage(args.image.read_bytes())
    if args.command == 'inspect':
        print(json.dumps(image.metadata(), indent=2))
        if args.extract:
            args.extract.mkdir(parents=True, exist_ok=True)
            (args.extract / 'kernel.mtk').write_bytes(image.sections[0])
            (args.extract / 'ramdisk.cpio.gz').write_bytes(image.unwrap_mtk(image.sections[1], 'ramdisk'))
            (args.extract / 'metadata.json').write_text(json.dumps(image.metadata(), indent=2) + '\n')
    elif args.command == 'roundtrip':
        if image.stock_roundtrip() != image.data:
            raise ValueError('Stock image round trip differs')
        print('Exact stock round trip OK; header SHA-1 OK; OEM signature not verified.')
    else:
        if args.output.exists():
            raise FileExistsError('Refusing to overwrite an existing image')
        args.output.write_bytes(image.development_recovery(args.ramdisk.read_bytes()))
        print('Unsigned development image created. Not tested on hardware. No flashing performed.')


if __name__ == '__main__':
    main()
