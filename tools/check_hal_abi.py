#!/usr/bin/env python3
"""Check an OEM ELF against candidate target libraries without executing ELF code.

Pass provider directories from an actual Android target build. A successful
static check is necessary but does not prove Android linker namespace, HAL
protocol, kernel ioctl or runtime compatibility.
"""
import argparse
import json
import re
import struct
import subprocess
from pathlib import Path


def symbol(value):
    name, separator, version = value.replace('@@', '@').partition('@')
    return name, version if separator else None


def inspect_elf(path):
    with path.open('rb') as stream:
        header = stream.read(64)
    if header[:4] != b'\x7fELF' or header[5] != 1:
        raise ValueError(f'Expected little-endian ELF: {path}')
    architecture = (header[4], struct.unpack_from('<H', header, 18)[0])
    dynamic = subprocess.run(['readelf', '-dW', str(path)], capture_output=True, text=True, check=True).stdout
    symbols = subprocess.run(['readelf', '--dyn-syms', '-W', str(path)], capture_output=True, text=True, check=True).stdout
    imports, exports = [], set()
    for line in symbols.splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[4] not in ('GLOBAL', 'WEAK', 'UNIQUE'):
            continue
        name = symbol(fields[7])
        if fields[6] == 'UND':
            if fields[4] != 'WEAK':
                imports.append(name)
        elif fields[5] in ('DEFAULT', 'PROTECTED'):
            exports.add(name)
            if '@@' in fields[7]:
                exports.add((name[0], None))
    return {
        'architecture': architecture,
        'needed': re.findall(r'\(NEEDED\).*\[([^\]]+)\]', dynamic),
        'imports': imports, 'exports': exports,
    }


def check(hal, provider_dirs):
    cache, objects, missing, mismatches = {}, {}, set(), []
    root = inspect_elf(hal)

    def load(path, data=None):
        path = path.resolve()
        if path in objects:
            return
        data = data or inspect_elf(path)
        if data['architecture'] != root['architecture']:
            mismatches.append(str(path))
            return
        objects[path] = data
        for needed in data['needed']:
            if needed not in cache:
                cache[needed] = next((folder / needed for folder in provider_dirs if (folder / needed).is_file()), None)
            dependency = cache[needed]
            if dependency is None:
                missing.add(needed)
            else:
                load(dependency)

    load(hal, root)
    available = set().union(*(data['exports'] for data in objects.values()))
    unresolved = []
    for path, data in objects.items():
        for name, version in data['imports']:
            # Unversioned imports may bind to a default/unversioned export only.
            if (name, version) not in available:
                unresolved.append({'object': str(path), 'symbol': name, 'version': version})
    return {
        'hal': str(hal), 'elf_class': root['architecture'][0],
        'elf_machine': root['architecture'][1],
        'providers': [str(path) for path in objects if path != hal.resolve()],
        'missing_libraries': sorted(missing), 'architecture_mismatches': sorted(set(mismatches)),
        'unresolved_global_symbols': unresolved,
        'static_symbol_check_passed': not (missing or mismatches or unresolved),
        'runtime_compatibility': 'NOT TESTED',
        'scope': 'Direct/transitive DT_NEEDED closure in supplied directories; Android namespace policy is not modeled.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hal', type=Path)
    parser.add_argument('--provider-dir', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = check(args.hal, args.provider_dir)
    output = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end='')
    raise SystemExit(0 if report['static_symbol_check_passed'] else 1)


if __name__ == '__main__':
    main()
