# Recovery-only target for the pinned Omni/TWRP Android 9 build environment.
# This does not install Android 9 on the tablet or register an Android 13 target.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/embedded.mk)
$(call inherit-product, vendor/omni/config/common.mk)

PRODUCT_DEVICE := acer_jetfirefhd
PRODUCT_NAME := omni_acer_jetfirefhd
PRODUCT_BRAND := acer
PRODUCT_MODEL := A3-A40
PRODUCT_MANUFACTURER := Acer
PRODUCT_CHARACTERISTICS := tablet
PRODUCT_SHIPPING_API_LEVEL := 23
PRODUCT_AAPT_CONFIG := normal
# Omni's charger image set has xhdpi but no hdpi directory on this branch.
# This resource bucket does not change the explicit LCD density or TWRP theme.
PRODUCT_AAPT_PREF_CONFIG := xhdpi
PRODUCT_LOCALES := en_US fr_FR

# Recovery has no radio, framework, vendor partition or hardware Composer HAL.
PRODUCT_DEFAULT_PROPERTY_OVERRIDES += \
    ro.hardware=mt8163 \
    ro.sf.lcd_density=240 \
    ro.adb.secure=0 \
    persist.sys.usb.config=adb

# build/make copies this device's recovery/root directory automatically.
