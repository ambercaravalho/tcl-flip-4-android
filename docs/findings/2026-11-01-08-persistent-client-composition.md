# 2026-11-01 08: Persistent client composition

Status: complete

## Objective

Make the verified full-height/forced-client display configuration survive a
phone or SurfaceFlinger restart. Keep the retained full-height driver unchanged
and treat persistence as the only experimental variable.

## Starting state

- Captured at `2026-11-01T16:50Z`.
- Device mode and active slot: booted Android GSI over ADB, slot B (`_b`).
- Running OS:
  - fingerprint:
    `TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys`
  - system fingerprint: same as runtime fingerprint
  - SDK: `34`
  - ABI: `armeabi-v7a`
  - flavor: `treble_a64_bvN-userdebug`
  - verified-boot state: locked/green
- Retained stable-profile identity:
  - top-level vbmeta digest:
    `9b9a93699922fd50d9528217ac62bb008bc6dc95ad890d3edb09bab74f781991`
  - loaded full-height-client module SHA-256:
    `89febd510f7aa939ce8a20943038f0beab67d1d59a49ce48110dc229b624cf50`
  - raw vendor-DLKM extent SHA-256:
    `ac2f2a35dc3e21f38ba51f8e8076812cbddea7b31ef7959f2d929f94b5bba116`
  - raw `vbmeta_b` SHA-256:
    `39ee8bd27281a52a1c28f80f2189e0b1a980f8bfa903ce16201ab94a5ccec834`
- Backup/rollback state:
  - verified full eMMC backup SHA-256:
    `ec16365c0b1147a98d08a39e2557b0d0ac5415aa48db8efcde29b0fe736118b3`
  - immediate coalescing-state rollback:
    `artifacts/backups/pre-spi-full-height/20261101T163700Z/`
  - stock-driver rollback:
    `artifacts/backups/pre-spi-coalesce/20261101T162920Z/`
- ADB/root/trace gate:
  - serial: `830f21d`
  - `ro.debuggable=0`
  - `ro.force.debuggable=0`
  - `service.adb.root=1`
  - identity: `uid=0(root)`, context `u:r:su:s0`
  - `tracing_on=0`, `current_tracer=nop`, empty `kprobe_events`
- Android state:
  `org.lineageos.setupwizard/.LocaleActivity` is resumed.
- **Direct prior physical observation:** the retained full-height driver with
  runtime forced client composition displayed Lineage Setup correctly and
  stably at the end of session 07.
- Runtime-only composition state is still active:
  SurfaceFlinger reports `forceClientComposition=true`.
- Candidate startup properties `debug.sf.disable_hwc`,
  `persist.sys.sf.disable_hwc`, and `persist.debug.sf.disable_hwc` are all
  unset.

## Artifacts

- Starting-state capture:
  `../../evidence/captures/gsi-spi-persistence/starting-state.txt`
  - SHA-256:
    `6853af6d6cf1f601a359db19bd0ca1b72fd3a468cb80b14fe99a441973a02c6f`
- Booted SurfaceFlinger:
  `/system/bin/surfaceflinger`
  - SHA-256:
    `7a1777748b9f4a2f048e4f5291764395b33a63343b2f1e2258ead5649f856a82`
- Preliminary persistence build:
  `../../artifacts/build/spi-client-composition-persistence/`
  - source ODM SHA-256:
    `621a56d908ff29ef17a7711fef5aa0715cf2bc32d95433cf83636e3f325eda25`
  - source current-safe vbmeta SHA-256:
    `39ee8bd27281a52a1c28f80f2189e0b1a980f8bfa903ce16201ab94a5ccec834`
  - output ODM SHA-256:
    `ffdeb68da60087b06a08d1e037924dfb2726ac868cb5983f93c1b89ad8df36eb`
  - output vbmeta SHA-256:
    `681375af4eba55bda370a521e7b5456efd770855b0d73be3dd2ac241adb62d74`
  - output ODM root digest:
    `f5d2ee2739d8715a9b10b86240a95203eb04e1035af58a8f60a2e4ba15d10106`
  - this preliminary output is not authorized for writing; rebuild from fresh
    same-session raw reads first.
- Fresh current-state backup:
  `../../artifacts/backups/pre-spi-persistence/20261101T165459Z/`
  - ODM SHA-256:
    `621a56d908ff29ef17a7711fef5aa0715cf2bc32d95433cf83636e3f325eda25`
  - `vbmeta_b` SHA-256:
    `39ee8bd27281a52a1c28f80f2189e0b1a980f8bfa903ce16201ab94a5ccec834`
