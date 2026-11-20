import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from slim_twrp_resources import slim
import twrp_port
from test_binary_formats import fixture
from test_twrp_port import cpio, probe_items, standard_recovery
import hashlib


class ResourceTests(unittest.TestCase):
    def resources(self, root):
        languages, fonts = root / 'twres/languages', root / 'twres/fonts'
        languages.mkdir(parents=True)
        fonts.mkdir()
        for lang in ('en', 'fr', 'ja', 'de'):
            (languages / (lang + '.xml')).write_text('<language><resource type="fontoverride" filename="RobotoCondensed-Regular.ttf"/></language>')
        for name in ('RobotoCondensed-Regular.ttf', 'DroidSansMono.ttf', 'DroidSansFallback.ttf', 'NotoSansCJKjp-Regular.ttf', 'OFL.txt'):
            (fonts / name).write_bytes(b'font or license fixture')
        (root / 'sbin').mkdir()
        (root / 'sbin/recovery').write_bytes(b'critical binary must be unchanged')
        return languages, fonts

    def test_retains_french_english_fonts_license_and_binaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            languages, fonts = self.resources(root)
            report = slim(root)
            self.assertEqual(sorted(p.name for p in languages.iterdir()), ['en.xml', 'fr.xml'])
            self.assertEqual(sorted(p.name for p in fonts.iterdir()), ['DroidSansMono.ttf', 'OFL.txt', 'RobotoCondensed-Regular.ttf'])
            self.assertEqual((root / 'sbin/recovery').read_bytes(), b'critical binary must be unchanged')
            self.assertEqual(len(report['removed']), 4)
            self.assertEqual(slim(root)['removed'], [])

    def test_missing_french_aborts_before_deleting_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            languages, fonts = self.resources(root)
            (languages / 'fr.xml').unlink()
            with self.assertRaisesRegex(ValueError, 'Required TWRP language'):
                slim(root)
            self.assertTrue((languages / 'ja.xml').exists())
            self.assertTrue((fonts / 'DroidSansFallback.ttf').exists())

    def test_missing_required_font_aborts_before_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            languages, fonts = self.resources(root)
            (fonts / 'RobotoCondensed-Regular.ttf').unlink()
            with self.assertRaisesRegex(ValueError, 'Required font'):
                slim(root)
            self.assertTrue((languages / 'ja.xml').exists())

    def test_rejects_symlinked_resource_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            languages, _ = self.resources(root)
            languages.rename(root / 'other-languages')
            languages.symlink_to(root / 'other-languages', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'real TWRP resource'):
                slim(root)
            self.assertTrue((root / 'other-languages/ja.xml').exists())

    def test_updates_existing_ramdisk_file_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.resources(root)
            listing, sums = root / 'ramdisk-files.txt', root / 'ramdisk-files.sha256sum'
            listing.write_text('twres/languages/ja.xml\ntwres/languages/fr.xml\nramdisk-files.txt\n')
            sums.write_text('0' * 64 + '  ./twres/languages/ja.xml\n' + '1' * 64 + '  ./ramdisk-files.txt\n')
            slim(root)
            self.assertNotIn('ja.xml', listing.read_text())
            self.assertNotIn('ja.xml', sums.read_text())
            self.assertIn(hashlib.sha256(listing.read_bytes()).hexdigest(), sums.read_text())


class SizeReportTests(unittest.TestCase):
    def test_report_matches_final_packed_size_with_mtk_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stock = root / 'stock.img'
            stock.write_bytes(fixture())
            (root / 'recovery.img').write_bytes(standard_recovery(cpio(probe_items())))
            pin = {'stock_recovery_sha256': hashlib.sha256(stock.read_bytes()).hexdigest()}
            with patch.object(twrp_port, 'settings', return_value=pin):
                report = twrp_port.size_report(stock, root)
                twrp_port.pack_built(stock, root, root / 'final.img')
            self.assertEqual(report['expected_mtk_image_bytes'], (root / 'final.img').stat().st_size)
            self.assertEqual(report['partition_bytes'], 16777216)
            self.assertTrue(report['fits_partition'])
            self.assertTrue(any(item['path'] == 'sbin/recovery' for item in report['largest_uncompressed_files']))
