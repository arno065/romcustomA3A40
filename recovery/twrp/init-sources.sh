#!/usr/bin/env bash
# Explicit local operation only. Never invoked by GitHub Actions.
set -euo pipefail
PROJECT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
SOURCE=${1:?Usage: bash recovery/twrp/init-sources.sh /new/source/directory}
command -v repo >/dev/null || { echo 'Install the Android repo launcher first.' >&2; exit 2; }
command -v python3 >/dev/null
python3 - "$SOURCE" <<'PY'
import shutil, sys
from pathlib import Path
dest = Path(sys.argv[1]).resolve()
if dest.exists():
    raise SystemExit('Use a new directory; existing source trees are not overwritten.')
ancestor = dest.parent
while not ancestor.exists():
    ancestor = ancestor.parent
if shutil.disk_usage(ancestor).free < 40 * 1024**3:
    raise SystemExit('Need at least 40 GiB free before syncing TWRP sources; 60+ GiB recommended.')
PY
mkdir -p -- "$SOURCE"
cd -- "$SOURCE"
readarray -t MANIFEST < <(python3 - "$PROJECT/recovery/twrp/sources.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))['manifest']
print(s['url']); print(s['commit'])
PY
)
repo init --depth=1 -u "${MANIFEST[0]}" -b "${MANIFEST[1]}"
mkdir -p .repo/local_manifests
python3 - "$PROJECT/recovery/twrp/sources.json" <<'PY'
import json, sys
from xml.etree import ElementTree as ET
root = ET.Element('manifest')
for p in json.load(open(sys.argv[1]))['projects']:
    ET.SubElement(root, 'extend-project', name=p['name'], path=p['path'], revision=p['commit'])
ET.ElementTree(root).write('.repo/local_manifests/acer-pins.xml', encoding='utf-8', xml_declaration=True)
PY
repo sync -c --no-clone-bundle --no-tags -j2
repo manifest -r -o acer-sources-resolved.xml
echo 'Sources synced. Build remains a separate explicit local operation.'
