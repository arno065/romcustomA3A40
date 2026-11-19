import gzip
import hashlib
import stat
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import twrp_port
from boot_image import BootImage
from test_binary_formats import fixture


def cpio(items):
    """Synthetic archives only: these ELF headers are not built executables."""
    raw = bytearray()
    for name, mode, data in items + [('TRAILER!!!', 0, b'')]:
        encoded = name.encode() + b'\0'
        values = [1, mode, 0, 0, 1, 0, len(data), 0, 0, 0, 0, len(encoded), 0]
        raw += b'070701' + ''.join(f'{v:08x}' for v in values).encode() + encoded
        raw += b'\0' * (-len(raw) % 4)
        raw += data
        raw += b'\0' * (-len(raw) % 4)
    return gzip.compress(bytes(raw), mtime=0)


def probe_items():
    elf = bytearray(64)
    elf[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<H', elf, 18, 183)
    items = [(name, stat.S_IFREG | 0o755, bytes(elf))
             for name in ['init', 'sbin/recovery', 'sbin/adbd']]
    files = {
        'twres/ui.xml': b'<recovery/>', 'twres/splash.xml': b'<recovery/>',
        'init.rc': b'import /init.recovery.${ro.hardware}.rc\n',
        'init.recovery.usb.rc': b'write /sys/class/android_usb/android0/functions adb\n',
        'default.prop': b'ro.hardware=mt8163\nro.debuggable=1\nro.adb.secure=0\n',
        'etc/recovery.fstab': (twrp_port.PORT / twrp_port.DEVICE / 'recovery.fstab').read_bytes(),
    }
    for name in ('init.recovery.mt8163.rc', 'ueventd.mt8163.rc'):
        files[name] = (twrp_port.PORT / twrp_port.DEVICE / 'recovery/root' / name).read_bytes()
    return items + [(name, stat.S_IFREG | 0o644, data) for name, data in files.items()]


class CpioTests(unittest.TestCase):
    def test_probe_structure_and_explicit_validation_limits(self):
        report = twrp_port.check_ramdisk(cpio(probe_items()))
        self.assertEqual(report['architecture'], 'AArch64')
        self.assertIn('hardware boot', report['not_checked'])

    def test_reject_path_traversal_and_absolute_names(self):
        for name in ['../init', '/init', 'x/../../init']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                twrp_port.read_newc(cpio([(name, stat.S_IFREG, b'x')]))

    def test_reject_duplicate_names(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            twrp_port.read_newc(cpio([('init', stat.S_IFREG, b'x')] * 2))

    def test_reject_truncated_gzip(self):
        with self.assertRaises(ValueError):
            twrp_port.read_newc(cpio(probe_items())[:-3])

    def test_reject_concatenated_gzip(self):
        with self.assertRaises(ValueError):
            twrp_port.read_newc(cpio([]) + gzip.compress(b'extra'))

    def test_reject_missing_cpio_trailer(self):
        with self.assertRaises(ValueError):
            twrp_port.read_newc(gzip.compress(gzip.decompress(cpio([]))[:110]))

    def test_bound_decompression(self):
        with patch.object(twrp_port, 'MAX_CPIO', 100), self.assertRaisesRegex(ValueError, 'exceeds'):
            twrp_port.read_newc(cpio(probe_items()))

    def test_reject_32_bit_recovery(self):
        items = probe_items()
        name, mode, data = items[1]
        items[1] = (name, mode, data[:4] + b'\x01' + data[5:])
        with self.assertRaisesRegex(ValueError, 'AArch64'):
            twrp_port.check_ramdisk(cpio(items))

    def test_reject_fstab_with_data_partition(self):
        items = [(n, m, d + b'/data ext4 /dev/block/mmcblk0p22\n' if n == 'etc/recovery.fstab' else d)
                 for n, m, d in probe_items()]
        with self.assertRaisesRegex(ValueError, 'fstab'):
            twrp_port.check_ramdisk(cpio(items))

    def test_reject_non_twrp_ramdisk(self):
        with self.assertRaisesRegex(ValueError, 'Missing'):
            twrp_port.check_ramdisk(cpio([probe_items()[0]]))

    def test_rooted_symlink_and_cycle(self):
        entries = {'link': (stat.S_IFLNK, b'/real'), 'real': (stat.S_IFREG, b'ok')}
        self.assertEqual(twrp_port.resolve(entries, 'link')[1], b'ok')
        entries['real'] = (stat.S_IFLNK, b'link')
        with self.assertRaisesRegex(ValueError, 'loop'):
            twrp_port.resolve(entries, 'link')


class PackagingTests(unittest.TestCase):
    def test_stage_and_pack_keep_kernel_but_remove_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stock = root / 'stock.img'
            stock.write_bytes(fixture())
            pinned = {'stock_recovery_sha256': hashlib.sha256(stock.read_bytes()).hexdigest(),
                      'stock_build': 'synthetic unit-test fixture'}
            with patch.object(twrp_port, 'settings', return_value=pinned):
                staged = root / 'device'
                twrp_port.prepare(stock, staged)
                ramdisk = root / 'ramdisk.gz'
                ramdisk.write_bytes(cpio(probe_items()))
                output = root / 'probe.img'
                twrp_port.pack(stock, ramdisk, output)
                built = BootImage(output.read_bytes())
                self.assertEqual(built.sections[0], BootImage(stock.read_bytes()).sections[0])
                self.assertEqual(built.trailer, b'')
                self.assertLess(len(output.read_bytes()), 16777216)
                with self.assertRaisesRegex(ValueError, 'overwrite'):
                    twrp_port.pack(stock, ramdisk, output)
                with self.assertRaisesRegex(ValueError, 'overwrite'):
                    twrp_port.prepare(stock, staged)

    def test_reject_unidentified_stock_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            stock = Path(tmp) / 'stock.img'
            stock.write_bytes(fixture())
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                twrp_port.stock_image(stock)

    def test_preflight_rejects_small_disk_before_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = twrp_port.preflight(Path(tmp), free_bytes=2 * 1024**3)
            self.assertFalse(report['ready'])
            self.assertTrue(any('20 GiB' in error for error in report['problems']))


if __name__ == '__main__':
    unittest.main()
