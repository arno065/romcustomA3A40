import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_hal_abi import check


@unittest.skipUnless(shutil.which('gcc') and shutil.which('readelf'), 'gcc and readelf are needed for real ELF fixtures')
class AbiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.good = self.root / 'good'
        self.bad = self.root / 'bad'
        self.good.mkdir()
        self.bad.mkdir()
        self.compile('int legacy_api(void) { return 7; }', self.good / 'libprovider.so')
        self.compile('int replacement_api(void) { return 8; }', self.bad / 'libprovider.so')
        self.hal = self.root / 'hal.so'
        self.compile('extern int legacy_api(void); int hal(void) { return legacy_api(); }',
                     self.hal, ['-L' + str(self.good), '-lprovider'])

    def tearDown(self):
        self.temp.cleanup()

    def compile(self, source, output, libraries=()):
        subprocess.run(['gcc', '-x', 'c', '-shared', '-nostdlib', '-fPIC',
                        '-Wl,-soname,' + output.name, '-o', str(output), '-', *libraries],
                       input=source, text=True, capture_output=True, check=True)

    def test_actual_provider_exports_resolve(self):
        self.assertTrue(check(self.hal, [self.good])['static_symbol_check_passed'])

    def test_same_library_name_with_changed_abi_fails(self):
        report = check(self.hal, [self.bad])
        self.assertFalse(report['static_symbol_check_passed'])
        self.assertIn('legacy_api', [entry['symbol'] for entry in report['unresolved_global_symbols']])

    def test_missing_library_is_reported(self):
        report = check(self.hal, [])
        self.assertEqual(report['missing_libraries'], ['libprovider.so'])

    def test_wrong_architecture_is_rejected(self):
        path = self.good / 'libprovider.so'
        data = bytearray(path.read_bytes())
        data[18:20] = (183).to_bytes(2, 'little')  # AArch64 provider for a host-x86 HAL.
        path.write_bytes(data)
        report = check(self.hal, [self.good])
        self.assertFalse(report['static_symbol_check_passed'])
        self.assertEqual(report['architecture_mismatches'], [str(path)])


if __name__ == '__main__':
    unittest.main()
