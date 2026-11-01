# 2026-11-01 07: SPI full-height client

Status: complete

## Objective

Determine whether rejecting non-320-line planes and forcing the observed
256-pixel client stride makes the controlled full-screen transition stable on
top of the retained, known-insufficient coalescing profile.

This is a filter/stride delta, not evidence that pending-counter coalescing
worked: session 06 still produced four frame transfers for four submissions.

## Starting state

- Captured at `2026-11-01T16:36:18Z`.
- Device mode and active slot: booted Android GSI over ADB, slot B (`_b`).
- Running OS:
  - fingerprint:
    `TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys`
  - system fingerprint: same as runtime fingerprint
  - SDK: `34`
  - ABI: `armeabi-v7a`
  - flavor: `treble_a64_bvN-userdebug`
  - verified-boot state: locked/green
- Retained coalescing identity:
  - top-level vbmeta digest:
    `7dda944068c7370652524aff99bfa83385a671ea115ac9af504ea1a73a00ec96`
  - system root digest:
    `07d1de5bd1fcecf354df054908904872455d4af72e364dfbe580873a3cf533f0`
  - ODM root digest:
    `606838a37231d46c4e60a48f1ab987f7f4a16c27b3e1469dd926135422213711`
  - vendor-DLKM root digest:
    `dae3a43d89d8855eeee304e0419d09f9d9ddcec079d5e0d8bcd5182fbba500fd`
  - loaded coalescing module SHA-256:
    `0ea57fdcd501c820692329e67459ded94b7a27f4373215a98ae7dd6c26d7decb`
  - raw vendor-DLKM extent SHA-256:
    `638c96cb26827666405fa96d12ea4693ea510fa6b53ab7e268755b58be49e80d`
  - raw `vbmeta_b` SHA-256:
    `2e743209f39a48c3e40ef4fe5d601e21818fc2754f722f9cace6b97823dea4e1`
- Backup/rollback state:
  - verified full eMMC backup SHA-256:
    `ec16365c0b1147a98d08a39e2557b0d0ac5415aa48db8efcde29b0fe736118b3`
  - session-06 stock rollback:
    `artifacts/backups/pre-spi-coalesce/20261101T162920Z/`
  - a new backup of the retained coalescing state is mandatory before writing
    the full-height profile.
- ADB/root/trace gate:
  - serial: `830f21d`
  - `ro.debuggable=0`
  - `ro.force.debuggable=0`
  - `service.adb.root=1`
  - identity: `uid=0(root)`, context `u:r:su:s0`
  - `tracing_on=0`, `current_tracer=nop`, empty `kprobe_events`
- Android state: full-screen control is resumed; Android's logical output is
  the green/magenta alternate pattern.
- **Direct physical observation:** after the coalescing key transition, the
  physical panel returned to blue/yellow with a gray gradient at the bottom.

## Artifacts

- Prepared full-height-client module:
  `../../artifacts/build/spi-driver-tests/msm_drm-full-height-client.ko`
  - SHA-256:
    `89febd510f7aa939ce8a20943038f0beab67d1d59a49ce48110dc229b624cf50`
- Prepared full-height-client vendor-DLKM image:
  `../../artifacts/build/spi-driver-tests/vendor_dlkm_b-full-height-client.img`
  - SHA-256:
    `ac2f2a35dc3e21f38ba51f8e8076812cbddea7b31ef7959f2d929f94b5bba116`
- The old prepared full-height vbmeta is prohibited. This session will derive
  a new vbmeta from a fresh read-back of the retained coalescing state.
- Current-safe full-height-client vbmeta:
  `../../artifacts/build/spi-driver-tests/vbmeta_b-full-height-client-current.img`
  - SHA-256:
    `39ee8bd27281a52a1c28f80f2189e0b1a980f8bfa903ce16201ab94a5ccec834`
- Signed EDL loader SHA-256:
  `4161aae496c91a584c58542cc539f9538f8ff5281f470eba18dd49b004020e0a`