- Current-derived final persistence build:
  `../../artifacts/build/spi-client-composition-persistence-current/`
  - ODM SHA-256:
    `5a5377ab606858d382ad4d4f46ed5f2180f3a2fd3d6d8b4e84129f6656ca21e2`
  - `vbmeta_b` SHA-256:
    `a1de9ab79b6a6a80ddef596ae9c3ca124face9fe3d60b2af7ea3f2bd1455e3c6`
  - ODM root digest:
    `0608bdaee149c52de3aa4e667adebb85d96e0c7ce510fc0cddf8c87a56ec9f5a`
- Fresh first-candidate backup:
  `../../artifacts/backups/pre-spi-persistence-v2/20261101T170010Z/`
  - ODM SHA-256:
    `5a5377ab606858d382ad4d4f46ed5f2180f3a2fd3d6d8b4e84129f6656ca21e2`
  - `vbmeta_b` SHA-256:
    `a1de9ab79b6a6a80ddef596ae9c3ca124face9fe3d60b2af7ea3f2bd1455e3c6`
- Current-derived delayed persistence build:
  `../../artifacts/build/spi-client-composition-persistence-v2-current/`
  - ODM SHA-256:
    `134a1d3a592e2b948516cf57ad096f70dd5c2673854f16dd8d0cb0b14ea3d47e`
  - `vbmeta_b` SHA-256:
    `2fc2aac67c7297a3520900ee699af9b69eb2775d92ffb690acb2cd31d8af2a99`
  - ODM root digest:
    `c12bbbb81d41f322bfac9e7e8682583ecc675f647218397759bcfbfda92b8b02`
- Fresh delayed-candidate backup:
  `../../artifacts/backups/pre-spi-persistence-v3/20261101T170428Z/`
  - ODM SHA-256:
    `134a1d3a592e2b948516cf57ad096f70dd5c2673854f16dd8d0cb0b14ea3d47e`
  - `vbmeta_b` SHA-256:
    `2fc2aac67c7297a3520900ee699af9b69eb2775d92ffb690acb2cd31d8af2a99`
- Current-derived reassertion build:
  `../../artifacts/build/spi-client-composition-persistence-v3-current/`
  - ODM SHA-256:
    `f265523d03d03637741a7423d2aab4776f915fa14f85e18dddc75a97c9cb6fe6`
  - `vbmeta_b` SHA-256:
    `9dfab9fd55ae63b21ee533397c82d2e6d4e582fe3233ffddead6a40fbabf5458`
  - ODM root digest:
    `f9895586eea495d3172b794c5ebcb5f8c28f8341e16df77201de62ab64ddde86`
- Fresh unbounded-candidate backup:
  `../../artifacts/backups/pre-spi-persistence-v4/20261101T171056Z/`
  - ODM SHA-256:
    `f265523d03d03637741a7423d2aab4776f915fa14f85e18dddc75a97c9cb6fe6`
  - `vbmeta_b` SHA-256:
    `9dfab9fd55ae63b21ee533397c82d2e6d4e582fe3233ffddead6a40fbabf5458`
- Current-derived bounded persistence build:
  `../../artifacts/build/spi-client-composition-persistence-v4-current/`
  - ODM SHA-256:
    `f80d0c0b27d2b364050bd8a82dc5dfad7eba7fd8f51a89dcef9c6cd9a6bc2025`
  - `vbmeta_b` SHA-256:
    `779b1c409d5d4124261d5975410db5364c3f47d5e31e4f110f708ab79a864b7a`
  - ODM root digest:
    `7e6feddd3a0faee03749562feefbe4d1bd0634c66ba7576b841ef3619267fb53`
- Final runtime evidence:
  `../../evidence/captures/gsi-spi-persistence/`
  - post-boot state:
    `9ade16a27a9b03bf6d4688a8cf434611d3ae3612fa56e589f76abcae00c0617a`
  - post-SurfaceFlinger-restart state:
    `b5b0071fe508343b9988acc89fa3e9baf92b4eb59c960912d8d41bb6fa60c05e`
  - control static screenshot:
    `712deddd144b0e9f42104e46ed8534361681798c6d8d60967f75f9a6ca67f5bd`
  - one-key trace:
    `8cb8381e1d961a7a3a2c1ff42300c7ad60456d48ee7bc9de966692786d21dcf2`
  - one-key screenshot:
    `1d2f8f4a7e7819c601167240c5e2bafa74d36f9603caa01f3394e2893be95a88`
  - final Lineage Setup screenshot:
    `4e9a94c71bff4ad17441b8c6e259602a07f1e590fa732be9dbc5ca825d717f89`
  - final runtime state:
    `a70891832fdee66b6f608beefcd9cbd65d987de48635d282f36688f537238f0c`

