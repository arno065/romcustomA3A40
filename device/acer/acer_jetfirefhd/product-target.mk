# Proposed product settings, not a complete runnable product or shipping config.
PRODUCT_BRAND := acer
PRODUCT_MANUFACTURER := Acer
PRODUCT_MODEL := A3-A40
PRODUCT_DEVICE := acer_jetfirefhd
PRODUCT_CHARACTERISTICS := tablet
PRODUCT_SHIPPING_API_LEVEL := 23
PRODUCT_AAPT_PREF_CONFIG := hdpi
PRODUCT_AAPT_CONFIG := normal large xlarge hdpi

# Keep ARM64 applications and ARM32 compatibility. Do not automatically enable
# ro.config.low_ram/Android Go: some apps hide features based on that flag.
# No GApps package is included in this bring-up fragment.
# No SELinux permissive override, fake security patch level or Amazon identity.