- Runtime evidence:
  `../../evidence/captures/gsi-spi-full-height/`
  - post-boot baseline manifest:
    `b63b9c5813371a86a8b41dcb38d83731306eaa7c34056f7fbd108012324eb466`
  - default-composition one-key trace:
    `d0564b5b92870e9c2840f4f4f6ed7b161a86563fadac2427cddd78db2134e347`
  - forced-client static screenshot:
    `88439bf85213760e897eefb7cb5e8a9b9c86c3a01b1aa555794e9b7c908a4d48`
  - forced-client one-key trace:
    `c6b7c01d1c1b57adde9aaf2adb7dbd014794130ad7c339067ea286a124e63332`
  - forced-client post-key screenshot:
    `c19407f75d57edc389a899e88815df7095d0132ea2144f4fb9699e4781ce2549`
  - Lineage-welcome redraw trace:
    `50a2c5877ed83ea9f6c08346179d4782a1bede3f90ea79a7244fe9f291ecafed`
  - Lineage-welcome screenshot:
    `9b443e402b00f0950c86dc6646548f9390bf37a175355a376a59129332e83ffb`
  - SurfaceFlinger forced-client dump:
    `a4fbd4432fcc47001776dbd6cb78cb84ea4a953eccb73be0b5e322e4320aeba9`
  - final runtime state:
    `d3fd5702f32943ef77eb341cce0004d1ab1b908d9eb8e73e86b04d9e9afae6f7`

## Actions and observations

1. **Observation:** session 06 failed its transfer-collapse and physical-output
   gates.
2. **User direction:** retain the coalescing state and flash the next test
   rather than restore stock between profiles.
3. **Observation:** the exact retained coalescing runtime and raw target hashes
   were rechecked before this session.
4. **Action:** entered EDL using `adb reboot edl`.
5. **Observation:** EDL reconfirmed the reference HWID, serial, PK hash,
   512-byte eMMC geometry, `vbmeta_b` at LBA `3377152`, and `super` at LBA
   `3686400`.
6. **Action:** read both complete current target ranges to
   `artifacts/backups/pre-spi-full-height/20261101T163700Z/` using
   `--skipresponse`.
7. **Observation:** fresh backups exactly matched the retained coalescing
   state:
   - vendor-DLKM:
     `638c96cb26827666405fa96d12ea4693ea510fa6b53ab7e268755b58be49e80d`
   - `vbmeta_b`:
     `2e743209f39a48c3e40ef4fe5d601e21818fc2754f722f9cace6b97823dea4e1`
8. **Action:** derived the full-height-client top-level vbmeta directly from
   that fresh retained-state read-back.
9. **Observation:** artifact validation passed:
   - embedded and standalone modules are byte-identical at
     `89febd51...cf50`;
   - the vendor-DLKM footer and complete SHA-256 hashtree verify;
   - the top-level vbmeta RSA-4096 signature and embedded key verify;
   - descriptor comparison against retained coalescing vbmeta changes only the
     vendor-DLKM root digest, from `dae3a43d...00fd` to
     `baa4df9b...719d`.
10. **Action:** after final user authorization, wrote the full-height-client
    vendor-DLKM first and current-safe `vbmeta_b` last. Neither write used
    `--skipresponse`.
11. **Observation:** read both target ranges back with `--skipresponse` and
    compared them byte-for-byte:
    - vendor-DLKM:
      `ac2f2a35dc3e21f38ba51f8e8076812cbddea7b31ef7959f2d929f94b5bba116`
    - `vbmeta_b`:
      `39ee8bd27281a52a1c28f80f2189e0b1a980f8bfa903ce16201ab94a5ccec834`
12. **Observation:** no DTBO or other range was written. The phone remains in
    EDL and the new state has not booted.
13. **Cross-profile direct observation:** the user reports that the Android
    boot animation has been smooth and without issue across all driver tests.
    This is relevant evidence that at least one real animated Android workload
    can remain stable, but its plane/submission shape has not yet been traced.
14. **Action:** after the verified writes, the user performed the
    battery-removal EDL exit and booted normally.
15. **Observation:** Android completed boot on slot B with locked/green AVB:
    - top-level vbmeta digest:
      `9b9a93699922fd50d9528217ac62bb008bc6dc95ad890d3edb09bab74f781991`;
    - vendor-DLKM root digest:
      `baa4df9bb3dc6d068c34ff4720a23a8c8d861db1046494ad4933a37f9144719d`;
    - loaded `msm_drm.ko`:
      `89febd510f7aa939ce8a20943038f0beab67d1d59a49ce48110dc229b624cf50`.
16. **Observation:** the complete root gate passed:
    `ro.debuggable=0`, `ro.force.debuggable=0`, `service.adb.root=1`,
    `uid=0`, `u:r:su:s0`, writable tracefs, `tracing_on=0`, and no probes.
17. **Direct physical observation:** under Android's default composition, the
    static blue/yellow control showed a large gray shadow. One D-pad event
    briefly produced the correct green/magenta output, then the panel reverted
    to blue/yellow. Android's screenshots remained correct.
