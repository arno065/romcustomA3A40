/* Legacy Acer MT8163 lock entry point -> Android 13 libui lock entry point.
 *
 * The only values forwarded are pointers and a 32-bit usage field. No C++
 * object is allocated, dereferenced or reinterpreted by this adapter. Its
 * integration still requires a target libui exporting the verified long
 * signature and a valid target GraphicBufferMapper object supplied by the
 * caller. This does not validate the rest of the graphics ABI or the kernel.
 */

_Static_assert(sizeof(int) == 4, "Android status_t must be 32-bit");
_Static_assert(sizeof(unsigned int) == 4, "Android usage must be 32-bit");

/* C++ references are pointer arguments in the Android ARM Itanium ABI.
 * Verified against LineageOS lineage-20.0 GraphicBufferMapper.h and the
 * corresponding overload symbol used by the MT8163 reference implementation.
 */
extern int acer_mapper_lock_target(void *self, const void *handle,
                                   unsigned int usage, const void *bounds,
                                   void **address, int *bytes_per_pixel,
                                   int *bytes_per_stride)
    __asm__("_ZN7android19GraphicBufferMapper4lockEPK13native_handlejRKNS_4RectEPPvPiS9_");

int acer_mapper_lock_legacy(void *self, const void *handle, unsigned int usage,
                           const void *bounds, void **address)
    __asm__("_ZN7android19GraphicBufferMapper4lockEPK13native_handlejRKNS_4RectEPPv");

int acer_mapper_lock_legacy(void *self, const void *handle, unsigned int usage,
                           const void *bounds, void **address)
{
    if (!self || !handle || !bounds || !address)
        return -22; /* android::BAD_VALUE == -EINVAL */

    return acer_mapper_lock_target(self, handle, usage, bounds, address,
                                   (int *)0, (int *)0);
}