## Actions and observations

1. **Action:** committed and pushed sessions 06 and 07 as `f220628`.
2. **Observation:** the repository was clean and synchronized with
   `origin/main` before opening this session.
3. **Observation:** Android 14 AOSP implements transaction `1008` by assigning
   its argument to `mDebugDisableHWC` and scheduling a repaint.
4. **Observation:** the exact booted SurfaceFlinger binary contains the
   forced-client Binder interface and transaction behavior but does not contain
   `debug.sf.disable_hwc`. The common legacy property is therefore not evidence
   of a working persistence path on this GSI.
5. **Observation:** the built-in Developer option uses the same transaction
   and reads back transaction `1010`; it is runtime state, not a persistent
   setting reapplied at boot.
6. **Action:** added a minimal ODM init service triggered by every
   `init.svc.surfaceflinger=running` transition, with `sys.boot_completed=1`
   as a fallback.
7. **Action:** added a helper that waits up to five seconds for the
   SurfaceFlinger Binder service, then invokes the already-proven transaction
   as the same root/`su` identity used in session 07.
8. **Observation:** running the helper from `/data/local/tmp` returned success,
   and transaction `1010` still reported forced client composition enabled.
9. **Action:** updated the normal GSI preparation pipeline to install the init
   service and executable helper in ODM with explicit modes, ownership, and
   SELinux labels.
10. **Action:** added and ran an ODM-only persistence builder guarded by exact
    source ODM and vbmeta SHA-256 values.
11. **Observation:** offline artifact validation passed:
    - the output ODM has a valid complete hashtree footer and root digest
      `f5d2ee27...0106`;
    - the top-level RSA-4096 signature and embedded key verify;
    - descriptor comparison reports exactly one changed descriptor, ODM;
    - the retained full-height vendor-DLKM root remains
      `baa4df9b...719d`;
    - embedded init/helper contents, modes, ownership, and labels match the
      source files.
12. **Direct physical observation:** immediately before EDL, the user
    reconfirmed that Lineage Setup was physically correct and stable and
    authorized the backup phase.
13. **Action:** entered EDL with `adb reboot edl`.
14. **Observation:** after the expected short USB re-enumeration delay, EDL
    reconfirmed HWID `0x002980e100420071`, serial `0xa2676da1`, the reference
    PK hash, 512-byte eMMC geometry, `vbmeta_b` at LBA `3377152`, and `super`
    at LBA `3686400`.
15. **Action:** read the complete current ODM and `vbmeta_b` target ranges
    with `--skipresponse`.
16. **Observation:** both fresh reads exactly match the retained state and
    their corresponding known host artifacts:
    - ODM:
      `621a56d908ff29ef17a7711fef5aa0715cf2bc32d95433cf83636e3f325eda25`;
    - `vbmeta_b`:
      `39ee8bd27281a52a1c28f80f2189e0b1a980f8bfa903ce16201ab94a5ccec834`.
17. **Action:** rebuilt the final persistence pair directly from those two
    fresh raw reads.
18. **Observation:** final validation passed:
    - complete ODM hashtree verification succeeded;
    - top-level RSA-4096 signature and embedded key verification succeeded;
    - exactly descriptor index 21, ODM, changed;
    - the full-height vendor-DLKM digest remains `baa4df9b...719d`;
    - extracted init and helper files compare byte-for-byte with their sources;
    - output sizes exactly match the `2872`-sector ODM and `128`-sector vbmeta
      ranges.
19. **Action:** after separate final user authorization, wrote the persistent
    ODM first and current-derived `vbmeta_b` last. Neither write used
    `--skipresponse`.
20. **Observation:** read both complete ranges back with `--skipresponse` and
    compared them byte-for-byte:
    - ODM:
      `5a5377ab606858d382ad4d4f46ed5f2180f3a2fd3d6d8b4e84129f6656ca21e2`;
    - `vbmeta_b`:
      `a1de9ab79b6a6a80ddef596ae9c3ca124face9fe3d60b2af7ea3f2bd1455e3c6`.
