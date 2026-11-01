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
  --display-profile none
```

The default USB diagnostic profile requests ADB/debug properties, installs the
legacy ConfigFS fallback, and includes the validated bounded
forced-client-composition helper and early hardware-navigation policy in ODM.
The preparation pipeline also embeds the signed keypad-cursor APK and its
idempotent accessibility enablement helper in system. It does **not** prove
that runtime root ADB will be available. To omit USB diagnostics:

```bash
tooling/scripts/prepare_gsi.py path/to/gsi.img.xz \
  --out-dir artifacts/build/android-flash \
  --no-usb-diagnostics \
  --display-profile none
```

`--no-usb-diagnostics` also omits the current device-specific ODM init file and
therefore omits persistent forced client composition. Do not treat that output
as the stable display or navigation baseline without adding and independently
validating equivalent early-init hooks.

The `wait-fences` and `spec-fence-off` display profiles exist only to reproduce
failed experiments. They are not fixes and must not be part of a normal build.

## Required output checks

1. Inspect `artifacts/build/android-flash/build-manifest.json`.
2. Confirm SDK is exactly 34.
3. Confirm `/system/bin/init` was identified as 32-bit ARM.
4. Record the source archive SHA-256, actual fingerprint, release, security
   patch, diagnostics selection, and output directory in the session finding.
5. Hash every output intended for flashing.
6. For the normal diagnostics-enabled build, confirm ODM contains
   `/bin/t440w-force-client-composition.sh` and
   `/etc/init/init.t440w.debug.rc`, has both mainkeys properties set to `1`,
   and contains the final device keylayouts with the expected modes and SELinux
   labels.
7. Confirm system contains:
   - `/system/app/T440WKeypadCursor/T440WKeypadCursor.apk`;
   - `/system/bin/t440w-enable-keypad.sh`;
   - `/system/etc/init/init.t440w.keypad.rc`.
   Verify the embedded APK signature and compare all three files byte-for-byte
   with their sources.
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

After boot, verify image identity and the complete ADB/root gate. Do not report
“debug enabled” based only on this build's ODM contents. The failed inference is
documented in
[`../findings/2026-11-01-02-clean-gsi-debugging.md`](../findings/2026-11-01-02-clean-gsi-debugging.md).
Also wait for the bounded helper to stop, confirm transaction `1010` still
reports forced client composition enabled, and perform the physical display
gate before relying on the panel. Confirm the baked keypad service is enabled
and bound, both mainkeys properties are `1`, no navigation-bar inset source is
present, and perform the complete physical-keypad/cursor gate.
