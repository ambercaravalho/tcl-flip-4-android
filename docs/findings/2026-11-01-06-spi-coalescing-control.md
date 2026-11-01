# 2026-11-01 06: SPI coalescing control

Status: complete

## Objective

Determine whether collapsing a burst of independent framebuffer submissions
to one pending SPI transfer makes the controlled GSI transition physically
stable. Hold plane acceptance, AB24 conversion, staging layout, TE handling,
SPI clock, and DTBO constant.

## Starting state

- Captured at `2026-11-01T16:27:12Z`.
- Device mode and active slot: booted Android GSI over ADB, slot B (`_b`).
- Running OS:
  - fingerprint:
    `TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys`
  - system fingerprint: same as runtime fingerprint
  - SDK: `34`
  - ABI: `armeabi-v7a`
  - flavor: `treble_a64_bvN-userdebug`
  - verified-boot state: locked/green
- Runtime image identity:
  - top-level vbmeta digest:
    `fa818c9ccb99bfce94979e2b449a8404e5ab140f9e9f0077bad94cb470c6f657`
  - system root digest:
    `07d1de5bd1fcecf354df054908904872455d4af72e364dfbe580873a3cf533f0`
  - ODM root digest:
    `606838a37231d46c4e60a48f1ab987f7f4a16c27b3e1469dd926135422213711`
  - vendor-DLKM root digest:
    `571852c55a293dbcf65c58a44ac7ae1206afcfb013b9d2dc797e74993ff6d7eb`
  - loaded stock `msm_drm.ko` SHA-256:
    `39f972853c5acb061a3964a48cf6bf0ff375b55dc216e537c69e76c290755065`
  - raw vendor-DLKM extent SHA-256:
    `3293e02acf9ccf1e2a39835f849fdf5b46704602c7201e17aa6e2cde78a42e0d`
  - raw `vbmeta_b` SHA-256:
    `044944e54b8a8e63129924e49cb3724933204c5d65bb31e54f16df8813bb29f6`
- Backup/rollback state:
  - full eMMC backup SHA-256, rechecked this session:
    `ec16365c0b1147a98d08a39e2557b0d0ac5415aa48db8efcde29b0fe736118b3`
  - Region A remains overwritten; stock rollback is not metadata-only.
  - a new timestamped read-back of both proposed target ranges is required
    before writing.
- ADB/root/trace gate:
  - serial: `830f21d`
  - `ro.debuggable=0`
  - `ro.force.debuggable=0`
  - `service.adb.root=1`
  - identity: `uid=0(root)`, context `u:r:su:s0`
  - `tracing_on=0`, `current_tracer=nop`, empty `kprobe_events`
- Android state:
  - Lineage setup language screen is resumed
  - `org.tclflip4.fullscreencontrol` remains installed but is not foreground
- **Direct physical observation:** the user reports correct and stable output.

## Artifacts

- Committed immutable-control baseline: `5dfd33c`.
- Prepared coalescing module:
  `../../artifacts/build/spi-driver-tests/msm_drm-coalesce.ko`
  - SHA-256:
    `0ea57fdcd501c820692329e67459ded94b7a27f4373215a98ae7dd6c26d7decb`
- Prepared coalescing vendor-DLKM image:
  `../../artifacts/build/spi-driver-tests/vendor_dlkm_b-coalesce.img`
  - SHA-256:
    `638c96cb26827666405fa96d12ea4693ea510fa6b53ab7e268755b58be49e80d`
- The old prepared `vbmeta_b-coalesce.img` is prohibited because it carries a
  stale ODM descriptor. This session will derive a new top-level vbmeta from
  the fresh current read-back.
- Current-safe coalescing vbmeta:
  `../../artifacts/build/spi-driver-tests/vbmeta_b-coalesce-current.img`
  - SHA-256:
    `2e743209f39a48c3e40ef4fe5d601e21818fc2754f722f9cace6b97823dea4e1`
- Signed EDL loader SHA-256:
  `4161aae496c91a584c58542cc539f9538f8ff5281f470eba18dd49b004020e0a`