21. **User correction:** this phone does not have a removable battery. The
    correct EDL exit is to hold Power for roughly ten seconds until vibration
    and reboot.
22. **Observation:** Android booted normally on slot B, locked/green. The
    full-height module remained
    `89febd510f7aa939ce8a20943038f0beab67d1d59a49ce48110dc229b624cf50`,
    and the new top-level vbmeta digest was
    `07e1b9addf52ccd9ade2a3950e736471e21929f349f57e064aacf88e79f0c6f4`.
23. **Observation:** the first persistence attempt failed its only success
    criterion. Transaction `1010` reported forced client composition disabled
    after boot.
24. **Action:** immediately reapplied the known-good runtime transaction, which
    restored transaction `1010` to enabled.
25. **Observation:** init logs show the helper ran on each SurfaceFlinger start
    and again at boot completion. The early invocations raced unavailable
    Binder registration and exited `10`; the boot-completed invocation exited
    `0`, but Android subsequently reset the overlay state to disabled.
26. **Action:** manually restarted the installed init service after boot.
27. **Observation:** the late invocation enabled forced client composition and
    it remained enabled after a ten-second check. The hook identity and command
    are valid; late-boot ordering is the failed variable.
28. **Action:** changed the helper to wait five seconds beyond SurfaceFlinger
    availability, recheck Binder availability, and only then invoke
    transaction `1008`.
29. **Observation:** the revised helper passed a live disable/run/read-back
    control: transaction `1010` changed from disabled to enabled after the
    five-second delay.
30. **Action:** changed the builder to replace an existing helper as well as
    create it on an unmodified ODM, then prepared a preliminary delayed
    candidate from the exact first-candidate images.
31. **Direct physical observation:** the user confirmed that the manually
    restored runtime was physically correct and stable and separately
    authorized the second backup phase.
32. **Action:** re-entered EDL and reconfirmed the same HWID, serial, PK hash,
    slot-B GPT geometry, and target LBAs.
33. **Action:** read the complete installed first-candidate ODM and
    `vbmeta_b` ranges with `--skipresponse`.
34. **Observation:** both fresh reads exactly matched their post-write
    read-backs from the first attempt.
35. **Action:** rebuilt the delayed candidate from those exact fresh reads.
36. **Observation:** delayed-candidate validation passed:
    - complete ODM hashtree verification succeeded;
    - top-level RSA-4096 signature and embedded key verification succeeded;
    - only ODM descriptor index 21 changed;
    - the full-height vendor-DLKM digest remains `baa4df9b...719d`;
    - the extracted 702-byte delayed helper and init file compare byte-for-byte
      with their sources;
    - output sizes exactly match the target ranges.
37. **Action:** after a second independent write authorization, wrote only the
    delayed ODM and its current-derived `vbmeta_b`, then read both complete
    ranges back.
38. **Observation:** both second-candidate read-backs matched byte-for-byte:
    - ODM:
      `134a1d3a592e2b948516cf57ad096f70dd5c2673854f16dd8d0cb0b14ea3d47e`;
    - `vbmeta_b`:
      `2fc2aac67c7297a3520900ee699af9b69eb2775d92ffb690acb2cd31d8af2a99`.
39. **Action:** the user exited EDL with the corrected long-Power-hold
    procedure and booted normally.
40. **Observation:** Android again booted slot B locked/green with unchanged
    full-height module. The top-level vbmeta digest became
    `36f4badcc12669833dfa49981304ed927343e521b63bef02d0b123d1540dd6c0`.
41. **Observation:** the delayed helper ran at boot completion and exited
    successfully after about five seconds, but transaction `1010` was disabled
    after Android settled. The second candidate therefore also failed.
42. **Action:** immediately restored the known-good runtime transaction.
43. **Inference:** a single successful late invocation still does not define
    a reliable final ordering point on this boot.
44. **Action:** revised the helper to reassert transaction `1008` immediately
    and every five seconds for one minute after each SurfaceFlinger start, then
    exit rather than remain as a polling daemon.
45. **Observation:** a live disable/start/read-back control showed the revised
    helper enabled forced client composition on its first iteration. The test
    process was then stopped; full boot behavior remains unverified.
