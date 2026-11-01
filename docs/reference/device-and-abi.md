# Device and userspace ABI reference

## Identity

- Device: TCL Flip 4 5G / Go Flip 5G, model T440W
- Product/platform names: `gflip5gtmo`, `pitti_32go`
- SoC HWID: `0x002980e100420071` (`MSM_ID 0x002980e1`)
- EDL USB ID: `05c6:9008`
- Storage: eMMC, 512-byte sectors, approximately 29.12 GiB
  (61,079,552 sectors)
- Layout: A/B with Virtual A/B and dynamic partitions in `super`
- Reference unit active slot: B

Evidence:
[`2026-10-31-02-offline-groundwork.md`](../findings/2026-10-31-02-offline-groundwork.md)
and [`CAPABILITIES.md`](../CAPABILITIES.md).

## ABI

The kernel is 64-bit ARM64 with 32-bit compatibility enabled. First-stage init,
vendor, and ODM userspace are 32-bit ARM and expose VNDK/API 34. The required
GSI is therefore:

- Android 14 / SDK 34
- `a64` / `arm32_binder64`
- A/B
- vanilla (`a64_bvN`)

An `arm64` userspace is not compatible merely because the kernel is ARM64.
Evidence:
[`2026-10-31-02-offline-groundwork.md`](../findings/2026-10-31-02-offline-groundwork.md).

## Stock/GSI boundary

The retained boot and hardware side is:

- `boot`, `init_boot`, `vendor_boot`, `dtbo`
- `vendor`, `odm`, `vendor_dlkm`, `system_dlkm`

The replaceable userspace side is:

- `system`
- `system_ext`
- `product`

For a GSI, `system_ext_b` and `product_b` must remain zero-length in `super`
metadata so first-stage init does not mount stock KaiOS partitions over the
copies inside the GSI.

## SELinux compatibility

Stock vendor policy references KaiOS/QTI `_34_0` types absent from a generic
GSI. The preparation pipeline combines GSI and vendor CIL with
`device/t440w/selinux/t440w_compat.cil`, writes a matching permissive
`precompiled_sepolicy` to ODM, and supplies matching policy hashes.

The kernel does not honor a SELinux permissive kernel-command-line switch, so
the loaded policy must carry the permissive map during bringup.

## Physical input

Stock KaiOS keylayout files contain names invalid to AOSP and several useful
T440W scancodes are absent or conflicting in AOSP `Generic.kl`. The prepared
ODM supplies valid device keylayouts, and the GSI's `Generic.kl` is corrected
for:

- `352` -> `DPAD_CENTER`
- `48` -> `DEL`
- `30` -> `ENVELOPE`
- `138` -> `CONTACTS`

## Debugging caveat

Do not infer root ADB from ODM input properties. On the clean GSI, the runtime
was `ro.debuggable=0` and `service.adb.root=0` because `ro.debuggable` had
already become read-only. See
[`2026-11-01-02-clean-gsi-debugging.md`](../findings/2026-11-01-02-clean-gsi-debugging.md).
