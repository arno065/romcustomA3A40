#!/usr/bin/env python3
"""Read-only, bounded call-graph audit of the identified Acer stock kernel.

Use vmlinux-to-elf to recover symbols first. This tool checks that the ELF
.kernel section exactly matches the original raw Image, then decodes direct
AArch64 branches. It does not modify a kernel or execute tablet code.
"""
import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path

ROOTS = ('elan_ktf_ts_probe', 'elan_ic_init_work')
START, STOP = 0xffffffc00066b000, 0xffffffc000671000


def kernel_section(elf):
    data = elf.read_bytes()
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError('Expected little-endian AArch64 ELF64')
    shoff = struct.unpack_from('<Q', data, 40)[0]
    entsize, count, names_index = struct.unpack_from('<HHH', data, 58)
    if entsize != 64 or names_index >= count or shoff + count * entsize > len(data):
        raise ValueError('Invalid ELF section table')
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, shoff + i * entsize) for i in range(count)]
    names_section = sections[names_index]
    names = data[names_section[4]:names_section[4] + names_section[5]]
    for section in sections:
        name = names[section[0]:].split(b'\0', 1)[0]
        if name == b'.kernel':
            if section[4] + section[5] > len(data):
                raise ValueError('Truncated ELF kernel section')
            return section[3], data[section[4]:section[4] + section[5]]
    raise ValueError('Reconstructed ELF needs a .kernel section')


def branches(code, start):
    direct, indirect = [], []
    for offset in range(0, len(code) - 3, 4):
        word = struct.unpack_from('<I', code, offset)[0]
        pc = start + offset
        if word & 0xfc000000 in (0x94000000, 0x14000000):
            relative = word & 0x3ffffff
            if relative & 0x2000000:
                relative -= 0x4000000
            target = pc + 4 * relative
            if word & 0xfc000000 == 0x94000000 or not start <= target < start + len(code):
                direct.append((pc, target, 'bl' if word & 0xfc000000 == 0x94000000 else 'b'))
        conditional = None
        if word & 0xff000010 == 0x54000000:
            conditional = (19, 'b.cond')
        elif word & 0x7e000000 == 0x34000000:
            conditional = (19, 'cbnz' if word & 0x01000000 else 'cbz')
        elif word & 0x7e000000 == 0x36000000:
            conditional = (14, 'tbnz' if word & 0x01000000 else 'tbz')
        if conditional:
            bits, op = conditional
            relative = (word >> 5) & ((1 << bits) - 1)
            if relative & (1 << (bits - 1)):
                relative -= 1 << bits
            target = pc + 4 * relative
            if not start <= target < start + len(code):
                direct.append((pc, target, op))
        if word & 0xfffffc1f in (0xd63f0000, 0xd61f0000):
            indirect.append(hex(pc))
    return direct, indirect


def audit(image, elf, nm):
    base, data = kernel_section(elf)
    original = image.read_bytes()
    if original != data:
        raise ValueError('Reconstructed .kernel differs from original raw Image')
    if base != 0xffffffc000080000:
        raise ValueError('Unexpected reconstructed virtual base for this firmware')
    # These bounds are intentionally specific to the inspected 0.013.00 image.
    digest = hashlib.sha256(data).hexdigest()
    expected = json.loads((Path(__file__).resolve().parents[1] / 'evidence/stock-touch-audit.json').read_text())['raw_image_sha256']
    if digest != expected:
        raise ValueError('This audit applies only to the documented stock kernel hash')
    listing = subprocess.check_output([nm, '-n', str(elf)], text=True)
    all_symbols = []
    for line in listing.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[1].lower() == 't':
            all_symbols.append((int(fields[0], 16), fields[2]))
    all_symbols.sort()
    at = {addr: name for addr, name in all_symbols}
    functions = {}
    for i, (addr, name) in enumerate(all_symbols[:-1]):
        if not START <= addr < STOP:
            continue
        end = next((a for a, _ in all_symbols[i + 1:] if a > addr), None)
        if end is None or not base <= addr < end <= base + len(data):
            raise ValueError('Invalid symbol bounds')
        calls, indirect = branches(data[addr - base:end - base], addr)
        functions[name] = {'address': hex(addr), 'bytes': end - addr,
                           'calls': [{'pc': hex(pc), 'target': at.get(target, hex(target)), 'instruction': op}
                                     for pc, target, op in calls], 'indirect_branch_pcs': indirect}
    visited, pending = set(), list(ROOTS)
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        if name not in functions:
            raise ValueError('Expected stock touch symbol missing: ' + name)
        visited.add(name)
        pending += [call['target'] for call in functions[name]['calls']
                    if call['target'] in functions and call['target'] not in visited]
    return {'raw_image_sha256': digest, 'reconstructed_kernel_bytes_match': True,
            'virtual_base': hex(base), 'roots': list(ROOTS),
            'driver_scan_address_range': [hex(START), hex(STOP)],
            'reachable_driver_functions': sorted(visited),
            'firmware_updater_reachable_via_decoded_direct_branches': any('Update_FW' in n for n in visited),
            'reachable_driver_indirect_branches': {n: functions[n]['indirect_branch_pcs']
                                                    for n in sorted(visited) if functions[n]['indirect_branch_pcs']},
            'functions': {n: functions[n] for n in sorted(set(visited) | {'Update_FW_in_Driver.isra.17', 'show_reset'})},
            'limits': ['Symbol bounds inferred from recovered kallsyms; ELF base is reconstructed.',
                       'Only direct branches inside the stated driver address range are traversed.',
                       'Framework callbacks, other threads, external helpers and all indirect targets are not proven.',
                       'No tablet test; no claim that every firmware programming path is disabled.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('image', type=Path)
    p.add_argument('elf', type=Path)
    p.add_argument('--nm', default='aarch64-linux-android-nm')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    report = audit(args.image, args.elf, args.nm)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('Direct-branch updater reachability:', report['firmware_updater_reachable_via_decoded_direct_branches'])


if __name__ == '__main__':
    main()