46. **Direct physical observation:** the user again confirmed that the
    manually restored runtime was correct and stable and authorized a third,
    separate backup phase.
47. **Action:** entered EDL, reconfirmed device/GPT identity, and read the
    complete installed delayed-candidate ODM and `vbmeta_b` with
    `--skipresponse`.
48. **Observation:** the fresh reads exactly match the second write's verified
    bytes.
49. **Action:** rebuilt the one-minute reassertion candidate from those exact
    fresh reads.
50. **Observation:** validation again passed the complete ODM hashtree,
    top-level signature/key, one-descriptor-only diff, preserved full-height
    vendor-DLKM digest, embedded-file comparison, and exact-size gates.
51. **Action:** after a third independent authorization, wrote the
    one-minute-reassertion ODM and current-derived `vbmeta_b`, then read both
    complete ranges back.
52. **Observation:** both third-candidate read-backs matched byte-for-byte:
    - ODM:
      `f265523d03d03637741a7423d2aab4776f915fa14f85e18dddc75a97c9cb6fe6`;
    - `vbmeta_b`:
      `9dfab9fd55ae63b21ee533397c82d2e6d4e582fe3233ffddead6a40fbabf5458`.
53. **Observation:** Android booted normally on slot B, locked/green, with
    top-level vbmeta digest
    `78d368ba6b86d72392978c9ea90aa4fd49ceebce7ed36c4e691032c157b082d7`
    and the unchanged full-height module.
54. **Observation:** before `adb root` or any manual transaction, SurfaceFlinger
    reported hardware composition disabled. The persistence mechanism therefore
    passed the boot-time functional gate.
55. **Mistake discovered before completion:** the wait function and outer
    reassertion loop shared `attempt`, so each function call reset the outer
    counter. The installed helper polled every five seconds indefinitely.
56. **Action:** stopped the unintended polling service after the boot window.
57. **Observation:** hardware composition remained disabled ten seconds after
    the service stopped.
58. **Action:** separated `wait_attempt` and `reassert_attempt` in the source,
    then ran the corrected helper from `/data/local/tmp` after explicitly
    enabling hardware composition.
59. **Observation:** the corrected helper immediately disabled hardware
    composition, exited successfully after approximately 60 seconds, and left
    hardware composition disabled after exit. The bounded behavior is now
    validated live but not yet installed in ODM.
60. **Direct physical observation:** with the unbounded service manually
    stopped, the user confirmed the panel remained correct and stable and
    authorized the bounded-helper backup phase.
61. **Action:** entered EDL, reconfirmed device/GPT identity, and read both
    complete current target ranges with `--skipresponse`.
62. **Observation:** the fresh reads exactly match the third candidate's
    verified write bytes.
63. **Action:** rebuilt the bounded candidate from those exact reads.
64. **Observation:** the bounded candidate passed the complete hashtree,
    signature/key, one-descriptor-only diff, retained vendor-DLKM digest,
    887-byte helper extraction/comparison, and exact-size gates.
65. **Action:** after a fourth independent authorization, wrote the bounded
    ODM and current-derived `vbmeta_b`, then read both complete ranges back.
66. **Observation:** both final read-backs matched byte-for-byte:
    - ODM:
      `f80d0c0b27d2b364050bd8a82dc5dfad7eba7fd8f51a89dcef9c6cd9a6bc2025`;
    - `vbmeta_b`:
      `779b1c409d5d4124261d5975410db5364c3f47d5e31e4f110f708ab79a864b7a`.
67. **Observation:** Android booted normally on slot B, locked/green, with
    top-level vbmeta digest
    `362827d0a97d4b386bf10fbcacc5d780d184a1bed76061c7ccad01a7aee8950c`
    and unchanged full-height module.
68. **Observation:** the bounded helper reasserted client composition through
    late initialization, then stopped after its one-minute window.
    SurfaceFlinger transaction `1010` remained enabled afterward.
69. **Direct physical observation:** the user reported the settled Lineage
    display correct and stable after the helper stopped.
70. **Action:** restarted SurfaceFlinger through init. Its PID changed from
    `2798` to `15532`; the init trigger started the bounded helper again.
71. **Observation:** after the restart helper stopped, hardware composition
    remained disabled and tracefs remained clean.
72. **Direct physical observation:** the user reported the Lineage display
    correct and stable after the SurfaceFlinger/framework restart.
73. **Action:** launched the same full-screen control and captured one D-pad
    event under the persistent profile.