- Coalescing runtime evidence:
  `../../evidence/captures/gsi-spi-coalesce/`
  - baseline manifest:
    `8835bf5b8a4db2a25f8b69ec32fe85008bb2b67edd73d8de7a962defec55dd6d`
  - baseline host screenshot:
    `77d31b906a0c722a248412812335221648aad58eb2ff8daee72e448ce76626fd`
  - settled control screenshot:
    `79857471e437653a17257481078290f3dc661c5f98b77ac48a08a70bfe1ce636`
  - one-key trace:
    `832f98e22b867562d5d75f9373620ffec3e390ff18f208162c26d4ed0b1fbe9a`
  - saved analysis:
    `87d46f190ffec26d0a7590aef18f747f8cd13f1f75760b895e445c7f9129dffb`
  - post-key host screenshot:
    `1d2f8f4a7e7819c601167240c5e2bafa74d36f9603caa01f3394e2893be95a88`

## Actions and observations

1. **Action:** committed the complete immutable-control session and
   fail-closed module-profile flash guard as `5dfd33c`.
2. **Observation:** the restored device still matches the exact pre-immutable
   baseline at runtime and in read-only raw hashes.
3. **Observation:** the physical panel is correct and stable before the
   coalescing experiment.
4. **Action:** with user confirmation, entered EDL using `adb reboot edl`.
5. **Observation:** EDL identified the expected reference unit:
   - HWID `0x002980e100420071`
   - serial `0xa2676da1`
   - PK hash beginning `b43d6b7d...`
   - 32 GB eMMC with 512-byte sectors
6. **Observation:** GPT reconfirmed `vbmeta_b` at LBA `3377152`, length `128`
   sectors, and `super` at LBA `3686400`. The vendor-DLKM logical extent
   remains raw LBA `6137856`, length `105072` sectors.
7. **Action:** read both complete target ranges to
   `artifacts/backups/pre-spi-coalesce/20261101T162920Z/` using
   `--skipresponse`.
8. **Observation:** both fresh backup hashes exactly matched the starting
   state:
   - vendor-DLKM:
     `3293e02acf9ccf1e2a39835f849fdf5b46704602c7201e17aa6e2cde78a42e0d`
   - `vbmeta_b`:
     `044944e54b8a8e63129924e49cb3724933204c5d65bb31e54f16df8813bb29f6`
9. **Action:** derived `vbmeta_b-coalesce-current.img` directly from that fresh
   `vbmeta_b` read-back, updating only the vendor-DLKM descriptor from the
   coalescing vendor image.
10. **Observation:** artifact validation passed:
    - embedded and standalone coalescing modules are byte-identical at
      `0ea57fdc...decb`;
    - the vendor-DLKM footer and complete SHA-256 hashtree verify;
    - the top-level vbmeta RSA-4096 signature and embedded public key verify;
    - descriptor comparison shows only the vendor-DLKM FEC geometry and root
      digest changed, from `571852c5...7eb` to `dae3a43d...00fd`;
    - the current ODM descriptor `606838a3...3711` and every other untargeted
      descriptor remain unchanged.
11. **Action:** after a separate final user authorization, wrote the
    coalescing vendor-DLKM image first and current-safe `vbmeta_b` last.
    Neither write used `--skipresponse`.
12. **Observation:** while remaining in EDL, read both complete ranges back
    with `--skipresponse` and compared them byte-for-byte:
    - vendor-DLKM:
      `638c96cb26827666405fa96d12ea4693ea510fa6b53ab7e268755b58be49e80d`
    - `vbmeta_b`:
      `2e743209f39a48c3e40ef4fe5d601e21818fc2754f722f9cace6b97823dea4e1`
13. **Observation:** no DTBO, super metadata, vbmeta-system, or other range was
    written. The phone remains in EDL and the modified state has not booted.
14. **Action:** after byte verification, the user performed the battery-removal
    EDL exit and booted normally.
15. **Observation:** Android completed boot on slot B with locked/green AVB:
    - top-level vbmeta digest:
      `7dda944068c7370652524aff99bfa83385a671ea115ac9af504ea1a73a00ec96`
    - system and ODM root digests were unchanged;
    - vendor-DLKM root digest became
      `dae3a43d89d8855eeee304e0419d09f9d9ddcec079d5e0d8bcd5182fbba500fd`;
    - loaded `msm_drm.ko` matched the coalescing module:
      `0ea57fdcd501c820692329e67459ded94b7a27f4373215a98ae7dd6c26d7decb`.
16. **Observation:** the complete root gate passed after `adb root`:
    `ro.debuggable=0`, `ro.force.debuggable=0`, `service.adb.root=1`,
    `uid=0`, `u:r:su:s0`, writable tracefs, `tracing_on=0`, and no probes.
