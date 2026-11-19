#!/usr/bin/env python3
"""Retrieve the documented stock archive and verify its exact SHA-256.

The archive is not installed, extracted or executed. Google Drive's public
large-file confirmation page is handled; sign-in/quota errors are not bypassed.
"""
import argparse
import hashlib
import html.parser
import http.cookiejar
import json
import urllib.parse
import urllib.request
from pathlib import Path


class Confirmation(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.action = None
        self.values = {}

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'form' and attrs.get('id') == 'download-form':
            self.active = True
            self.action = attrs.get('action')
        if self.active and tag == 'input' and attrs.get('type') == 'hidden':
            self.values[attrs['name']] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form':
            self.active = False


def checksum(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('downloads/acer-a3a40-stock-0.013.00.zip'))
    args = parser.parse_args()
    metadata = json.loads((Path(__file__).resolve().parents[1] / 'sources/firmware.json').read_text())
    if args.output.exists():
        if checksum(args.output) == metadata['sha256']:
            print(f'Already present and verified: {args.output}')
            return
        raise FileExistsError('Existing output does not match the expected firmware; it will not be overwritten')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.partial')
    if temporary.exists():
        raise FileExistsError(f'An interrupted download exists: {temporary}')

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    response = opener.open(metadata['download_url'], timeout=60)
    if 'text/html' in response.headers.get('Content-Type', ''):
        with response:
            page = response.read(128 * 1024).decode('utf-8', errors='replace')
        form = Confirmation()
        form.feed(page)
        parsed = urllib.parse.urlsplit(form.action or '')
        if parsed.scheme != 'https' or parsed.netloc != 'drive.usercontent.google.com' or parsed.path != '/download':
            raise RuntimeError('No public download confirmation found; the mirror may require login or have exceeded its quota')
        query = urllib.parse.urlencode(form.values)
        response = opener.open(form.action + '?' + query, timeout=60)
    with response:
        if 'text/html' in response.headers.get('Content-Type', ''):
            raise RuntimeError('The mirror returned an HTML page instead of the firmware archive')
        digest = hashlib.sha256()
        count = 0
        with temporary.open('xb') as target:
            while block := response.read(4 * 1024 * 1024):
                count += len(block)
                if count > metadata['bytes']:
                    raise ValueError('Download exceeds the documented firmware size')
                target.write(block)
                digest.update(block)
        if count != metadata['bytes'] or digest.hexdigest() != metadata['sha256']:
            raise ValueError(f'Firmware integrity mismatch; unverified file kept at {temporary}')
    temporary.rename(args.output)
    print(f'Download verified: {args.output}\nSHA-256: {digest.hexdigest()}')


if __name__ == '__main__':
    main()
