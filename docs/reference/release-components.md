# Release components

The rooted community release profile uses only hash-pinned upstream artifacts.
`tooling/release-components.json` is the canonical machine-readable manifest;
downloaded APKs remain ignored under
`artifacts/downloads/release-components/`.

## Included projects

- **Magisk 31.1** — GPL-3.0, official
  [`topjohnwu/Magisk`](https://github.com/topjohnwu/Magisk) release. MagiskSU
  uses explicit grants configured in the Manager. The release profile grants
  no application root by default. The root payload lives in patched
  `init_boot_b`. Manager rejects a system-app installation, so the image
  carries its pinned APK under `/system/etc/t440w/release/` and the release
  procedure installs it normally under `/data/app`.
- **C9 3.0.4** — Apache-2.0, official
  [`austinauyeung/C9`](https://github.com/austinauyeung/C9) release. The T440W
  build carries only device-default key and appearance changes; corresponding
  source and patch material must ship with a binary release. Two clean builds,
  after removing AGP's optional nondeterministically ordered baseline-profile
  hints, produce SHA-256
  `0fdaf4646a5bdc7ac85853aeacbe48fc71f2326d5c70594f85958c8fda7f28f2`.
- **microG Services 0.3.17.252432 and Companion** — Apache-2.0, official
  [`microg/GmsCore`](https://github.com/microg/GmsCore) custom-ROM artifacts.
  These replace proprietary Google client components, but enabled features
  still communicate with proprietary Google network services. Privileged,
  default-permission, and power-management XML is derived from hash-pinned
  `lineageos4microg/android_vendor_partner_gms`; this GSI's restrictive
  spoofing implementation does not expose `FAKE_PACKAGE_SIGNATURE`, so that
  nonexistent permission is deliberately omitted from the device allowlists.
  Existing-user upgrades also require the default background-location grant;
  the final permission XML includes it and runtime verification passed.
- **Aurora Store 4.8.4** — GPL-3.0, official F-Droid distribution of
  [`AuroraOSS/AuroraStore`](https://gitlab.com/AuroraOSS/AuroraStore).
  The non-privileged system installation uses Android's confirmed Session
  Installer. It receives no silent-install or root grant.

## Selection notes

- FlipMouse is specific to the TCL Flip 2 but its repository declares no
  license. It must not be redistributed or modified without an explicit
  license from its author.
- MATVT is GPL-3.0, but the project's phone-release source provenance is
  disputed in its own release notes. C9 has a current, fully published phone
  implementation and a permissive redistribution license.
- GsfProxy is not included by default. The current microG release recommends
  Services plus Companion for custom ROMs; add another component only if
  microG Self-Check or a directly tested compatibility requirement proves it
  necessary. The accepted release leaves only the optional legacy
  GsfProxy/C2DM Self-Check item unchecked.

## Update procedure

1. Confirm the new release on the project's canonical release page.
2. Record the exact source tag/commit, artifact size, SHA-256, and license.
3. Update `tooling/release-components.json`.
4. Run `tooling/scripts/fetch-release-components.py` from an empty cache.
5. Verify APK package names, signing certificates, ABI coverage, minimum SDK,
   and reproducibility or upstream release signatures where available.
6. Re-run the complete offline image and physical-device release gates.

Do not replace an artifact merely because a mutable “latest” URL changed.
