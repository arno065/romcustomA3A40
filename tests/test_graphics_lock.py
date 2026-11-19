import ctypes
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

LEGACY = '_ZN7android19GraphicBufferMapper4lockEPK13native_handlejRKNS_4RectEPPv'
TARGET = LEGACY + 'PiS9_'


@unittest.skipUnless(shutil.which('gcc'), 'gcc is needed for the native ABI forwarding fixture')
class GraphicsLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        stub = self.root / 'target.c'
        stub.write_text('''
unsigned long seen[7];
int result = -17;
int fake_target(void *self, const void *handle, unsigned int usage,
                const void *bounds, void **address, int *bpp, int *stride)
    __asm__("''' + TARGET + '''");
int fake_target(void *self, const void *handle, unsigned int usage,
                const void *bounds, void **address, int *bpp, int *stride) {
    seen[0] = (unsigned long)self; seen[1] = (unsigned long)handle;
    seen[2] = usage; seen[3] = (unsigned long)bounds;
    seen[4] = (unsigned long)address; seen[5] = (unsigned long)bpp;
    seen[6] = (unsigned long)stride;
    *address = (void *)0x1234;
    return result;
}
''')
        source = Path(__file__).resolve().parents[1] / 'hardware/acer/graphics-lock/mapper_lock.c'
        output = self.root / 'bridge.so'
        subprocess.run(['gcc', '-shared', '-fPIC', '-std=c11', '-Wall', '-Werror',
                        '-o', str(output), str(source), str(stub)], check=True, capture_output=True)
        self.library = ctypes.CDLL(str(output))
        self.lock = getattr(self.library, LEGACY)
        self.lock.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                              ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        self.lock.restype = ctypes.c_int

    def tearDown(self):
        self.temp.cleanup()

    def test_preserves_pointer_arguments_and_signed_status(self):
        address = ctypes.c_void_p()
        status = self.lock(0x10, 0x20, 0xF0000001, 0x30, ctypes.byref(address))
        seen = (ctypes.c_ulong * 7).in_dll(self.library, 'seen')
        self.assertEqual(status, -17)
        self.assertEqual(list(seen)[:4], [0x10, 0x20, 0xF0000001, 0x30])
        self.assertEqual(list(seen)[5:], [0, 0])
        self.assertEqual(address.value, 0x1234)

    def test_preserves_success_status(self):
        ctypes.c_int.in_dll(self.library, 'result').value = 0
        address = ctypes.c_void_p()
        self.assertEqual(self.lock(0x10, 0x20, 0, 0x30, ctypes.byref(address)), 0)

    def test_invalid_output_pointer_does_not_call_provider(self):
        self.assertEqual(self.lock(0x10, 0x20, 0, 0x30, None), -22)
        seen = (ctypes.c_ulong * 7).in_dll(self.library, 'seen')
        self.assertEqual(list(seen), [0] * 7)


if __name__ == '__main__':
    unittest.main()
