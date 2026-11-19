#!/usr/bin/env python3
"""Inventory old HAL imports with readelf; do not load/execute OEM libraries."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

CRITICAL = ('egl/libGLES_mali.so', 'hw/gralloc.mt8163.so',
            'hw/hwcomposer.mt8163.so', 'hw/audio.primary.mt8163.so',
            'hw/sensors.mt8163.so', 'hw/camera.mt8163.so')


def audit(root):
    entries = []
    for libdir in ('lib', 'lib64'):
        for relative in CRITICAL:
            path = root / 'system' / libdir / relative
            if not path.exists():
                entries.append({'path': f'/system/{libdir}/{relative}', 'present': False})
                continue
            binary = path.read_bytes()
            dynamic = subprocess.run(['readelf', '-dW', str(path)], capture_output=True, text=True, check=True).stdout
            symbols = subprocess.run(['readelf', '--dyn-syms', '-W', str(path)], capture_output=True, text=True, check=True).stdout
            imports = []
            for line in symbols.splitlines():
                fields = line.split()
                if len(fields) >= 8 and fields[6] == 'UND' and fields[4] != 'WEAK':
                    imports.append(fields[7])
            needed = re.findall(r'\(NEEDED\).*\[([^\]]+)\]', dynamic)
            entries.append({
                'path': f'/system/{libdir}/{relative}', 'present': True,
                'elf_bits': {1: 32, 2: 64}[binary[4]],
                'sha256': hashlib.sha256(binary).hexdigest(),
                'needed': needed, 'undefined_global_symbols': sorted(set(imports)),
                'stock_dependencies_not_in_lib_root': [n for n in needed if not (root / 'system' / libdir / n).exists()],
                'android_13_abi_compatibility': 'UNVERIFIED',
            })
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extracted', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    entries = audit(args.extracted)
    args.output.write_text(json.dumps(entries, indent=2) + '\n')
    for entry in entries:
        print(entry['path'], entry.get('elf_bits'), 'NEEDED:', len(entry.get('needed', [])))


if __name__ == '__main__':
    main()