74. **Observation:** the trace matched the session-07 stable shape:
    - one `240x320` submission from a `256x320`, 1024-byte-pitch `AB24`
      client target;
    - one window reset with five command transfers;
    - two completed frame transfers;
    - no short-plane submission;
    - clean tracefs after capture.
75. **Direct physical observation:** the user reported both the static control
    and one-key transition correct and stable.
76. **Action:** returned to
    `org.lineageos.setupwizard/.DateTimeActivity`.
77. **Direct physical observation:** the user reported the final Lineage
    date/time screen correct and stable.

## Planned write and rollback set

- Confirm fresh GPT geometry and slot B in EDL.
- Read with `--skipresponse`:
  - ODM at LBA `3688448`, `2872` sectors;
  - `vbmeta_b` at LBA `3377152`, `128` sectors.
- Require the fresh reads to match the recorded current ODM and full-height
  vbmeta exactly, then rebuild from those read-back paths.
- Write without `--skipresponse`, payload first and verification metadata last:
  - persistent-client ODM at LBA `3688448`;
  - freshly derived `vbmeta_b` at LBA `3377152`.
- Read both complete ranges back with `--skipresponse` and compare byte for
  byte before reboot.
- Immediate rollback is the same-session pair, restored ODM first and vbmeta
  last, followed by another complete read-back comparison.
- No system, super metadata, vendor-DLKM, DTBO, or other range is in the write
  set.

## Conclusions

- Forced client composition is now persistent across both a full phone reboot
  and a controlled SurfaceFlinger/framework restart.
- No SurfaceFlinger property supported this behavior on the exact GSI binary.
  A device-specific ODM init service is required.
- One invocation at SurfaceFlinger start, boot completion, or five seconds
  later is not a reliable ordering point. Reasserting every five seconds for
  one minute covers the observed early SurfaceFlinger restart and late
  framework reset; the helper then exits and the state remains active.
- The retained full-height driver is unchanged. Persistence changes only ODM
  and the matching ODM descriptor in top-level vbmeta.
- The persistent profile passed the same controlled full-screen and
  Lineage Setup physical gates as the runtime-only session-07 profile.

## Disproven assumptions

- Setting `debug.sf.disable_hwc=1` is sufficient on this GSI: unsupported by
  the exact booted binary, which does not contain or read that property name.
- Invoking transaction `1008` as soon as SurfaceFlinger or boot completion is
  reported is late enough: false on this boot, where Android reset the state
  after the helper exited successfully.
- Waiting five seconds beyond boot completion is sufficient: false on the
  second boot.

## Mistakes and process corrections

- Earlier findings described the EDL exit as battery removal. The reference
  phone has a non-removable battery; use a roughly ten-second Power hold until
  vibration/reboot.
- The first helper treated Binder registration as the final ordering gate.
  A successful transaction can still be overwritten by later framework
  initialization, so the revised helper deliberately delays and rechecks.
- The first one-minute helper reused one global shell variable for nested
  counters and became an unintended permanent polling loop. Distinct variable
  names are now mandatory, and the corrected helper was observed to exit.

## Ending state

- Device mode and active slot: booted Android GSI on slot B.
- Running OS/build: retained full-height-client profile with bounded persistent
  forced client composition active.
- Partitions or sectors changed:
  - LBA `3688448`, `2872` sectors: bounded-persistence ODM;
  - LBA `3377152`, `128` sectors: matching current-derived `vbmeta_b`.
- No system, super metadata, vendor-DLKM, DTBO, or other range was written.
- Verified rollback paths:
  - immediate pre-final backup:
    `artifacts/backups/pre-spi-persistence-v4/20261101T171056Z/`;
  - original pre-persistence stable profile:
    `artifacts/backups/pre-spi-persistence/20261101T165459Z/`;
  - stock-driver rollback remains
    `artifacts/backups/pre-spi-coalesce/20261101T162920Z/`.
- ADB/root/trace access: root adbd and clean, writable tracefs.
- Physical display: Lineage date/time screen is correct and stable by direct
  user observation.
- Persistence service: stopped normally after its bounded window; hardware
  composition remains disabled.
- Uncommitted host artifacts: this finding, init/helper/tooling changes, and
  ignored build, backup, log, and capture evidence.

## Safe next step

Commit this completed session and update durable documentation. The next device
session can continue Lineage setup while treating the persistent full-height
client-composition pair as the display baseline.
