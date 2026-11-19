#!/usr/bin/env python3
"""Generate a partial Acer 3.18.22 bring-up patch against a pinned source tree.

This is a recovery/kernel investigation candidate, not Android 13 support.
It does not infer sensor, battery or camera configuration from another tablet.
Inherited defconfig settings still need comparison with the Acer binary kernel.
"""
import argparse
import re
import subprocess
from pathlib import Path

PIN = 'd65e8c4b0f64f36603a16a3a3c386b17a5240d01'
DRIVER = 'drivers/input/touchscreen/mediatek/EKTH3386/ektf_mtk.c'
KCONFIG = 'drivers/input/touchscreen/mediatek/EKTH3386/Kconfig'
NO_UPDATE = 'CONFIG_ACER_A3A40_BRINGUP_NO_TOUCH_FW'


def disable_function(source, name, return_statement):
    # Match definitions, excluding forward declarations, then count C braces
    # while ignoring quoted strings and comments.
    match = re.search(r'\b' + re.escape(name) + r'\([^;{}]*\)\s*(?://[^\n]*)?\s*\{', source)
    if not match:
        raise ValueError(f'Function definition not found: {name}')
    opening = match.end() - 1
    token = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27|[{}]', re.S)
    depth = 1
    closing = None
    for part in token.finditer(source, opening + 1):
        if part.group() == '{':
            depth += 1
        elif part.group() == '}':
            depth -= 1
            if depth == 0:
                closing = part.start()
                break
    if closing is None:
        raise ValueError(f'Unbalanced function: {name}')
    return (source[:opening + 1] + f'\n#ifdef {NO_UPDATE}\n'
            '    /* Preserve the tablet controller firmware during bring-up. */\n'
            f'    {return_statement}\n#else\n' + source[opening + 1:closing]
            + '\n#endif\n' + source[closing:])


def set_config(source, key, value):
    pattern = r'^(?:' + re.escape(key) + r'=.*|# ' + re.escape(key) + r' is not set)\s*$'
    line = f'# {key} is not set' if value is None else f'{key}={value}'
    if re.search(pattern, source, re.M):
        return re.sub(pattern, lambda _: line, source, count=1, flags=re.M)
    return source.rstrip() + '\n' + line + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('project', type=Path)
    args = parser.parse_args()

    def git(*command, **kwargs):
        return subprocess.run(['git', '-C', str(args.kernel), *command], capture_output=True, text=True, **kwargs)

    if git('rev-parse', 'HEAD', check=True).stdout.strip() != PIN:
        raise ValueError('Kernel checkout does not match the audited source revision')
    # Never overwrite a user's unrelated changes to the source files we edit.
    for path in (DRIVER, KCONFIG):
        if git('diff', '--', path, check=True).stdout:
            raise ValueError(f'Existing changes in {path}; use a fresh candidate checkout')

    config = git('show', f'{PIN}:arch/arm64/configs/neostra8163_tb_m_defconfig', check=True).stdout
    settings = {
        'CONFIG_BUILD_ARM64_APPENDED_DTB_IMAGE_NAMES': '"acer_jetfirefhd"',
        'CONFIG_ARCH_MTK_PROJECT': '"neostra8163_tb_m"',
        'CONFIG_CUSTOM_KERNEL_LCM': '"nt71397_wuxga_dsi_vdo_nt65902"',
        'CONFIG_LCM_WIDTH': '"1920"', 'CONFIG_LCM_HEIGHT': '"1200"',
        'CONFIG_TOUCHSCREEN_MTK_GT9XX_MTK': None,
        'CONFIG_TOUCHSCREEN_MTK_EKTH3386': 'y',
        NO_UPDATE: 'y',
    }
    for key, value in settings.items():
        config = set_config(config, key, value)
    config = '\n'.join(line.rstrip() for line in config.splitlines()).rstrip() + '\n'
    config_path = args.kernel / 'arch/arm64/configs/acer_jetfirefhd_bringup_defconfig'
    if config_path.exists():
        raise FileExistsError(config_path)
    config_path.write_text(config)

    dts_path = args.kernel / 'arch/arm64/boot/dts/acer_jetfirefhd.dts'
    if dts_path.exists():
        raise FileExistsError(dts_path)
    dts_path.write_text('// Decompiled from Acer A3-A40 0.013.00 stock DTB; not a 4.9 binding conversion.\n'
                        + (args.project / 'kernel/reference/acer_jetfirefhd.stock.dts').read_text())

    driver = (args.kernel / DRIVER).read_text()
    for name, result in (
        ('check_update_flage', 'return;'),
        ('Update_FW_in_Driver', 'return -EOPNOTSUPP;'),
        ('FW_Update', 'return -EOPNOTSUPP;'),
        ('elan_TWO_WIRE_ICE', 'return -EOPNOTSUPP;'),
    ):
        driver = disable_function(driver, name, result)
    if '#include <linux/errno.h>' not in driver:
        driver = driver.replace('#include', '#include <linux/errno.h>\n#include', 1)
    (args.kernel / DRIVER).write_text(driver)

    kconfig = (args.kernel / KCONFIG).read_text()
    marker = '\nendif'
    if kconfig.count(marker) != 1:
        raise ValueError('Unexpected touchscreen Kconfig structure')
    kconfig = kconfig.replace(marker, '''
config ACER_A3A40_BRINGUP_NO_TOUCH_FW
    bool "Block internal Elan firmware programming during Acer A3-A40 bring-up"
    default n
    help
      Do not auto-program a controller using firmware from the donor source.
      This blocks the internal update/check/ICE entry points. It is not a
      complete access-control mechanism for all debug or raw I2C interfaces.

endif''')
    (args.kernel / KCONFIG).write_text(kconfig)

    tracked = git('diff', '--', DRIVER, KCONFIG, check=True).stdout
    patch = tracked
    for path in (str(config_path.relative_to(args.kernel)), str(dts_path.relative_to(args.kernel))):
        result = git('diff', '--no-index', '--', '/dev/null', path)
        if result.returncode != 1:
            raise ValueError(result.stderr)
        patch += result.stdout
    destination = args.project / 'kernel/patches/0001-acer-a3a40-observed-hardware-bringup.patch'
    destination.write_text(patch)
    print(f'Partial bring-up patch generated: {destination}')
    print('Kernel remains 3.18.22. No kernel compilation, Android 13 image or hardware validation is implied.')


if __name__ == '__main__':
    main()
