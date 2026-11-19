#!/usr/bin/env python3
"""Inspect an Acer stock system image without mounting or executing its files.

Requires dissect.extfs==3.15. Inputs remain unchanged; APKs are inventoried,
not extracted. A sparse raw image is created directly from the ZIP stream.
"""
import argparse
import hashlib
import json
import shutil
import stat
import struct
import zipfile
from pathlib import Path


def exact(stream, size):
    data = stream.read(size)
    if len(data) != size:
        raise ValueError('Truncated sparse image')
    return data


def unsparse(stream, output):
    header = exact(stream, 28)
    magic, major, minor, hsize, csize, block, blocks, chunks, checksum = struct.unpack('<I4H4I', header)
    if magic != 0xED26FF3A or major != 1 or hsize < 28 or csize < 12 or not block:
        raise ValueError('Unsupported sparse header')
    exact(stream, hsize - 28)
    produced = 0
    with output.open('wb') as target:
        for _ in range(chunks):
            ch = exact(stream, csize)
            kind, reserved, count, total = struct.unpack_from('<2H2I', ch)
            size = count * block
            payload = total - csize
            if kind == 0xCAC1 and payload == size:
                remaining = size
                while remaining:
                    data = exact(stream, min(remaining, 4 * 1024 * 1024))
                    target.write(data)
                    remaining -= len(data)
            elif kind == 0xCAC2 and payload == 4:
                fill = exact(stream, 4)
                if fill == b'\0' * 4:
                    target.seek(size, 1)
                else:
                    pattern = fill * (1024 * 1024 // 4)
                    remaining = size
                    while remaining:
                        n = min(remaining, len(pattern))
                        target.write(pattern[:n])
                        remaining -= n
            elif kind == 0xCAC3 and payload == 0:
                target.seek(size, 1)
            elif kind == 0xCAC4 and payload == 4 and count == 0:
                exact(stream, 4)  # ZIP CRC verifies input; sparse CRC not verified here.
            else:
                raise ValueError(f'Invalid sparse chunk: {kind:x}')
            produced += size
        if produced != blocks * block or stream.read(1):
            raise ValueError('Sparse length mismatch')
        target.truncate(produced)


def inspect(raw, output):
    from dissect.extfs import ExtFS
    inventory = []
    with raw.open('rb') as stream:
        fs = ExtFS(stream)

        def walk(node, relative=Path('.')):
            if node.filetype == stat.S_IFDIR:
                for child in sorted(node.iterdir(), key=lambda c: c.filename):
                    if child.filename in ('.', '..'):
                        continue
                    if '/' in child.filename or '\0' in child.filename:
                        raise ValueError('Unsafe filesystem name')
                    walk(child, relative / child.filename)
                return
            entry = {'path': '/system/' + relative.as_posix(), 'bytes': node.size}
            if node.filetype == stat.S_IFLNK:
                entry['link'] = node.link
            elif node.filetype == stat.S_IFREG:
                with node.open() as source:
                    prefix = source.read(64)
                if prefix[:4] == b'\x7fELF':
                    entry['elf_bits'] = {1: 32, 2: 64}.get(prefix[4])
                    entry['elf_machine'] = struct.unpack_from('<H', prefix, 18)[0]
                parts = relative.parts
                selected = parts[0] in ('lib', 'lib64', 'vendor', 'etc', 'bin', 'xbin', 'usr') or relative.name == 'build.prop'
                if selected:
                    destination = output / 'system' / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with node.open() as source, destination.open('wb') as target:
                        shutil.copyfileobj(source, target)
                    entry['sha256'] = hashlib.sha256(destination.read_bytes()).hexdigest()
            inventory.append(entry)

        walk(fs.get('/'))
    (output / 'inventory-system.json').write_text(json.dumps(inventory, indent=2) + '\n')
    print(f'Inventoried {len(inventory)} files; selected vendor/config/ELF files extracted.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('raw', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.raw.exists():
        temporary = args.raw.with_suffix('.partial')
        with zipfile.ZipFile(args.archive) as archive:
            candidates = [n for n in archive.namelist() if n.endswith('/Firmware/system.img')]
            if len(candidates) != 1:
                raise ValueError('Expected one Firmware/system.img')
            with archive.open(candidates[0]) as source:
                unsparse(source, temporary)
        temporary.rename(args.raw)
        print('Sparse image decoded and ZIP entry CRC checked.', flush=True)
    inspect(args.raw, args.output)


if __name__ == '__main__':
    main()
