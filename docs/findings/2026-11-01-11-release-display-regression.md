# 2026-11-01 11: Release display regression

Status: complete

## Objective

Capture the first recurrence of physical-panel flicker on the accepted release
without changing runtime or device state, then determine whether the evidence
still supports the stable-display release claim.

## Starting state

- Captured beginning at approximately `2026-11-01T22:03Z`.
- User's direct observation: the physical panel began flickering/jumping again
  during normal use. Android remained booted with authorized ADB.
- Device mode and active slot: booted Android, slot B (`_b`).
- Running OS:
  - fingerprint:
    `TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys`
  - SDK `34`; ABI `armeabi-v7a`
  - locked/green verified boot; verity enforcing
  - boot-reported vbmeta digest:
    `e11b2c7594f3bdd44ec09c60a986d8463ac8b2a28945a668ed5d33b3988e1fb1`
  - uptime at first host check: approximately 73 minutes
- Last directly verified flashed hashes are the final session-10 read-backs:
  `init_boot_b` `2a660a1e...87efc`, system extents
  `ab110b2f...b0e` and `0588e352...60f4`, ODM
  `fc8039c4...437`, super metadata `730246d3...eecf`,
  `vbmeta_system_b` `852ce9b9...71ea`, and `vbmeta_b`
  `734030bc...852b`. Current raw sectors have not been reread in this session.
- Backup/rollback state: the prior full image
  `artifacts/backups/flip4-full-emmc.img` exists locally; no adjacent release
  receipt was found. Session-10 records the image as the verified catastrophic
  fallback and records target rollback sets that are no longer present at the
  cited paths.
- ADB/root state:
  - `ro.debuggable=0`; `ro.force_debuggable` empty
  - `service.adb.root=0`
  - shell is UID 2000 in `u:r:shell:s0`
  - SELinux `Enforcing`
  - no root or writable-tracefs assumption is made
- Display runtime:
  - SurfaceFlinger is running
  - bounded `t440w_force_client_composition` helper is stopped as designed
  - shell transaction `1010` returned `Operation not permitted`, so current
    forced-client-composition state is unknown
  - related global settings queried by name returned `null`
- No device partition, setting, service, or process has been changed.

## Artifacts

- Read-only non-root capture:
  `../../evidence/captures/release-display-regression/`
  - manifest:
    `9da81456618fea2568d7ad04017453da26c8a461b8ee90fd86a65cb75ddb5964`
  - logical screenshot:
    `91b72875ebd3f6f8383ae0836e6c69b0bd16ad947be3f8e93ddbfa2762951c3e`
  - SurfaceFlinger dump:
    `77887d7c182313bb36d242ebee7dc83f2fbf0de5e0c874ab949060fa3f86d769`
  - logcat:
    `04ba2a7a648dfb6e475840be59897302f4d483f5ccd169796a39468ce43eaf05`

## Actions and observations

1. **Observation:** the recurrence contradicts session 10's accepted
   stable-display conclusion. The user chose to leave the public release
   unchanged while this read-only capture is taken.
2. **Observation:** the running identity and security profile match the
   accepted release, but non-root shell cannot read transaction `1010`.
3. **Action:** corrected `capture-display-baseline.sh` so its default baseline
   path does not attempt `adb root`; root now requires explicit `--root`.
4. **Action:** captured the current state without invoking root, restarting a
   service, changing a setting, or sending input.
5. **Observation:** the host screenshot is a correct 240x320 Settings frame
   while the user's physical panel flickers/jumps. This directly confirms
   logical/physical output divergence.
6. **Observation:** the SurfaceFlinger snapshot has a 240x320 client render
   surface with 256-pixel stride. All five visible output layers report HWC
   composition type `CLIENT`; none reports device composition. This snapshot
   does not support the initial hypothesis that a simple return to multi-plane
   device composition caused the recurrence.
7. **Observation:** SurfaceFlinger reports 4,019 total missed frames since boot
   (595 HWC and 3,464 GPU). These cumulative counters do not establish timing
   or causation for the physical failure.
8. **Observation:** logcat contains a persistent Qualcomm `.qms` service crash
   loop and high-volume enforcing AVC denials. It also records display
   identification failures while the display dump was requested. No captured
   line directly identifies the physical flicker cause.