18. **Observation:** the default-composition trace still contained four
    framebuffer submissions and four frame transfers. Full-height filtering
    removed the short planes from the bridge but did not make the physical
    transition stable.
19. **Action:** forced all-client composition at runtime with
    `service call SurfaceFlinger 1008 i32 1`. The saved SurfaceFlinger dump
    directly reports `forceClientComposition=true`.
20. **Direct physical observation:** without another driver or partition
    change, the user reported that the physical control output became correct
    and stable and matched Android's green/magenta screenshot.
21. **Action:** captured another ten-second trace while the user pressed
    D-pad Down exactly once.
22. **Observation:** the paired full-height/forced-client trace contained:
    - one `240x320` framebuffer submission from a `256x320`, 1024-byte-pitch
      `AB24` client buffer;
    - one full-window reset and its five command transfers;
    - two completed full-frame transfers;
    - no short-plane submission;
    - median TE interval `16.799 ms`.
23. **Direct physical observation:** the user reported that this transition
    changed correctly and remained stable.
24. **Action:** while forced-client composition remained enabled, traced a
    controlled return from the test app to the paused Lineage welcome screen.
25. **Observation:** `org.lineageos.setupwizard/.WelcomeActivity` resumed.
    Its animated redraw produced 35 framebuffer submissions, every one
    `240x320` from a `256x320`, 1024-byte-pitch `AB24` client buffer. The trace
    recorded 37 frame transfers plus five window commands; the two extra frame
    transfers are boundary/pending work rather than independent short planes.
26. **Direct physical observation:** the user reported that the physical
    Lineage welcome screen was correct and stable.
27. **User direction:** after both the controlled-client and Lineage/SystemUI
    gates passed, the user deliberately retained the full-height vendor-DLKM,
    current-safe vbmeta, and current runtime forced-client state.
28. **Observation:** the final gate remained locked/green on slot B with the
    expected module and vbmeta digest, root adbd, `tracing_on=0`,
    `current_tracer=nop`, and empty `kprobe_events`.

## Conclusions

- Full-height filtering by itself is not a stable-display fix. Under default
  Android composition, the controlled transition still failed physically.
- Full-height filtering paired with forced client composition passed both
  required physical gates. It converts the bridge input from independent
  Android planes to one full-height client target per composed frame.
- The controlled event still caused two full-frame transfers for one
  submission. Exact one-transfer coalescing is therefore not required for the
  observed stability; supplying complete composed frame contents is the
  decisive correction in this profile.
- The working state is only partly persistent. The driver/vbmeta survives a
  reboot, but `service call SurfaceFlinger 1008 i32 1` is a runtime setting and
  must be reapplied after SurfaceFlinger or the phone restarts.

## Disproven assumptions

- Rejecting non-320-line planes and fixing the client stride is sufficient
  under default composition: disproven by the failed default-composition
  control.
- A stable transition requires exactly one full-frame transfer: disproven by
  the correct, stable forced-client transition with two transfers.

## Mistakes and process corrections

None yet.

## Ending state

- Device mode and active slot: booted Android GSI on slot B.
- Running OS/build: unchanged Android 14 GSI with the full-height-client
  `msm_drm.ko` loaded and forced client composition active.
- Partitions or sectors changed this session:
  - LBA `6137856`, `105072` sectors: full-height-client vendor-DLKM;
  - LBA `3377152`, `128` sectors: current-safe full-height-client vbmeta.
- Verified rollback paths:
  - immediate rollback:
    `artifacts/backups/pre-spi-full-height/20261101T163700Z/`;
  - stock rollback remains the session-06 pre-test backup.
- ADB/root/trace access: root adbd and clean, writable tracefs.
- Physical display: Lineage welcome screen is correct and stable by direct
  user observation.
- Runtime-only state: SurfaceFlinger forced-client composition is active and
  will reset on reboot or SurfaceFlinger restart.
- Uncommitted host artifacts: session-06 and session-07 findings; ignored
  evidence, backups, and generated vbmeta.

## Safe next step

In a new session, make forced client composition reproducible at boot without
changing another display variable, then reboot and repeat the controlled
client and Lineage/SystemUI gates. Until then, after any reboot, reapply
`service call SurfaceFlinger 1008 i32 1` before relying on the physical panel.
To abandon this profile, restore both raw ranges from the selected verified
rollback and read them back before reboot.

## Dated correction: 2026-11-01

The battery-removal EDL-exit wording is incorrect. The T440W reference phone
has a non-removable battery; session 08 verified exit by holding Power for
roughly ten seconds until vibration/reboot.
