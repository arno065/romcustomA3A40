import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_stock_touch import branches


class Arm64BranchTests(unittest.TestCase):
    def test_forward_and_backward_direct_calls(self):
        direct, indirect = branches(struct.pack('<II', 0x94000002, 0x97ffffff), 0x1000)
        self.assertEqual(direct, [(0x1000, 0x1008, 'bl'), (0x1004, 0x1000, 'bl')])
        self.assertEqual(indirect, [])

    def test_local_branch_is_not_an_external_tail_call(self):
        direct, _ = branches(struct.pack('<II', 0x14000001, 0xd65f03c0), 0x1000)
        self.assertEqual(direct, [])

    def test_external_tail_call_is_retained(self):
        direct, _ = branches(struct.pack('<I', 0x14000008), 0x1000)
        self.assertEqual(direct, [(0x1000, 0x1020, 'b')])

    def test_indirect_call_and_jump_are_not_silently_ignored(self):
        direct, indirect = branches(struct.pack('<III', 0xd63f0020, 0xd61f0040, 0xd65f03c0), 0x1000)
        self.assertEqual(direct, [])
        self.assertEqual(indirect, ['0x1000', '0x1004'])

    def test_conditional_external_branches_are_retained(self):
        for word, op in [(0x54000100, 'b.cond'), (0x34000100, 'cbz'),
                         (0x35000100, 'cbnz'), (0x36000100, 'tbz'), (0x37000100, 'tbnz')]:
            with self.subTest(op=op):
                direct, _ = branches(struct.pack('<I', word), 0x1000)
                self.assertEqual(direct, [(0x1000, 0x1020, op)])