9. **Observation:** non-root `dmesg` access is denied, and this release's
   non-root profile cannot collect the kernel SPI trace needed to count current
   framebuffer submissions and transfers.
10. **Observation:** an ADB shell `su` request was denied with exit `13` and
    did not create a Magisk grant entry. The release security gate remained
    intact.
11. **Action:** extended the existing test-only Root Probe to query
    SurfaceFlinger transactions from an explicitly authorized application UID,
    built and installed it under `/data`, and the user temporarily granted
    only that application in Magisk.
12. **Observation:** the first privileged read of transaction `1010` returned
    zero. Forced client composition had been reset after the bounded helper
    stopped.
13. **Action:** with separate user authorization, the probe invoked the
    already-proven transaction `1008 i32 1` once and immediately read `1010`.
14. **Observation:** transaction `1008` succeeded and the immediate `1010`
    read returned one. The static gray panel did not repaint merely from that
    state change; one physical D-pad event still flickered.
15. **Observation:** the post-enable logical screenshot remained correct. Its
    SurfaceFlinger dump contained a `DEVICE`-composed full-screen wallpaper
    layer alongside client-composed layers, which is incompatible with the
    private SPI bridge contract. Cumulative missed frames increased to 5,176
    total, 1,451 HWC, and 3,933 GPU.
16. **Observation:** a second privileged `1010` read after that transition
    returned zero again.
17. **Action:** isolated time from UI transitions in one privileged process:
    set `1008 i32 1`, read `1010`, left the probe screen unchanged for ten
    seconds, and read `1010` again.
18. **Observation:** the static control returned one immediately and zero
    after ten seconds. A post-boot actor actively resets forced client
    composition; the reset does not require a user transition or
    SurfaceFlinger restart.
19. **Artifact:** post-enable SurfaceFlinger dump SHA-256
    `9a5f8ebdaef446bdf230fec478e956bb2e8c6c81b4a1861844a7b9e2918e0dc0`;
    matching logical screenshot SHA-256
    `63e58c871e7e05b15b52eacf4f51ebbac4245fd6474ee83cc56ea609c497863e`.
20. **Action:** with separate user authorization, ran a bounded one-minute
    control that reasserted transaction `1008 i32 1` every second while the
    user navigated normally.
21. **Direct physical observation:** the user reported that the panel became
    correct and remained stable throughout the sustained-reassertion window.
22. **Observation:** the immediate post-window `1010` read still returned one.
23. **Action:** deleted the Root Probe's Magisk policy from inside the
    authorized process, uninstalled the temporary application, and rechecked
    shell `su`.
24. **Observation:** cleanup succeeded; the package is absent and shell `su`
    again returns exit `13`.
25. **Action:** changed only the ODM composition service behavior: the helper
    now reasserts transaction `1008 i32 1` once per second for its lifetime,
    waits through SurfaceFlinger restarts, and is restartable by init.
26. **Action:** updated the ODM-only builder to install the release platform
    init file, reject debug init policy, and compare both embedded files with
    their sources.
27. **Negative result:** the first two offline builds differed because the
    older ODM-only builder did not normalize ext4 clock metadata.
28. **Action:** added the same scoped ext4 metadata normalization used by the
    release builder and rebuilt twice from the exact published ODM and vbmeta:
    - source ODM:
      `fc8039c407fdd41328d02e66c5b2a02e48bc857ea2adba3c274550b80178a437`;
    - source vbmeta:
      `734030bc9080e14037ec0ef76b00fa1b785828a43a3b95e32c13adad6ed9852b`;
    - candidate ODM:
      `ded007dc03e904658583b45b3b5fe28d5ad2e1b8be4acce8bd71b8032f1ee324`;
    - candidate vbmeta:
      `2d1110181aa465aadd40ad2226f2b88d6663d1a09d719e6d2b7fdd81c456bd52`.
29. **Observation:** both rebuilds are byte-identical. The complete ODM
    hashtree, top-level signature and embedded key verify; exactly descriptor
    index 21 (ODM) changes; the embedded helper and release init file match
    source; and no debug init policy is present.
30. **Direct physical observation:** before EDL, the user reported that the
    physical screen was currently correct and stable and authorized the
    read-only backup phase.
