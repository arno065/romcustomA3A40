import gzip
import io
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from boot_image import BootImage, MTK_MAGIC, align
from inspect_system import unsparse


def wrapped(payload, name):
    header = bytearray(b'\xff' * 512)
    struct.pack_into('<II', header, 0, MTK_MAGIC, len(payload))
    header[8:40] = name.ljust(32, b'\0')
    return bytes(header) + payload


def fixture():
    kernel = wrapped(b'kernel-fixture', b'KERNEL')
    ramdisk = wrapped(gzip.compress(b'070701' + b'cpio-fixture'), b'RECOVERY')
    sections = [kernel, ramdisk, b'']
    header = bytearray(2048)
    header[:8] = b'ANDROID!'
    struct.pack_into('<10I', header, 8, len(kernel), 0x40080000,
                     len(ramdisk), 0x44000000, 0, 0, 0x4e000000, 2048, 0, 0)
    header[576:596] = BootImage.digest(sections)
    return bytes(header) + b''.join(s.ljust(align(len(s), 2048), b'\0') for s in sections) + b'example-signature'


class BootTests(unittest.TestCase):
    def test_exact_roundtrip_retains_signature(self):
        original = fixture()
        self.assertEqual(BootImage(original).stock_roundtrip(), original)

    def test_modified_recovery_updates_headers_and_drops_old_signature(self):
        original = BootImage(fixture())
        payload = gzip.compress(b'070701' + b'new-development-cpio')
        rebuilt = BootImage(original.development_recovery(payload))
        self.assertEqual(rebuilt.unwrap_mtk(rebuilt.sections[1], 'ramdisk'), payload)
        self.assertEqual(rebuilt.sections[0], original.sections[0])
        self.assertEqual(rebuilt.ramdisk_addr, 0x44000000)
        self.assertEqual(rebuilt.trailer, b'')

    def test_reject_corrupt_hash(self):
        data = bytearray(fixture())
        data[2561] ^= 1
        with self.assertRaises(ValueError):
            BootImage(data)

    def test_reject_truncated_section(self):
        with self.assertRaises(ValueError):
            BootImage(fixture()[:3000])

    def test_reject_non_cpio_ramdisk(self):
        with self.assertRaises(ValueError):
            BootImage(fixture()).development_recovery(gzip.compress(b'not a recovery'))

    def test_reject_mtk_length_mismatch_even_with_valid_android_hash(self):
        image = BootImage(fixture())
        sections = image.sections.copy()
        kernel = bytearray(sections[0])
        struct.pack_into('<I', kernel, 4, 1)
        sections[0] = bytes(kernel)
        header = bytearray(image.header)
        header[576:596] = BootImage.digest(sections)
        data = bytes(header) + b''.join(s.ljust(align(len(s), 2048), b'\0') for s in sections)
        with self.assertRaises(ValueError):
            BootImage(data)

    def test_new_arm64_kernel_updates_mtk_and_android_lengths(self):
        raw = bytearray(64)
        raw[56:60] = b'ARM\x64'
        dtb = struct.pack('>10I', 0xd00dfeed, 40, 0, 0, 0, 17, 16, 0, 0, 0)
        kernel = gzip.compress(bytes(raw)) + dtb
        ramdisk = gzip.compress(b'070701new-cpio')
        rebuilt = BootImage(BootImage(fixture()).development_recovery(ramdisk, kernel))
        self.assertEqual(rebuilt.unwrap_mtk(rebuilt.sections[0], 'kernel'), kernel)
        self.assertEqual(rebuilt.kernel_size, len(kernel) + 512)
        self.assertEqual(rebuilt.trailer, b'')

    def test_new_kernel_requires_appended_dtb(self):
        raw = bytearray(64)
        raw[56:60] = b'ARM\x64'
        with self.assertRaises(ValueError):
            BootImage(fixture()).development_recovery(gzip.compress(b'070701cpio'), gzip.compress(bytes(raw)))


class SparseTests(unittest.TestCase):
    def sparse(self):
        block = 4096
        header = struct.pack('<I4H4I', 0xed26ff3a, 1, 0, 28, 12, block, 3, 4, 0)
        raw = struct.pack('<2H2I', 0xcac1, 0, 1, 12 + block) + b'A' * block
        fill = struct.pack('<2H2I', 0xcac2, 0, 1, 16) + b'B' * 4
        skip = struct.pack('<2H2I', 0xcac3, 0, 1, 12)
        crc = struct.pack('<2H2I', 0xcac4, 0, 0, 16) + bytes(4)
        return header + raw + fill + skip + crc

    def test_raw_fill_hole_crc_chunks(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'system.raw'
            unsparse(io.BytesIO(self.sparse()), output)
            self.assertEqual(output.read_bytes(), b'A' * 4096 + b'B' * 4096 + bytes(4096))

    def test_reject_truncated_sparse(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                unsparse(io.BytesIO(self.sparse()[:-1]), Path(folder) / 'system.raw')


if __name__ == '__main__':
    unittest.main()
