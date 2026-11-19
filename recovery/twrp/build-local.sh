#!/usr/bin/env bash
# Build a ramdisk locally, then apply Acer wrappers with the checked packer.
# Android make's intermediate boot.img is not an Acer flashable image.
set -eo pipefail
PROJECT=$(cd -- "$(dirname -- "$0")/../.." && pwd)
SOURCE=${1:?Usage: bash recovery/twrp/build-local.sh SOURCE STOCK_RECOVERY OUTPUT_DIRECTORY}
STOCK=${2:?Pass the documented original Acer recovery.img}
OUTPUT=${3:?Pass a new output directory}
SOURCE=$(realpath -- "$SOURCE")
STOCK=$(realpath -- "$STOCK")
OUTPUT=$(realpath -m -- "$OUTPUT")
JOBS=${ACER_TWRP_JOBS:-2}
[[ "$JOBS" =~ ^[1-9][0-9]*$ ]] || { echo 'ACER_TWRP_JOBS must be positive.' >&2; exit 2; }
[[ ! -e "$OUTPUT" ]] || { echo 'Output directory already exists.' >&2; exit 2; }
[[ -z "${OUT_DIR:-}" && -z "${OUT_DIR_COMMON_BASE:-}" ]] || { echo 'Unset OUT_DIR and OUT_DIR_COMMON_BASE for this recipe.' >&2; exit 2; }
python3 "$PROJECT/tools/twrp_port.py" preflight "$SOURCE"
python3 - "$SOURCE" "$PROJECT/recovery/twrp/sources.json" <<'PY'
import json, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1])
config = json.load(open(sys.argv[2]))
for p in config['projects'] + [dict(path='.repo/manifests', commit=config['manifest']['commit'])]:
    actual = subprocess.check_output(['git', '-C', str(root / p['path']), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != p['commit']:
        raise SystemExit('Unexpected source revision: ' + p['path'])
PY
# The Android 9 build tools require python to be Python 2.7. Our tools use python3.
python -c 'import sys; assert sys.version_info[:2] == (2, 7), "Android 9 build requires python 2.7"'
python3 "$PROJECT/tools/twrp_port.py" prepare "$STOCK" "$SOURCE/device/acer/acer_jetfirefhd"
mkdir -p -- "$OUTPUT"
cd -- "$SOURCE"
repo manifest -r -o "$OUTPUT/sources-resolved.xml"
export ALLOW_MISSING_DEPENDENCIES=true
export LC_ALL=C LANG=C
source build/envsetup.sh
lunch omni_acer_jetfirefhd-eng
# Build just the ramdisk target. Do not publish Android's unwrapped images.
make -j"$JOBS" out/target/product/acer_jetfirefhd/ramdisk-recovery.img 2>&1 | tee "$OUTPUT/build.log"
python3 "$PROJECT/tools/twrp_port.py" pack "$STOCK" \
    out/target/product/acer_jetfirefhd/ramdisk-recovery.img \
    "$OUTPUT/TWRP-A3-A40-PROBE-UNTESTED.img"
echo 'Created an untested unsigned probe; no flash or boot command has been run.'