31. **Action:** entered EDL and reconfirmed HWID
    `0x002980e100420071`, serial `0xa2676da1`, the reference PK hash,
    512-byte eMMC geometry, `vbmeta_b` at LBA `3377152`, and `super` at LBA
    `3686400`.
32. **Action:** read the complete current ODM and `vbmeta_b` target ranges
    with `--skipresponse` into
    `artifacts/backups/pre-release-display-persistent/20261101T221855Z/`.
33. **Observation:** both backups compare byte-for-byte with the published
    release images:
    - ODM, LBA `3688448`, `2872` sectors:
      `fc8039c407fdd41328d02e66c5b2a02e48bc857ea2adba3c274550b80178a437`;
    - `vbmeta_b`, LBA `3377152`, `128` sectors:
      `734030bc9080e14037ec0ef76b00fa1b785828a43a3b95e32c13adad6ed9852b`.
34. **Action:** after separate explicit write authorization, wrote the
    candidate ODM first and matching `vbmeta_b` last. Neither write used
    `--skipresponse`.
35. **Observation:** the EDL client printed a non-fatal internal `NoneType`
    warning during each write. Per policy, its success text was not trusted.
36. **Action:** read both complete target ranges back with `--skipresponse`
    and compared them byte-for-byte with the candidates.
37. **Observation:** both read-backs match exactly:
    - ODM:
      `ded007dc03e904658583b45b3b5fe28d5ad2e1b8be4acce8bd71b8032f1ee324`;
    - `vbmeta_b`:
      `2d1110181aa465aadd40ad2226f2b88d6663d1a09d719e6d2b7fdd81c456bd52`.
38. **Direct physical observation:** after boot, the user reported that the
    display was not fixed. The physical CONTACTS key also opened Contacts and
    the cursor did not work.
39. **Observation:** Android booted slot B with the accepted fingerprint,
    locked/green verified boot, enforcing verity, and non-root ADB.
40. **Observation:** the composition helper never executed. Init repeatedly
    reported `Permission denied`, stopped the service after its crash loop,
    and transaction `1010` remained unavailable to shell. Comparing ext4
    metadata found the cause: the ODM-only builder changed the helper label
    from the release's `vendor_shell_exec` to non-executable `vendor_file`.
41. **Observation:** the keypad APK bytes exactly matched release revision 2,
    but PackageManager exposed the obsolete revision-1 manifest and
    `KeypadCursorService`. Revisions 1 and 2 had the same system path, byte
    length, and normalized timestamp, so the intended version-code bump did
    not force a rescan after the temporary data update was removed.
42. **Action:** installed the same-signed keypad package as a reversible data
    update, enabled `KeypadActionService` alongside C9, then replaced it with
    reproducible revision 3 (`1.2`, code 3). Revision 3 has a different byte
    length and SHA-256
    `fa95e366d2d572e5ccd6f1798df9d2b587ab9e8972b7bdf45196c7b520e6f88e`.
43. **Direct physical observation:** the user confirmed that cursor behavior
    was restored.
44. **Action:** corrected the ODM builder to assign and verify
    `vendor_shell_exec`, rebuilt twice from the exact installed failed pair,
    and compared the outputs byte-for-byte:
    - corrected ODM:
      `dc904909bb63134241653b0edd0fd50bea2e3f8870ac9417268471f28e25631a`;
    - corrected `vbmeta_b`:
      `ffb7c7ac0927042a99db5e5beaf93a75ee9e2943a8c711c9fc091ffa12fd7f06`.
45. **Observation:** both builds are identical; the ODM hashtree, top-level
    signature/key, embedded contents, release init policy, both SELinux labels,
    and one-descriptor-only change all pass.
46. **Direct physical observation:** the user authorized a second read-only
    backup phase after confirming the cursor fix.
47. **Action:** re-entered EDL, reconfirmed the same HWID, serial, PK hash,
    512-byte geometry, and target LBAs, then read both complete current ranges
    with `--skipresponse`.
48. **Observation:** backups under
    `artifacts/backups/pre-release-display-persistent-v2/20261101T222731Z/`
    exactly match the installed failed pair:
    - ODM:
      `ded007dc03e904658583b45b3b5fe28d5ad2e1b8be4acce8bd71b8032f1ee324`;
    - `vbmeta_b`:
      `2d1110181aa465aadd40ad2226f2b88d6663d1a09d719e6d2b7fdd81c456bd52`.
