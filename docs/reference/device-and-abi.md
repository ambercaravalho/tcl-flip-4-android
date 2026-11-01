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
- `48` -> `BACK`
- `30` -> `ENVELOPE`
- `138` -> `CONTACTS`

The validated physical-keypad profile additionally maps:

- matrix and PMIC `116` -> `HOME WAKE`;
- left/right softkeys `139`/`158` -> inert `F1`/`F2`;
- `231` remains `CALL`.

The version-code-3 `org.tclflip4.keypadcursor` AccessibilityService
consumes the reserved keys needed for global behavior. `ENVELOPE` launches
Messaging and `CONTACTS` delegates cursor toggle to C9. C9 supplies the cursor,
D-pad movement, center click, and conditional page up/down behavior.

Revision 3 deliberately differs in byte length from revision 2. PackageManager
can otherwise reuse a stale same-path manifest when two system APK revisions
have equal size and normalized timestamps.

TrebleDroid's `vndk.rc` copies `persist.sys.phh.mainkeys` to
`qemu.hw.mainkeys`. The ODM init hook sets both to `1` before framework startup
to omit the unusable on-screen navigation bar. On the accepted final boot,
`qemu.hw.mainkeys` was no longer visible after startup while the navigation-bar
inset remained absent; post-boot validation must inspect the actual inset and
physical panel rather than rely only on the late property value.

Evidence:
[`2026-11-01-09-physical-keypad-navigation.md`](../findings/2026-11-01-09-physical-keypad-navigation.md),
[`2026-11-01-10-rooted-release-stack.md`](../findings/2026-11-01-10-rooted-release-stack.md),
and
[`2026-11-01-11-release-display-regression.md`](../findings/2026-11-01-11-release-display-regression.md).

## Debugging caveat

Do not infer root ADB from ODM input properties. On the clean GSI, the runtime
was `ro.debuggable=0` and `service.adb.root=0` because `ro.debuggable` had
already become read-only. See
[`2026-11-01-02-clean-gsi-debugging.md`](../findings/2026-11-01-02-clean-gsi-debugging.md).

The tested Lineage/crDroid GSI instead exposes `adbroot_service` and a
**Rooted debugging** switch in Developer options. Enabling that switch through
the system Settings UI produced root adbd, `service.adb.root=1`, and writable
tracefs even though `ro.debuggable=0` and `ro.force.debuggable=0` remained
unchanged. Shell cannot directly call `setEnabled()` because the service
requires a system-UID caller.

The stock `init_boot_b` ramdisk's
`system/etc/ramdisk/build.prop` contains boot-image identity only, not either
debug property. AOSP's separate `/force_debuggable` mechanism is gated on an
unlocked/orange verified-boot state and is not activated by adding the marker
to this locked/green device.

Evidence:
[`2026-11-01-03-gsi-adb-root.md`](../findings/2026-11-01-03-gsi-adb-root.md).

## Accepted release security profile

The rooted release uses an enforcing policy, authenticated non-root adbd, and
Magisk 31.1 in patched `init_boot_b`. Unknown applications and ADB shell are
denied by default; application root requires an explicit Manager grant.
Manager itself must be installed under `/data/app`, not scanned as a system
application. Trace collection is disabled in the final state.

Evidence:
[`2026-11-01-10-rooted-release-stack.md`](../findings/2026-11-01-10-rooted-release-stack.md).
