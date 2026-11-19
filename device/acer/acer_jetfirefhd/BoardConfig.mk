# Integration scaffold. No lunch target is registered until the kernel and
# Android 13 HAL/linker strategy have been implemented and checked.
DEVICE_PATH := device/acer/acer_jetfirefhd
include $(DEVICE_PATH)/BoardConfig.stock.mk

# An old proprietary kernel is useful for a recovery experiment, but must not
# silently become the Android 13 production kernel. Supply this file only after
# choosing the actual Acer kernel source/configuration and build format.
include $(DEVICE_PATH)/BoardConfig.kernel.mk