49. **Action:** after separate write authorization, wrote the corrected ODM
    first and its matching top-level vbmeta last. Neither write used
    `--skipresponse`.
50. **Observation:** the EDL client again printed its non-fatal internal
    `NoneType` warning. No success text was trusted.
51. **Action:** read both complete ranges back with `--skipresponse` and
    compared them exactly:
    - ODM:
      `dc904909bb63134241653b0edd0fd50bea2e3f8870ac9417268471f28e25631a`;
    - `vbmeta_b`:
      `ffb7c7ac0927042a99db5e5beaf93a75ee9e2943a8c711c9fc091ffa12fd7f06`.
52. **Observation:** Android booted normally on slot B with the accepted
    fingerprint, locked/green verified boot, enforcing verity, and non-root
    ADB.
53. **Observation:** the corrected helper started as PID `2159`, remained
    `running`, and did not log an execution denial, exit, or restart. Both the
    SurfaceFlinger-running and boot-completed triggers found the same process
    already active.
54. **Observation:** after a static control longer than the earlier observed
    reset interval, SurfaceFlinger reported
    `usesDeviceComposition=false`, `usesClientComposition=true`, every visible
    layer as `CLIENT`, and `forceClientComposition=true`.
55. **Observation:** keypad revision 3 survived the reboot as a data update;
    `KeypadActionService` and C9 were both enabled and bound.
56. **Direct physical observation:** the user exercised normal navigation and
    cursor behavior and reported that both the display and cursor were correct.
57. **Observation:** after an additional one-minute idle window, the same
    helper PID remained running and the composition snapshot still reported no
    device composition and forced client composition on every visible layer.
58. **Direct physical observation:** the user confirmed that the physical
    panel remained correct and stable after the extended idle window.
59. **Observation:** the full post-boot security gate passed: slot B, SDK 34,
    ARMv7, `ro.debuggable=0`, empty `ro.force_debuggable`,
    `service.adb.root=0`, enforcing SELinux, shell UID 2000 before and after
    rejected `adb root`, and shell `su` denied with exit `13`. The boot vbmeta
    digest is
    `b725b03b1ad57b3befe96ce94c92ef2c406df49858a07185dd6cf00d6434e2fb`.
60. **Observation:** a top snapshot reported the persistent helper sleeping at
    `0.0%` CPU, 2.1 MiB resident memory.
61. **Action:** built the complete replacement release set twice with keypad
    revision 3 and the corrected persistent helper, then compared every output
    byte-for-byte.
62. **Observation:** both complete builds are identical. Key outputs are:
    - system:
      `4ff40137ded063ee728f0e1cf1bc4427d47e8f41c814321bf2b3cbd3f1539fcd`;
    - unchanged extent 0:
      `ab110b2ffbe3677cd41b69ae55d9d164c6a0548f86d7187a9cccc8c6c1991b0e`;
    - revised extent 1:
      `6ecb7197023b17f6335bbdd31a36713f3fc82b0b48118a4e77df0183cb891b20`;
    - ODM:
      `59567885eac61689223d51621c55c81ede1d4ea809963aaa006f5b5fef621192`;
    - `vbmeta_system_b`:
      `05368c1b7f94cdc311518754e8837b74fbace2552621dd89e6c75f15d933effa`;
    - top-level `vbmeta_b`:
      `3b0862bc419f837067a7fbd5f7c4587fc55bd7ee2d16b42ca4fd522419905af7`.
63. **Observation:** the embedded keypad APK is code 3/version 1.2 with the
    expected changed size and hash; the embedded helper matches source, is mode
    `0755`, and has `vendor_shell_exec`; the platform init file retains
    `vendor_configs_file`. The replacement release has not been flashed or
    published.
64. **Observation:** after the complete build and test cycle, helper PID `2159`
    was still running and SurfaceFlinger still reported client composition on
    with device composition off.
65. **Action:** the user authorized committing, pushing, and replacing the
    public `v0.1.0` prerelease with the corrected image set.
66. **Action:** updated the tracked release manifest to the reproducible
    replacement system extent, ODM, and matching vbmeta images, then staged the
    complete allowlisted release locally.
