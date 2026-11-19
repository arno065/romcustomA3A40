#!/usr/bin/env python3
"""Decode FDT properties without treating binary cell arrays as text strings."""
import argparse
import json
import struct
from pathlib import Path


def decode(data):
    if len(data) < 40:
        raise ValueError('Truncated FDT header')
    header = struct.unpack_from('>10I', data)
    magic, total, structure, strings = header[:4]
    if magic != 0xD00DFEED or total > len(data):
        raise ValueError('Invalid FDT header')
    names = data[strings:strings + header[8]]
    pos = structure
    stack, result = [], {}
    while pos + 4 <= structure + header[9]:
        token = struct.unpack_from('>I', data, pos)[0]
        pos += 4
        if token == 1:
            end = data.index(b'\0', pos)
            stack.append(data[pos:end].decode())
            pos = (end + 4) & ~3
            result['/'.join(stack) or '/'] = {}
        elif token == 2:
            stack.pop()
        elif token == 3:
            size, offset = struct.unpack_from('>II', data, pos)
            pos += 8
            value = data[pos:pos + size]
            if len(value) != size:
                raise ValueError('Truncated FDT property')
            pos = (pos + size + 3) & ~3
            name = names[offset:names.index(b'\0', offset)].decode()
            entry = {'raw_hex': value.hex()}
            pieces = value[:-1].split(b'\0') if value.endswith(b'\0') else []
            if pieces and all(p and all(32 <= c < 127 for c in p) for p in pieces):
                entry['strings'] = [p.decode() for p in pieces]
            elif value and len(value) % 4 == 0:
                entry['cells'] = list(struct.unpack('>' + str(len(value) // 4) + 'I', value))
            elif not value:
                entry['boolean'] = True
            result['/'.join(stack) or '/'][name] = entry
        elif token == 9:
            return result
        elif token != 4:
            raise ValueError(f'Unknown FDT token {token}')
    raise ValueError('FDT end token missing')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dtb', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(decode(args.dtb.read_bytes()), indent=2) + '\n')


if __name__ == '__main__':
    main()