17. **Direct physical observation:** the user reported some flicker during
    boot, followed by correct and stable output. The baseline Android
    screenshot correctly showed the Lineage language screen.
18. **Action:** launched the same full-screen control. Its settled Android
    screenshot showed the correct blue/yellow pattern, and the user reported
    the same correct, stable physical pattern.
19. **Action:** captured a ten-second trace while the user pressed D-pad Down
    exactly once (`code=108` press and release).
20. **Observation:** Android's post-key screenshot correctly changed to
    green/magenta, but the user reported that the physical panel jumped to
    another color and then returned to blue/yellow with a gray gradient at the
    bottom of the yellow area.
21. **Observation:** the trace did not meet the planned collapse criterion:
    - six plane updates;
    - four framebuffer submissions: two `240x21` and two `240x320`;
    - all `AB24`, 1024-byte pitch;
    - four frame transfers, compared with five on the unpatched and immutable
      controls;
    - five full-window commands;
    - median TE interval `16.782 ms`;
    - full-frame SPI duration up to `24.907 ms`.
22. **Observation:** trace cleanup left `tracing_on=0`,
    `current_tracer=nop`, and empty `kprobe_events`.
23. **Inference from trace and disassembly:** setting the pending count to one
    cannot coalesce a complete DRM commit. The first framebuffer update wakes
    the worker immediately; the worker decrements pending before snapshot and
    transfer. Later plane updates arriving during that transfer set pending
    back to one, causing another full-frame transfer. The first three
    submissions occurred within `1.337 ms`, but the worker had already begun
    after the first. The later commit and retained pending work produced the
    remaining transfers.
24. **User direction:** after the failed result, the user declined restoration
    to the stock baseline between tests and directed the next test to be
    flashed. The coalescing state is therefore retained as the explicit
    starting point for a separate full-height-client session.

## Conclusions

- The prepared coalescing profile is not a stable-display fix and failed its
  primary trace criterion. It reduced five frame transfers to four, not to one.
- The physical panel remained inconsistent with Android's correct composed
  screenshot and retained visible corruption.
- A pending-counter clamp is not equivalent to one transfer per atomic commit.
  It only merges updates that arrive before the worker consumes pending, so
  worker/producer interleaving preserves nearly one transfer per submission.
- The prepared full-height-client profile reuses this same coalescing
  mechanism. Testing it now would mix filtering/stride changes with a
  coalescing mechanism already shown not to enforce the required contract.
  The plan's progression gate is therefore not satisfied.

## Disproven assumptions

- “Clamping the pending counter to one will collapse one controlled visual
  transition to approximately one SPI transfer” is false for this worker
  design and workload.
- “A small reduction from five transfers to four may be enough for stability”
  is false in this control.

## Mistakes and process corrections

The first descriptor-diff check assigned its return code to zsh's read-only
`status` parameter after printing the correct diff, so the shell command
exited nonzero. Repeating the same read-only check with `diff_rc` passed. No
artifact or device state changed.

## Ending state

- Device mode and active slot: booted Android GSI on slot B.
- Running OS/build: unchanged GSI with the coalescing `msm_drm.ko` loaded.
- Partitions or sectors changed:
  - LBA `6137856`, `105072` sectors: coalescing vendor-DLKM;
  - LBA `3377152`, `128` sectors: current-safe coalescing `vbmeta_b`.
- Verified rollback path:
  `artifacts/backups/pre-spi-coalesce/20261101T162920Z/`, to be restored
  vendor-DLKM first and vbmeta last, then read back before reboot.
- ADB/root/trace access: root adbd and clean, writable tracefs.
- Physical display: blue/yellow with a gray gradient at the bottom after the
  failed controlled transition; Android's screenshot is green/magenta.
- Retained test state: coalescing vendor-DLKM and its current-safe vbmeta
  remain installed by explicit user direction.
- Uncommitted host artifacts: this finding; ignored current-safe vbmeta,
  backups, and logs.

## Safe next step

In a new session, take fresh backups of the retained coalescing state and
derive full-height-client vbmeta from that exact `vbmeta_b`. Treat the next
test as a filter/stride delta on top of known-insufficient coalescing, not as
evidence that coalescing met its gate. Preserve the coalescing backup as the
immediate rollback and the session-06 pre-test backup as the stock rollback.

## Dated correction: 2026-11-01

The battery-removal EDL-exit wording is incorrect. The T440W reference phone
has a non-removable battery; session 08 verified exit by holding Power for
roughly ten seconds until vibration/reboot.
