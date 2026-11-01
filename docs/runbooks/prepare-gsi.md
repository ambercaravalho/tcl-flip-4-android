# Prepare an Android 14 GSI

This procedure is offline. It does not authorize flashing the output.

## Inputs

- Android 14 / SDK 34 `a64_bvN` GSI (`.img`, `.img.xz`, or `.img.gz`)
- `artifacts/build/odm_b-dbg-patched.img`
- `artifacts/build/vendor_b.img`
- `artifacts/build/vbmeta_b.img`
- `artifacts/build/vbmeta_system_b.img`

Do not choose an image from its filename alone.

## Prepare

From the repository root:

```bash
tooling/scripts/setup.sh
tooling/scripts/build-keypad-cursor.sh
tooling/scripts/prepare_gsi.py path/to/gsi.img.xz \
  --out-dir artifacts/build/android-flash \
  --selinux-mode enforcing \
  --display-profile none
```

The default release profile does not force USB debugging or root adbd. It sets
`ro.adb.secure=1`, includes the validated bounded forced-client-composition
helper and early hardware-navigation policy in ODM, and generates an enforcing
merged SELinux policy. The pipeline also embeds the signed keypad action APK
and its idempotent accessibility enablement helper in system.

To add the authenticated legacy ConfigFS ADB fallback for bring-up:

```bash
tooling/scripts/prepare_gsi.py path/to/gsi.img.xz \
  --out-dir artifacts/build/android-flash \
  --usb-diagnostics \
  --display-profile none
```

An unauthenticated root-adbd request now requires both
`--usb-diagnostics --unsafe-root-adb`. It is a bring-up-only profile and must
not be distributed. A broad permissive policy likewise requires the explicit
`--selinux-mode permissive` option.

The platform init file and composition helper are independent of USB selection,
so release builds retain the stable display and navigation baseline.

The `wait-fences` and `spec-fence-off` display profiles exist only to reproduce
failed experiments. They are not fixes and must not be part of a normal build.

## Required output checks

1. Inspect `artifacts/build/android-flash/build-manifest.json`.
2. Confirm SDK is exactly 34.
3. Confirm `/system/bin/init` was identified as 32-bit ARM.
4. Record the source archive SHA-256, actual fingerprint, release, security
   patch, diagnostics selection, and output directory in the session finding.
5. Hash every output intended for flashing.
6. Confirm ODM contains
   `/bin/t440w-force-client-composition.sh` and
   `/etc/init/init.t440w.platform.rc`, has both mainkeys properties set to `1`,
   sets `ro.adb.secure=1`, and contains the final device keylayouts with the
   expected modes and SELinux labels. Release output must not contain
   `/etc/init/init.t440w.debug.rc`.
7. Confirm system contains:
   - `/system/app/T440WKeypadCursor/T440WKeypadCursor.apk`;
   - `/system/bin/t440w-enable-keypad.sh`;
   - `/system/etc/init/init.t440w.keypad.rc`.
   Verify the embedded APK signature and compare all three files byte-for-byte
   with their sources. If an APK revision changes manifest components, increase
   its version code; equal-version replacement may leave existing-user package
   metadata stale.
8. Inspect both vbmeta outputs with:

```bash
tooling/tools/avb/avbtool.py info_image \
  --image artifacts/build/android-flash/vbmeta_b_android.img
tooling/tools/avb/avbtool.py info_image \
  --image artifacts/build/android-flash/vbmeta_system_b_android.img
```

9. Verify the generated `super` metadata maps `system_b` to the intended
   extent(s) and leaves `product_b` and `system_ext_b` at zero length.

## Handoff

The session record must name the exact output hashes and expected rollback
path. Flash only through
[`flash-and-verify.md`](flash-and-verify.md).

After boot, verify image identity and the complete ADB/root gate. On release
output, `adb shell id` must remain shell and `adb root` must fail; Magisk
application root is a separate gate. Do not infer either state from image
contents. The earlier failed property inference is documented in
[`../findings/2026-11-01-02-clean-gsi-debugging.md`](../findings/2026-11-01-02-clean-gsi-debugging.md).
Also wait for the bounded helper to stop, confirm transaction `1010` still
reports forced client composition enabled, and perform the physical display
gate before relying on the panel. Confirm the baked keypad service is enabled
and bound, `persist.sys.phh.mainkeys=1`, no navigation-bar inset source is
present, and perform the complete physical-keypad/cursor gate. A late
`qemu.hw.mainkeys` value alone is not a sufficient functional check.

For the rooted release, install the image-carried Manager as a normal data app:

```bash
adb shell pm install -r -g \
  /system/etc/t440w/release/Magisk-v31.1.apk
adb shell pm path com.topjohnwu.magisk
```

The path must resolve under `/data/app`, and Manager must open without its
system-app abnormal-state warning. Verify an ordinary test application is
denied first, explicitly grant it in Manager, confirm UID 0 in
`u:r:magisk:s0`, then delete the policy and uninstall the probe. Reconfirm
shell `su` remains denied.
