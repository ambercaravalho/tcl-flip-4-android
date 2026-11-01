# Build and publish a release

This is a maintainer runbook. Community installers should use the versioned
[installation guide](../guides/install-v0.1.0.md).

## Inputs

The release pipeline is intentionally hash-pinned. Downloaded APKs remain
ignored under `artifacts/downloads/release-components/`; generated images
remain ignored under `artifacts/build/`.

Prepare the host and components:

```bash
tooling/scripts/setup.sh
tooling/scripts/fetch-release-components.py
tooling/scripts/build-c9-t440w.sh
tooling/scripts/build-keypad-cursor.sh \
  artifacts/build/keypad-actions-release-v2
```

The canonical component identities and source commits are in
`tooling/release-components.json`.

The image builders also require Android SDK tools and the local
`t440w-tools:local` container used by the ext4/SELinux steps. That container is
not yet defined by this repository; a new host cannot claim a reproducible
build until its toolchain is independently reconstructed and recorded.

## Build the accepted system set

The `v0.1.0` release was produced from these exact inputs:

```bash
tooling/scripts/build-rooted-release.py \
  --system artifacts/build/keypad-profile-current/system_b-keypad.img \
  --expect-system-sha256 d20e2c86bd2ac4bae24384f9a53ad68f872d5b1cd21a6c2dc5baad534a172112 \
  --odm artifacts/build/keypad-profile-odm-correction/odm_b-keypad.img \
  --expect-odm-sha256 2e66c8535449f239c180947a592434e452e3a979cfc89f8bf0ebe90433100c89 \
  --vendor artifacts/build/vendor_b.img \
  --expect-vendor-sha256 c0f59c061b67559c379c8b51df7e1a30545c30a24591cf436b47fcd557475bdb \
  --vbmeta artifacts/build/rooted-release/magisk/vbmeta_b-magisk.img \
  --expect-vbmeta-sha256 db7fb47c124352a03859e8ad16df17d0c37b54f31d40e031fb275800398dab00 \
  --vbmeta-system artifacts/build/keypad-profile-current/vbmeta_system_b-keypad.img \
  --expect-vbmeta-system-sha256 5bb155cde647c2d275ecdec48587c0e181aab44d9f7b55c4126f5bd39c31b44c \
  --super-meta artifacts/build/android-lineage21-clean/super_meta_android.img \
  --expect-super-meta-sha256 1fc97f04e3f50149295e9a082be9ae1901fa67451d742ab791372c59115ab725 \
  --out-dir artifacts/build/rooted-release/rebuild-v0.1.0
```

The Magisk input was derived separately with
`tooling/scripts/patch-magisk-init-boot.sh`, which requires the exact current
`init_boot_b` and top-level vbmeta plus a rooted 32-bit ARM Android
environment. Do not patch a filename selected by convention.

The full-height display partition was built with
`tooling/scripts/build-spi-driver-variant.py full-height-client` from the exact
stock `vendor_dlkm_b`. The patcher rejects any `msm_drm.ko` other than SHA-256
`39f972853c5acb061a3964a48cf6bf0ff375b55dc216e537c69e76c290755065`.

The exact matching TCL 6.1 module source is unavailable. Shipping the binary
patched GPL module therefore has an unresolved corresponding-source risk; the
non-matching TCL 4.19/5.15 disclosures do not cure it.

## Reproducibility gate

Build into a local, non-synchronized output directory twice. Compare:

- system and both release extents;
- ODM;
- super metadata;
- `vbmeta_system_b`;
- final top-level vbmeta.

Every pair must be byte-identical and match
`tooling/releases/v0.1.0.json`. Run the release verifier before packaging:

```bash
.venv/bin/python tooling/scripts/install-release.py \
  artifacts/releases/v0.1.0
```

Do not publish the monolithic system image; it duplicates the two flash
extents and exceeds GitHub's per-asset limit. Never package backups, userdata,
stock OTAs, untracked/private signing material, evidence captures, or absolute
host paths. The tracked public AOSP test keys are required to reproduce this
release and are not private trust anchors.

## Package

Commit and push the final documentation/tooling first. The packager refuses a
dirty tree so the archived sources and sanitized manifest can name one exact
commit. Then create the staging directory and metadata:

```bash
.venv/bin/python tooling/scripts/package-release.py \
  --output artifacts/releases/v0.1.0
```

The packager copies only the allowlisted image set, writes `SHA256SUMS`, a
path-sanitized manifest, release notes, and a source/provenance archive. Review
all generated text before upload.

## Publish with GitHub CLI

Tag the clean source commit named by `release-manifest.json`:

```bash
git tag -a v0.1.0 -m "T440W Android 14 v0.1.0"
git push origin v0.1.0
```

Create a draft pre-release and upload the staged assets:

```bash
gh release create v0.1.0 \
  --repo ambercaravalho/tcl-flip-4-android \
  --title "T440W Android 14 v0.1.0" \
  --notes-file artifacts/releases/v0.1.0/RELEASE_NOTES.md \
  --prerelease --draft

gh release upload v0.1.0 artifacts/releases/v0.1.0/* \
  --repo ambercaravalho/tcl-flip-4-android
```

Inspect names and sizes with `gh release view`. Download `SHA256SUMS`, the
sanitized manifest, and small image assets into a new temporary directory and
hash them again. Publish only after remote verification:

```bash
gh release edit v0.1.0 \
  --repo ambercaravalho/tcl-flip-4-android \
  --draft=false --prerelease
```

Record the tag commit and final release URL in the handoff. A GitHub release is
not accepted merely because upload commands returned success.