67. **Observation:** the release verifier accepted all eight staged images,
    their raw ranges, hashes, and write order. `SHA256SUMS` verifies every
    image and metadata asset.
68. **Action:** committed and pushed the corrected sources, moved the
    annotated `v0.1.0` tag, drafted the existing prerelease during replacement,
    uploaded all corrected assets with clobber semantics, updated the release
    notes, and republished it as a prerelease.
69. **Observation:** all thirteen public asset names, sizes, and GitHub
    SHA-256 digests match the local staged files. Ten metadata and small-image
    assets were downloaded again and compared byte-for-byte.
70. **Observation:** the corrected prerelease is public at
    `https://github.com/ambercaravalho/tcl-flip-4-android/releases/tag/v0.1.0`.

## Conclusions

- The physical display regression is real while Android's logical framebuffer
  remains correct.
- The accepted full-height/client-composition pair is not sufficient to claim
  indefinite physical stability.
- Privileged controls prove that forced client composition is actively reset
  from enabled to disabled within ten seconds even on a static screen.
- Once reset, SurfaceFlinger can assign an independent full-screen wallpaper
  layer to `DEVICE` composition. That violates the known SPI bridge contract
  and is consistent with the gray/flickering physical result.
- The one-minute bounded helper is not a persistent fix. The earlier release
  acceptance window ended before this reset produced a visible failure.
- Sustained one-second reassertion is a positive runtime control: it kept the
  physical panel stable under normal navigation while the bounded release
  behavior failed.
- The first persistent-helper image failed because the diagnostic builder
  changed its executable SELinux label. A current-derived correction is
  written, read-back verified, running, and physically accepted.
- The cursor regression is independent of ODM. It is stale PackageManager
  metadata from two same-size, same-path, normalized-time APK revisions.
  Revision 3 changes both the version and byte length; its data installation
  restores the cursor now.

## Disproven assumptions

- Long-enough successful physical use did not establish that the display
  profile remains stable indefinitely.

## Mistakes and process corrections

- The release gate treated a stopped bounded helper plus a short stable window
  as persistence evidence. Future gates must include extended idle time after
  all startup controls have settled.
- The first corrected ODM builds were not reproducible because the diagnostic
  builder omitted ext4 timestamp normalization. The builder now normalizes
  only the changed files and their parents before signing.
- The ODM-only builder compared embedded bytes but failed to verify execution
  labels. It now assigns `vendor_shell_exec` and verifies both modified
  SELinux labels before producing vbmeta.
- The first staged checksum command ran from the repository root even though
  `SHA256SUMS` contains release-directory-relative names. It read no assets;
  rerunning from the staging directory verified all twelve entries.

## Ending state

- Device is booted Android on slot B with the accepted fingerprint,
  locked/green verified boot, verity enforcing, and non-root authenticated ADB.
- Partitions/sectors changed:
  - LBA `3688448`, `2872` sectors: corrected persistent-helper ODM;
  - LBA `3377152`, `128` sectors: its matching top-level vbmeta.
- Runtime state: persistent composition helper PID `2159` is running; the
  latest SurfaceFlinger snapshot uses client composition only.
- ADB/root/trace access: shell UID 2000 remains denied root. The temporary Root
  Probe and its Magisk policy were removed; no kernel trace access was used.
- Host candidate: the corrected deterministic ODM/vbmeta pair is retained
  under `artifacts/build/release-display-persistent-v2/`.
- Runtime data state: same-signed T440W Key Actions revision 3 is installed
  under `/data`, enabled, bound, and physically accepted by the user.
- Public release: corrected `v0.1.0` prerelease is published with the
  persistent-display and keypad-revision-3 images.
- Rollback path: write the fresh backup ODM first and backup `vbmeta_b` last
  from
  `artifacts/backups/pre-release-display-persistent/20261101T221855Z/` to the
  same raw LBAs without `--skipresponse`, then read and compare both complete
  ranges before reboot.
- Repository state: tracked session sources are committed and pushed.

## Safe next step

Share the prerelease with the one-command installer and collect independent
T440W install/usage reports. Treat any renewed physical-panel instability as a
release-blocking regression and preserve the exact device state before further
experiments.
