DEVICE_PATH := device/acer/acer_jetfirefhd
# Copied from the measured common geometry by tools/twrp_port.py prepare.
include $(DEVICE_PATH)/BoardConfig.stock.mk

TARGET_NO_BOOTLOADER := true
TARGET_NO_RADIOIMAGE := true
TARGET_PREBUILT_KERNEL := $(DEVICE_PATH)/prebuilt/stock-kernel.gz-dtb
BOARD_HAS_NO_SELECT_BUTTON := true
BOARD_HAS_NO_REAL_SDCARD := true
BOARD_BUILD_SYSTEM_ROOT_IMAGE := false
BOARD_USES_RECOVERY_AS_BOOT := false
BOARD_AVB_ENABLE := false
BOARD_RECOVERY_SWIPE := true
TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/recovery.fstab
TARGET_RECOVERY_PIXEL_FORMAT := "RGBX_8888"
TARGET_SCREEN_WIDTH := 1920
TARGET_SCREEN_HEIGHT := 1200
RECOVERY_GRAPHICS_FORCE_USE_LINELENGTH := true

TW_THEME := landscape_hdpi
TW_DEFAULT_LANGUAGE := fr
TW_EXTRA_LANGUAGES := true
TW_NO_REBOOT_BOOTLOADER := true
TW_NO_USB_STORAGE := true
TW_NO_SCREEN_TIMEOUT := true
TW_NO_SCREEN_BLANK := true
TW_NO_HAPTICS := true
TW_NO_CPU_TEMP := true
TW_INCLUDE_CRYPTO := false
TW_EXCLUDE_ENCRYPTED_BACKUPS := true
TW_EXCLUDE_MTP := true
TW_EXCLUDE_BASH := true
TW_EXCLUDE_NANO := true
TW_EXCLUDE_PYTHON := true
TW_EXCLUDE_TZDATA := true

# No guessed touchscreen rotation/brightness sysfs path is imposed here.
# Do not enable BOARD_HAS_MTK_HARDWARE: wrappers are added by our final packer.
# Do not flash Android make's intermediate boot.img, which lacks MTK wrappers.
