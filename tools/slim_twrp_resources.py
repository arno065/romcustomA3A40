#!/usr/bin/env python3
"""Remove unused TWRP locales/fonts in the build ramdisk, never on a tablet."""
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

KEEP_LANGUAGES = {'en.xml', 'fr.xml'}
EXTRA_FONTS = {'DroidSansFallback.ttf', 'NotoSansCJKjp-Regular.ttf'}


def slim(root):
    if root.is_symlink():
        raise ValueError('Recovery root must not be a symlink')
    for folder in (root / 'twres', root / 'twres/languages', root / 'twres/fonts'):
        if folder.is_symlink() or not folder.is_dir():
            raise ValueError('Expected a real TWRP resource directory: ' + str(folder))
    languages, fonts = root / 'twres/languages', root / 'twres/fonts'
    # Validate all retained resources before deleting anything.
    for name in sorted(KEEP_LANGUAGES):
        language = languages / name
        if language.is_symlink() or not language.is_file():
            raise ValueError('Required TWRP language missing: ' + name)
        for element in ET.parse(language).iter():
            filename = element.get('filename')
            if element.get('type') == 'fontoverride' and filename:
                if Path(filename).name != filename or filename in EXTRA_FONTS:
                    raise ValueError('Retained language references an unsupported font')
                if not (fonts / filename).is_file() or (fonts / filename).is_symlink():
                    raise ValueError('Required font missing: ' + filename)
    obsolete = [p for p in languages.glob('*.xml') if p.name not in KEEP_LANGUAGES]
    obsolete += [fonts / name for name in sorted(EXTRA_FONTS)
                 if (fonts / name).exists() or (fonts / name).is_symlink()]
    if any(p.is_symlink() or not p.is_file() for p in obsolete):
        raise ValueError('Unexpected non-regular obsolete resource')
    for name in ('ramdisk-files.txt', 'ramdisk-files.sha256sum'):
        manifest = root / name
        if manifest.is_symlink() or (manifest.exists() and not manifest.is_file()):
            raise ValueError('Expected regular ramdisk manifest: ' + name)
    removed = [{'path': str(p.relative_to(root)), 'bytes': p.stat().st_size} for p in sorted(obsolete)]
    for path in obsolete:
        path.unlink()
    # build/make creates these indexes immediately before this hook.
    # Keep them consistent for TWRP's later ramdisk/repack tooling.
    removed_paths = {item['path'] for item in removed}
    listing = root / 'ramdisk-files.txt'
    if listing.is_file():
        lines = [line for line in listing.read_text().splitlines()
                 if line.removeprefix('./') not in removed_paths]
        listing.write_text('\n'.join(lines) + '\n')
    sums = root / 'ramdisk-files.sha256sum'
    if sums.is_file():
        lines = []
        for line in sums.read_text().splitlines():
            fields = line.split(maxsplit=1)
            if len(fields) == 2:
                relative = fields[1].lstrip('*').removeprefix('./')
                if relative in removed_paths:
                    continue
                if relative == 'ramdisk-files.txt' and listing.is_file():
                    line = hashlib.sha256(listing.read_bytes()).hexdigest() + '  ' + fields[1]
            lines.append(line)
        sums.write_text('\n'.join(lines) + '\n')
    return {'kept_languages': sorted(KEEP_LANGUAGES), 'removed': removed,
            'removed_uncompressed_bytes': sum(item['bytes'] for item in removed),
            'note': 'Raw resource bytes; compressed image savings must be measured after build.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    print(json.dumps(slim(args.root), indent=2))


if __name__ == '__main__':
    main()
