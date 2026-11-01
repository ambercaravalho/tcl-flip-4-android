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
tooling/scripts/prepare_gsi.py path/to/gsi.img.xz \
  --out-dir artifacts/build/android-flash \
  --display-profile none
```

The default USB diagnostic profile requests ADB/debug properties and installs
the legacy ConfigFS fallback. It does **not** prove that runtime root ADB will
be available. To omit it:

```bash
tooling/scripts/prepare_gsi.py path/to/gsi.img.xz \
  --out-dir artifacts/build/android-flash \
  --no-usb-diagnostics \
  --display-profile none
```

The `wait-fences` and `spec-fence-off` display profiles exist only to reproduce
failed experiments. They are not fixes and must not be part of a normal build.

## Required output checks

1. Inspect `artifacts/build/android-flash/build-manifest.json`.
2. Confirm SDK is exactly 34.
3. Confirm `/system/bin/init` was identified as 32-bit ARM.
4. Record the source archive SHA-256, actual fingerprint, release, security
   patch, diagnostics selection, and output directory in the session finding.
5. Hash every output intended for flashing.
6. Inspect both vbmeta outputs with:

```bash
tooling/tools/avb/avbtool.py info_image \
  --image artifacts/build/android-flash/vbmeta_b_android.img
tooling/tools/avb/avbtool.py info_image \
  --image artifacts/build/android-flash/vbmeta_system_b_android.img
```

7. Verify the generated `super` metadata maps `system_b` to the intended
   extent(s) and leaves `product_b` and `system_ext_b` at zero length.

## Handoff

The session record must name the exact output hashes and expected rollback
path. Flash only through
[`flash-and-verify.md`](flash-and-verify.md).

After boot, verify image identity and the complete ADB/root gate. Do not report
“debug enabled” based only on this build's ODM contents. The failed inference is
documented in
[`../findings/2026-11-01-02-clean-gsi-debugging.md`](../findings/2026-11-01-02-clean-gsi-debugging.md).
