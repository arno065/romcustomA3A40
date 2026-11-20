"""Execute the collector against a fake adb, never a tablet or an adb server."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

PWSH = os.environ.get('ACER_TEST_PWSH') or shutil.which('pwsh')
SCRIPT = Path(__file__).resolve().parents[1] / 'tools/Collect-AcerDiagnostics.ps1'
FAKE = '''#!/usr/bin/env python3
import json, os, sys, time
with open(os.environ['ACER_FAKE_CALLS'], 'a') as f:
    f.write(json.dumps(sys.argv[1:]) + '\\n')
args = sys.argv[1:]
mode = os.environ.get('ACER_FAKE_MODE', 'recovery')
if args == ['version']:
    print('Android Debug Bridge fake test fixture')
elif args == ['devices']:
    print('List of devices attached')
    print('ACER42\\t' + ('unauthorized' if mode == 'unauthorized' else 'device'))
    if mode == 'multiple': print('OTHER42\\tdevice')
elif len(args) == 4 and args[:3] == ['-s', 'ACER42', 'shell']:
    command = args[3]
    if command.startswith('for p in '):
        print('ro.product.model=A3-A40')
        print('ro.bootmode=' + ('normal' if mode == 'android' else 'recovery'))
        print('ro.twrp.version=' + ('' if mode == 'android' else 'fake-test-only'))
    elif '/tmp/recovery.log' in command:
        print('RECOVERY_LOG_NOT_PRESENT' if mode == 'android' else 'TWRP synthetic log')
    elif command == 'getevent -p':
        if mode == 'timeout': time.sleep(5)
        print('fake input capabilities')
    elif command == 'dmesg':
        print('dmesg: permission denied', file=sys.stderr)
        sys.exit(1)
    else: print('synthetic diagnostic result')
else:
    print('Unexpected invocation: ' + repr(args), file=sys.stderr)
    sys.exit(99)
'''


@unittest.skipUnless(PWSH and os.name == 'posix', 'PowerShell + POSIX fake executable needed')
class CollectorTests(unittest.TestCase):
    def run_collector(self, mode, extra=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        tools = root / 'native tools'
        tools.mkdir()
        fake = tools / 'fake-adb'
        fake.write_text(FAKE)
        fake.chmod(0o755)
        output = root / 'report [with spaces]'
        calls = root / 'calls.jsonl'
        env = dict(os.environ, ACER_FAKE_MODE=mode, ACER_FAKE_CALLS=str(calls),
                   XDG_CACHE_HOME=str(root / 'cache'), XDG_CONFIG_HOME=str(root / 'config'),
                   XDG_DATA_HOME=str(root / 'data'), POWERSHELL_TELEMETRY_OPTOUT='1')
        result = subprocess.run([PWSH, '-NoLogo', '-NoProfile', '-File', str(SCRIPT),
                                 '-AdbPath', str(fake), '-OutputDirectory', str(output)] + (extra or []),
                                env=env, text=True, capture_output=True, timeout=40)
        commands = [json.loads(line) for line in calls.read_text().splitlines()]
        return result, output, commands

    def test_collect_and_zip_without_mutating_adb_commands(self):
        result, output, calls = self.run_collector('recovery')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertTrue(manifest['Mode'].startswith('Recovery detected'))
        self.assertEqual(len(manifest['Results']), 12)
        self.assertTrue(any(r['File'] == 'dmesg.txt' and r['ExitCode'] == 1 for r in manifest['Results']))
        self.assertEqual(calls[:2], [['version'], ['devices']])
        for call in calls[2:]:
            self.assertEqual(call[:3], ['-s', 'ACER42', 'shell'])
            self.assertEqual(len(call), 4)  # Whole remote shell command survives native quoting.
            self.assertFalse(re.search(r'(^|[;\n])\s*(mount|umount|reboot|dd|su|setenforce|twrp)\b', call[3]))
            self.assertNotIn('/sys/bus/i2c', call[3])
        with zipfile.ZipFile(str(output) + '.zip') as archive:
            self.assertIn('manifest.json', archive.namelist())
        self.assertTrue(Path(str(output) + '.zip.sha256').is_file())

    def test_android_baseline_does_not_claim_recovery_validation(self):
        result, output, _ = self.run_collector('android')
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertTrue(manifest['Mode'].startswith('Android baseline'))

    def test_multiple_or_unauthorized_devices_stop_before_shell(self):
        for mode in ('multiple', 'unauthorized'):
            with self.subTest(mode=mode):
                result, output, calls = self.run_collector(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())
                self.assertEqual(calls, [['version'], ['devices']])

    def test_command_timeout_is_recorded_and_collection_continues(self):
        result, output, _ = self.run_collector('timeout', ['-TimeoutSeconds', '1'])
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((output / 'manifest.json').read_text())
        item = next(r for r in report['Results'] if r['File'] == 'input-capabilities.txt')
        self.assertTrue(item['TimedOut'])
        self.assertTrue(Path(str(output) + '.zip').is_file())
