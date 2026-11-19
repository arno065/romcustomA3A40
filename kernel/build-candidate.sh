#!/usr/bin/env bash
# Build an unvalidated 3.18.22 hardware-investigation candidate, not Android 13.
# No adb, fastboot, firmware flashing, or privileged commands are used here.
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_root="${ACER_BUILD_DIR:-$project_root/out/kernel-work}"
artifact_root="$project_root/out/kernel-investigation"
kernel_sha=d65e8c4b0f64f36603a16a3a3c386b17a5240d01
toolchain_sha=4b341df712969ca2ac0c3cf6294260d406b9d9be
mkdir -p "$build_root" "$artifact_root"
exec > >(tee "$artifact_root/build.log") 2>&1

cat > "$artifact_root/STATUS.txt" <<'EOF'
UNVALIDATED KERNEL INVESTIGATION, NOT A FLASHABLE ROM.
Target: Acer A3-A40 hardware investigation on a Linux 3.18.22 donor tree.
This is not an Android 13-compatible kernel or a tested recovery.
Inherited battery, camera, sensor and power settings remain unverified.
EOF

checkout_source() {
    local url="$1" sha="$2" destination="$3"
    if [[ -e "$destination" ]]; then
        echo "Refusing to reuse an existing checkout: $destination" >&2
        return 1
    fi
    git init -q "$destination"
    git -C "$destination" remote add origin "$url"
    git -C "$destination" fetch --depth 1 origin "$sha"
    git -C "$destination" checkout -q --detach FETCH_HEAD
    test "$(git -C "$destination" rev-parse HEAD)" = "$sha"
}

checkout_source https://github.com/acer-b1-790/android_kernel_acer_b1-790.git \
    "$kernel_sha" "$build_root/kernel"
checkout_source https://android.googlesource.com/platform/prebuilts/gcc/linux-x86/aarch64/aarch64-linux-android-4.9 \
    "$toolchain_sha" "$build_root/toolchain"

git -C "$build_root/kernel" apply --check \
    "$project_root/kernel/patches/0001-acer-a3a40-observed-hardware-bringup.patch"
git -C "$build_root/kernel" apply \
    "$project_root/kernel/patches/0001-acer-a3a40-observed-hardware-bringup.patch"

compiler="$build_root/toolchain/bin/aarch64-linux-android-"
"${compiler}gcc" --version
printf 'kernel=%s\ntoolchain=%s\n' "$kernel_sha" "$toolchain_sha" > "$artifact_root/revisions.txt"

# Old shipped dtc sources use common globals. Keep this host-only workaround
# separate from flags for the actual ARM64 kernel compiled with GCC 4.9.
make -C "$build_root/kernel" O="$build_root/obj" ARCH=arm64 \
    CROSS_COMPILE="$compiler" HOSTCFLAGS='-O2 -fcommon' \
    acer_jetfirefhd_bringup_defconfig
cp "$build_root/obj/.config" "$artifact_root/kernel.config"

make -C "$build_root/kernel" O="$build_root/obj" ARCH=arm64 \
    CROSS_COMPILE="$compiler" HOSTCFLAGS='-O2 -fcommon' \
    -j"$(nproc)" Image.gz-dtb
cp "$build_root/obj/arch/arm64/boot/Image.gz-dtb" "$artifact_root/"
sha256sum "$artifact_root/Image.gz-dtb" > "$artifact_root/kernel.sha256"
echo 'Kernel compilation completed; hardware compatibility and Android 13 support remain unverified.'
