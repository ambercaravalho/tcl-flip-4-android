# 2026-11-01 10: Rooted release stack

Status: complete

## Objective

Build and validate a single community release candidate with Magisk-managed
application root, authenticated non-root ADB by default, a maintained
third-party cursor, official microG, and Aurora Store while preserving the
validated keypad and stable-display profiles.

## Starting state

- Captured at `2026-11-01T18:17:33Z`.
- Repository commit:
  `b36ddc09f17da5569f2dd7e12806b80d698df407`
  (`Add persistent physical keypad navigation`); the working tree was clean.
- Device mode and active slot: booted Android over ADB on slot B (`_b`).
- Running OS:
  - fingerprint:
    `TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys`
  - system fingerprint: same as the runtime fingerprint
  - SDK: `34`
  - ABI: `armeabi-v7a`
  - verified-boot state: locked/green with verity enforcing
  - top-level vbmeta digest:
    `814b5fe5df5bc29bc761e2dc33957483d0408f38cb04cab1e5e8dfa0e4062689`
- Exact installed image identities from the completed session-09 write and
  read-back:
  - ODM:
    `2e66c8535449f239c180947a592434e452e3a979cfc89f8bf0ebe90433100c89`
  - system:
    `d20e2c86bd2ac4bae24384f9a53ad68f872d5b1cd21a6c2dc5baad534a172112`
  - `vbmeta_system_b`:
    `5bb155cde647c2d275ecdec48587c0e181aab44d9f7b55c4126f5bd39c31b44c`
  - `vbmeta_b`:
    `e909b1735c3b1f1de342933735921124f7beee4fcfabe2ee06051fedaa574a90`
- Current security state:
  - `ro.debuggable=0`
  - `ro.force_debuggable` is empty
  - `ro.adb.secure=0`
  - `service.adb.root=1`
  - global `adb_root=1`
  - ADB identity: `uid=0(root)`, context `u:r:su:s0`
  - `getenforce` reports `Enforcing`, but boot audit records
    `permissive=1` denials; the generated policy retains the bring-up-wide
    permissive map and is not release-enforcing.
- Stable display/keypad state:
  - forced client composition transaction `1010` reports enabled
  - bounded composition and keypad-enablement helpers are stopped normally
  - navigation-bar insets are absent
  - both mainkeys properties are `1`
  - the baked keypad service is enabled and bound with capability `40`
  - baked keypad APK SHA-256:
    `93b3ef7600d2070a59e58bce38835903df6bc456068ac6bd5679b3c087196dc5`
- Capacity:
  - mounted system reports `2,005,820` KiB total and `65,608` KiB available
  - the matching host ext4 superblock reports `67,182,592` free bytes
  - signed system image size: `2,074,083,328` bytes
  - verified two-region super capacity: `2,541,662,208` bytes
- Backup/rollback state:
  - verified full eMMC backup:
    `artifacts/backups/flip4-full-emmc.img`
  - complete pre-keypad profile:
    `artifacts/backups/pre-keypad-profile/20261101T174853Z/`
  - immediate pre-keypad-correction pair:
    `artifacts/backups/pre-keypad-odm-correction/20261101T180015Z/`
  - Region A was overwritten during Lineage testing; metadata-only stock
    rollback is not sufficient.
- Trace state: `tracing_on=0`, `current_tracer=nop`, empty `kprobe_events`.
- Known release blockers:
  - unauthenticated root ADB is enabled
  - the loaded policy contains a broad permissive map
  - public AOSP test keys anchor the accepted AVB chain
  - the system filesystem is too full for current microG releases

## Artifacts

- Planned ignored dependency cache:
  `artifacts/downloads/release-components/`
- Planned ignored release build:
  `artifacts/build/rooted-release/`
- Planned same-session backups:
  `artifacts/backups/pre-rooted-release/<timestamp>/`

## Actions and observations

1. **Observation:** the repository started clean and synchronized at the
   session-09 commit.
2. **Observation:** the device retained the complete final session-09 keypad,
   navigation, and stable-display profile.
3. **Observation:** the running release candidate starts with root adbd and
   authentication disabled. This is distinct from Magisk-style per-application
   authorization and must not be retained.
4. **Observation:** the kernel reports enforcing globally, but AVC records
   include `permissive=1`; the current merged policy is still a bring-up
   policy, not an enforcing release policy.
5. **Observation:** current system free space is approximately 67 MB. Official
   microG Services v0.3.17 is approximately 108 MB before its companion,
   Aurora, Magisk Manager, or a replacement cursor, so an exact-size injection
   cannot succeed. The system filesystem and dynamic-partition mapping must be
   grown within verified super capacity.
6. **Action:** pinned official release sources, commits, artifact sizes,
   SHA-256 values, signer certificates, and licenses in
   `tooling/release-components.json`, then fetched every APK into the ignored
   artifact cache with fail-closed verification.
7. **Observation:** pinned component identities:
   - Magisk `31.1`, source `0972f67d97f9b6302b67c5171283330c74114b4a`,
     APK SHA-256
     `89cefac0a318afa39fb3880c45c87b036c05bc1ebf02a7a715b7f8d7c26ac6e7`;
   - C9 `3.0.4`, source
     `cda4cb7029a1a38c5f980e516c4edd1803bef0d5`, upstream APK SHA-256
     `10bfad9e36de88a68d9b5942419a0b79601092017c37b6c849653c7c0048fc85`;
   - microG Services `0.3.17.252432`, source
     `32bc8954ff872d0e1a05ddfae81561b6dbecef69`, APK SHA-256
     `e5e6cba078bdec812b5450599350e5c1a12c8b7438da5bf77123af170f8c1a35`;
   - microG Companion from the same release, APK SHA-256
     `9b8616011cc8f026bcbbe094df850794abb9d6d9f23214d7a8f8c4d1033ea012`;
   - Aurora Store `4.8.4` official F-Droid build, source
     `ad3d349edce82e119ba239f3a07b3afe028abd19`, APK SHA-256
     `fd9c75d90d0f4a7c132b9b4a5a2cf1992a45e03b8d8ff988b7dcfbc0db2c4d11`.
8. **Observation:** FlipMouse is not redistributable because its repository
   declares no license. C9 is Apache-2.0, current, publishes complete source,
   targets Android 7+, and includes 32-bit ARM native libraries.
9. **Action:** split the required mainkeys/composition init policy into
   `init.t440w.platform.rc`; reduced `init.t440w.debug.rc` to an optional
   authenticated USB fallback; made release-safe USB and enforcing SELinux the
   GSI builder defaults; retained unsafe root ADB and broad permissive policy
   only behind separate explicit options.
10. **Action:** built C9 from the pinned source with a minimal tracked patch:
    internal activation keys disabled, TV control scheme selected, F1/Call
    assigned to vertical scroll, and the T440W action service assigned to
    launch C9's exported standard-cursor toggle for CONTACTS.
11. **Observation:** the first C9 host build passed release lint/R8, APK
    signature verification, and 32-bit ABI inspection. Prototype APK SHA-256:
    `7f6be6f42ae38ee3bc15b00c955788da4628f3e1a45299e1c149d08c82641d83`.
12. **Action:** saved the original accessibility state, installed C9 and a
    same-key `/data` update of the baked keypad package, replaced only the old
    keypad cursor component with the new action component, and enabled C9.
13. **Observation:** both services are enabled and bound. T440W Key Actions
    reports key-filter capability `40`; C9 reports gesture/key-filter
    capability `41`. C9 uses approximately 31 MB PSS while active. Host
    `input keyevent` injection does not traverse the physical accessibility
    key-filter path, so physical keypad and panel acceptance remain mandatory.
14. **Observation:** the user physically exercised C9 with the keypad and
    confirmed that cursor toggle, movement, click, scroll, disable, and
    post-disable keypad behavior all pass and feel good. C9 is the accepted
    release cursor.
15. **Action:** installed pinned microG Services and Companion as reversible
    `/data` prototypes. The microG Self-Check reports signature-spoofing
    support, Services installed, the expected signature, and Companion
    installed.
16. **Action:** installed pinned Aurora Store as a reversible `/data`
    prototype and completed onboarding. The requested package-installer and
    external-storage app-ops are allowed. Anonymous login is not yet tested
    because the phone currently has no validated network/default route.
17. **Action:** installed the pinned Magisk Manager APK on `/data`, read the
    exact current `init_boot_b`, and patched it on the same 32-bit ARM device
    with the official Magisk `boot_patch.sh` and APK payloads. Recreated and
    verified the embedded init-boot AVB hash footer, then updated only the
    `init_boot` hash descriptor in an exact-current `vbmeta_b` and re-signed it
    with the already accepted public AOSP test key.
18. **Observation:** two clean Magisk patch runs were byte-for-byte
    reproducible. Prepared pair:
    - `init_boot_b-magisk.img`:
      `2a660a1eaadfcab823f33fa86bb9ed09cbf099bbcaa902286e6093f02ef87efc`;
    - `vbmeta_b-magisk.img`:
      `db7fb47c124352a03859e8ad16df17d0c37b54f31d40e031fb275800398dab00`.
    The signed top-level vbmeta signature verifies and only descriptor index
    `19` differs from the installed vbmeta.
19. **Observation:** the exact pre-write rollback pair is:
    - `init_boot_b`, 8,388,608 bytes:
      `07965eb937d7165a7b609e732d0b56ce9c43fbdb7d8e2e7f3b0859c1570373ec`;
    - `vbmeta_b`, 65,536 bytes:
      `e909b1735c3b1f1de342933735921124f7beee4fcfabe2ee06051fedaa574a90`.
20. **Planned write set:** after a fresh EDL GPT and backup check, write
    `init_boot_b` first at raw LBA `3350528` for `16384` sectors, then
    `vbmeta_b` at raw LBA `3377152` for `128` sectors. Neither write may use
    `--skipresponse`; both complete ranges must be read with `--skipresponse`
    and compared before reboot.
21. **Rollback set:** write the exact backups from observation 19 to the same
    raw LBAs in the same payload-then-vbmeta order, then read and compare both
    ranges before reboot. The verified full-eMMC backup remains the
    catastrophic fallback.
22. **Observation:** fresh EDL GPT output reconfirmed `init_boot_b` at byte
    offset `0x66400000`, length `0x800000` (LBA `3350528`, `16384` sectors),
    and `vbmeta_b` at `0x67100000`, length `0x10000` (LBA `3377152`, `128`
    sectors). Fresh raw reads matched both rollback hashes in observation 19.
23. **Action:** wrote `init_boot_b-magisk.img` first and
    `vbmeta_b-magisk.img` second using raw `ws` commands without
    `--skipresponse`. Read both full ranges with `--skipresponse`; each
    read-back compared byte-for-byte and matched its prepared hash before
    reboot.
24. **Observation:** the user confirmed Android returned with a stable display.
    Runtime is slot B, locked/green, with top-level vbmeta digest
    `1d0b69562185dd76a39b18a603502ae24cef9739101e8159b939d48828e837d3`.
    Magisk first- and second-stage init ran, `magiskd` is active, and Manager
    reports version `31.1` / code `31100`.
25. **Observation:** this intermediate boot still uses the old bring-up system:
    `ro.adb.secure=0`, and `adb root` still succeeds even though adbd initially
    starts as UID `2000` with `service.adb.root=0`. This is not the release ADB
    gate; the already prepared secure system profile must remove that
    capability.
26. **Action:** completed Magisk Manager's one-time setup and rebooted. Magisk
    31.1 uses a manual **Grant Superuser** list: unknown applications and ADB
    shell are denied instead of receiving an interactive pop-up.
27. **Observation:** a test-only ordinary application UID was denied with exit
    `13` before authorization. The user then enabled it in Manager's Grant
    Superuser list using the accepted C9 cursor; the policy database recorded
    UID `10463`, policy `2`, and the same test returned exit `0` with
    `uid=0(root)` in `u:r:magisk:s0`.
28. **Action:** deleted the temporary policy, uninstalled the root probe, and
    rechecked ADB shell. Shell is UID `2000`, has no policy row, and `su`
    returns exit `13`. On-device hashes after Manager setup remain exactly:
    - `init_boot_b`:
      `2a660a1eaadfcab823f33fa86bb9ed09cbf099bbcaa902286e6093f02ef87efc`;
    - `vbmeta_b`:
      `db7fb47c124352a03859e8ad16df17d0c37b54f31d40e031fb275800398dab00`.
29. **Observation:** two independent C9 builds differed only in AGP-generated,
    optional baseline-profile ordering; `classes.dex` and every other APK
    entry were identical. Removing those optimization hints before signing
    produced identical T440W APKs with SHA-256
    `0fdaf4646a5bdc7ac85853aeacbe48fc71f2326d5c70594f85958c8fda7f28f2`.
30. **Action:** generalized exact-file ext4 injection, added release-side ADB
    property cleanup, neutralized PHH's `adb_root` init service, and rebuilt
    ODM from the current system/vendor policy inputs without the bring-up-wide
    permissive transformation. The release ODM contains the non-debug platform
    init policy and no `init.t440w.debug.rc`.
31. **Action:** grew the raw system ext4 filesystem by 256 MiB, from
    `2,056,237,056` to `2,324,672,512` bytes. Injected the action-only keypad
    shim, accepted C9, Magisk Manager, microG Services and Companion, their
    ARMv7 native libraries and permission/sysconfig files, and non-privileged
    Aurora Store. Every pre-existing system file outside the declared ADB and
    keypad replacements retained the same mode, size, and content hash.
32. **Observation:** the expanded filesystem has `169,930,752` free bytes
    after injection. Its signed size is `2,344,615,936` bytes, leaving
    `197,046,272` bytes of the verified two-region system capacity unused.
    Super metadata maps system to:
    - LBA `3698688`, `1,240,920` sectors;
    - LBA `6254592`, `3,338,408` sectors.
33. **Observation:** offline AVB verification passed for system and ODM.
    `vbmeta_system_b` changes only descriptor index `12` (system), and the
    Magisk-derived top-level vbmeta changes only descriptor index `21` (ODM),
    preserving its already verified init-boot descriptor and every other
    descriptor byte.
34. **Prepared release output hashes:**
    - system:
      `c5fdfd82384ca898d39558bcb80fbb6e56f002332cd71194bafc8850077b23ac`;
    - system extent 0:
      `151478f881269895dda0ea77ba66911c786993f46846599c406aa7de3fbdb243`;
    - system extent 1:
      `96a84c3a4ba7a7dc651f23e7169cb038e20e683278f2ab6b6aabe8730ec5e5ad`;
    - ODM:
      `d2e25d132cad30b61dae0c79e91e66da0f8255be6bff983d61480edb27bc8222`;
    - super metadata:
      `730246d306c90aa474eb75e0d346c2ee9eeec49726d9171dc70f51c5ef85eecf`;
    - `vbmeta_system_b`:
      `d9027b48e1319e975bf281202dafb9ab929baaa677f656af835996cf668d4cd7`;
    - `vbmeta_b`:
      `61224f852e344fb06b04be931edf5198642d2bd8acbf8be22a5090102a92b85e`.
35. **Planned final write set:** after fresh EDL GPT and complete target-range
    backups, write system extent 0, system extent 1, and ODM first; write super
    metadata next; write raw `vbmeta_system_b` and raw `vbmeta_b` last. No
    write uses `--skipresponse`. Read back and compare all six ranges before
    reboot. `init_boot_b` is read and checked but not rewritten because the
    accepted Magisk image is already installed.
36. **Planned final rollback set:** restore the full same-session ranges for
    system extent 0 (`1,240,920` sectors), the expanded extent-1 target
    (`3,338,408` sectors), ODM (`2,872` sectors), super metadata (`1,024`
    sectors), `vbmeta_system_b` (`128` sectors), and `vbmeta_b` (`128`
    sectors), then read and compare every range before reboot.
37. **Observation:** the initial independent rebuild differed only in
    e2fsprogs wall-clock inode/superblock metadata and the downstream AVB
    hashes. The builder now normalizes declared changed inodes and ext4
    superblock write/check times, rejects checksum-bearing filesystems that
    need a different normalizer, and performs a read-only filesystem check.
    A fresh canonical build and a second independent local build compared
    byte-for-byte across ODM, system, both system extents, super metadata, and
    both vbmeta images. The hashes in observation 34 are that reproducible set.
38. **Action:** after the user reconfirmed a stable Android display, entered
    EDL and obtained fresh GPT output and complete backups under
    `artifacts/backups/pre-rooted-release/20261101T193619Z-final/`. Known
    installed hashes matched for Magisk init boot, current ODM, super metadata,
    and both vbmeta images. Concatenating extent 0 and the currently mapped
    prefix of extent 1 reproduced current system hash
    `d20e2c86bd2ac4bae24384f9a53ad68f872d5b1cd21a6c2dc5baad534a172112`.
    The full expanded extent-1 target was backed up, including its previously
    unmapped tail.
39. **Action:** wrote both system extents, ODM, super metadata,
    `vbmeta_system_b`, and `vbmeta_b` in that order. All writes omitted
    `--skipresponse` and completed. During mandatory readback, complete system
    extent 0 compared exactly with hash
    `151478f881269895dda0ea77ba66911c786993f46846599c406aa7de3fbdb243`.
40. **Process interruption:** EDL then disappeared from USB before the second
    readback began. A cable reconnect did not restore `05c6:9008`; after the
    documented Power hold, Android booted. The other five ranges therefore
    remained unverified across that first boot and must be reread before this
    flash can be accepted.
41. **Runtime observation after interrupted verification:** Android booted
    slot B, locked/green, with `ro.debuggable=0`, `ro.adb.secure=1`, enforcing
    SELinux, and ADB shell UID `2000`. The user reported the display visible
    but unstable, so the release failed its display gate.
42. **Root cause:** init parsed `init.t440w.platform.rc` and tried the
    composition helper at SurfaceFlinger start and boot completion, but both
    attempts exited `127`: enforcing SELinux denied `execv` because the helper
    was labeled generic `vendor_file`. Forced client composition was therefore
    never enabled. The accepted permissive bring-up profile had hidden this
    file-label defect.
43. **Action:** rebuilt ODM with the composition helper labeled
    `vendor_shell_exec`, then backed up, wrote, and read back the corrected ODM
    and its top-level vbmeta. The corrected hashes are
    `fc8039c407fdd41328d02e66c5b2a02e48bc857ea2adba3c274550b80178a437`
    and
    `734030bc9080e14037ec0ef76b00fa1b785828a43a3b95e32c13adad6ed9852b`.
    The previously interrupted system, super-metadata, and vbmeta-system
    readbacks were also completed and matched their prepared images exactly.
44. **Observation:** the corrected release booted slot B locked/green and
    enforcing. It retained authenticated non-root ADB, denied shell `su`,
    ran the display helper for its bounded 61-second interval and exited zero,
    and passed the user's stable-display, keypad, C9, and hidden-navigation-bar
    physical gates.
45. **Observation:** microG's required Self-Check items and permissions pass;
    only optional legacy GsfProxy/C2DM remains unchecked. Aurora anonymous
    browsing, download, and Session Installer passed. The user's installed
    Signal package and data remain present.
46. **Release-blocking observation:** Magisk Manager reports an abnormal state
    when Android scans it from `/system/app/Magisk`; Manager does not support
    running as a system application. This does not invalidate the accepted
    Magisk root payload in `init_boot_b`, but Manager must instead be installed
    normally under `/data/app`.
47. **Action:** changed the release image to carry the pinned Manager installer
    at non-package-scanned
    `/system/etc/t440w/release/Magisk-v31.1.apk`, removed its system-app and
    extracted-library entries, and added microG's background-location default
    permission. Two independent final builds compared byte-for-byte. Final
    changed hashes are:
    - system:
      `60d9873a62f428b0d1694eb156f5e833c2ccccf9bd630292327d10a7ff263643`;
    - system extent 0:
      `ab110b2ffbe3677cd41b69ae55d9d164c6a0548f86d7187a9cccc8c6c1991b0e`;
    - system extent 1:
      `9db26fda32e4e5f4f8d73a9a021ce45439f84ae478088a824bba52ae59960fe6`;
    - `vbmeta_system_b`:
      `16c73ffa2ab875de0284173af55d2ee8be6acfab7bc6eb623526caf38e7f678f`.
    ODM, super metadata, and top-level vbmeta remain byte-identical to the
    accepted corrected release.
48. **Action:** after the user confirmed EDL, fresh GPT output reconfirmed the
    reference unit, slot-B geometry, and 512-byte sectors. Fresh rollback reads
    are under
    `artifacts/backups/pre-rooted-release-manager-correction/20261101T202705Z/`
    and match the installed accepted release:
    - extent 0:
      `151478f881269895dda0ea77ba66911c786993f46846599c406aa7de3fbdb243`;
    - extent 1:
      `96a84c3a4ba7a7dc651f23e7169cb038e20e683278f2ab6b6aabe8730ec5e5ad`;
    - `vbmeta_system_b`:
      `d9027b48e1319e975bf281202dafb9ab929baaa677f656af835996cf668d4cd7`.
    Rollback writes are raw `ws` to LBA `3698688`, `6254592`, and `2080768`
    respectively, without `--skipresponse`, followed by complete
    `--skipresponse` reads and exact comparison before reboot.
49. **Action:** wrote the final Manager-placement correction to both system
    extents and raw `vbmeta_system_b`. Both complete extents and the vbmeta
    range were subsequently read with `--skipresponse` and compared exactly
    before reboot. The first vbmeta read attempt began after USB had dropped,
    performed no read, and was retried successfully after reconnection.
50. **Observation:** Android returned with a stable display, but the physical
    CONTACTS key launched Contacts instead of toggling C9. The image contained
    the intended `KeypadActionService`; PackageManager still exposed the old
    `KeypadCursorService`. The old and new same-signed APKs both used version
    code `1` and normalized modification time, so the existing-user package
    cache did not rescan the changed manifest. Installing the action APK as a
    reversible `/data` update immediately exposed and bound the correct
    service, and the user confirmed that cursor behavior passed again.
51. **Action:** increased the baked keypad action package to version code `2`
    / version name `1.1`, rebuilt it twice byte-identically with SHA-256
    `450e8e06a6b723479b0279d6857bb2d47a3fde594e44b8c403e56749497d21ec`,
    and rebuilt the complete release twice byte-identically. The permanent
    upgrade-safe final hashes are:
    - system:
      `9a9616da3b136c7d8c3dbf788871237ee114f9cf8ca872de9f2c875d0f8dfa1a`;
    - unchanged extent 0:
      `ab110b2ffbe3677cd41b69ae55d9d164c6a0548f86d7187a9cccc8c6c1991b0e`;
    - extent 1:
      `0588e3523bfa663109ddb0be8c3ebe78e0a2d11a7f308085e939db8579a960f4`;
    - `vbmeta_system_b`:
      `852ce9b924b61171900a6acd88700c887b5bf73663f487a82a6afd50821171ea`.
    ODM, super metadata, top-level vbmeta, and system extent 0 are unchanged,
    so the minimal permanent write set is extent 1 followed by raw
    `vbmeta_system_b`.
52. **Action:** after the user returned the phone to EDL, fresh GPT output
    again matched the reference unit and slot-B geometry. Fresh pre-write
    rollback reads are under
    `artifacts/backups/pre-rooted-release-keypad-v2/20261101T204637Z/`:
    - system extent 1:
      `9db26fda32e4e5f4f8d73a9a021ce45439f84ae478088a824bba52ae59960fe6`;
    - `vbmeta_system_b`:
      `16c73ffa2ab875de0284173af55d2ee8be6acfab7bc6eb623526caf38e7f678f`.
    Rollback is raw `ws` of those files to LBAs `6254592` and `2080768`
    respectively, with no `--skipresponse`, followed by complete
    `--skipresponse` reads and exact comparison before reboot.
53. **Action:** wrote final-v2 system extent 1 and raw `vbmeta_system_b`
    without `--skipresponse`, read both complete ranges with
    `--skipresponse`, and compared them exactly before reboot. Read-back
    hashes are the final hashes in observation 51.
54. **Direct physical observation:** after reboot, the user confirmed that the
    display is stable and every keypad/cursor action passes. The temporary
    `/data` keypad update was then removed; PackageManager fell back to the
    baked version `1.1` / code `2` APK under `/system`, exposed
    `KeypadActionService`, and bound it alongside C9.
55. **Observation:** final runtime is slot B, locked/green, SDK 34 and ARMv7,
    with top-level vbmeta digest
    `e11b2c7594f3bdd44ec09c60a986d8463ac8b2a28945a668ed5d33b3988e1fb1`.
    SELinux is enforcing; `ro.debuggable=0`, `ro.force_debuggable` is empty,
    `ro.adb.secure=1`, `service.adb.root=0`, adbd and its shell are UID 2000,
    and shell `su` returns exit `13`. `adb root` does not change that state.
56. **Observation:** the composition helper stopped normally after 61.614
    seconds with status zero; the keypad helper also stopped normally. No
    navigation-bar inset source exists, `persist.sys.phh.mainkeys=1`, tracing
    is off with the `nop` tracer and no kprobes, and no bounded helper remains
    running. A top sample showed no release component consuming measurable CPU.
57. **Action:** installed the image-carried Magisk 31.1 installer normally.
    Manager resolves only from `/data/app`, has no system-app flags, opens
    without the abnormal-state warning, and recognizes installed Magisk
    `31.1 (31100)`.
58. **Observation:** the test-only Root Probe was initially denied with exit
    `13`. After the user explicitly enabled it in Manager, it returned exit
    zero as `uid=0(root)` in `u:r:magisk:s0`. The temporary policy was deleted,
    the probe was uninstalled, Manager's Superuser list became empty, and
    shell `su` remained denied.
59. **Observation:** microG is loaded from `/system/priv-app`; its required
    permissions, including background location, are granted. Android's
    add-account screen exposes the microG-backed **Google** account type.
    Optional legacy GsfProxy/C2DM remains the only unchecked Self-Check item.
    Aurora remains a non-privileged system app and its anonymous browse,
    download, and Session Installer tests pass. The user's Signal installation
    remains intact.

## Conclusions

The rooted release stack is accepted. Magisk v31.1 in `init_boot_b` supplies
explicit per-application root while authenticated ADB remains non-root.
Manager must be installed as a normal `/data` application from the pinned
installer carried outside package-scanned system directories.

C9 is the accepted cursor, microG Services and Companion provide the system
Google-compatibility layer, and Aurora is the non-privileged system store.
The enforcing release profile preserves the stable forced-client-composition
display, physical keypad, hidden navigation bar, and user data.

The AVB chain is internally verified but remains anchored in public AOSP test
keys. This is suitable for the current community image, not a private
production trust anchor.

## Disproven assumptions

- A Magisk Manager APK cannot be shipped as a scanned system application;
  Magisk explicitly rejects that state.
- Replacing a same-signed system APK's manifest while retaining the same
  version code and normalized timestamp does not reliably invalidate
  PackageManager's existing-user cache. Component-changing releases require a
  version-code increase.
- Successful EDL write text is not evidence of persistence. Only the complete
  readbacks established the accepted final state.

## Mistakes and process corrections

- The first post-reboot USB check ran before macOS re-enumerated the phone and
  blocked in `adb wait-for-device`; the user reconnected the cable and no
  storage action occurred.
- The first EDL GPT process stalled before programmer output. It was terminated
  without a read or write, the USB cable was reconnected, and the next fresh
  EDL session completed normally.
- The first root-probe APK omitted javac-generated anonymous inner classes from
  DEX and crashed. The builder was corrected to include every generated class
  before the authorization result was evaluated.
- A second release build written directly into the synchronized artifact tree
  remained raw at the ODM AVB-footer step despite the child tool returning
  success. Verification stopped the build before any comparison or device
  action. Reproduction was moved to a local nonsynchronized output directory;
  the canonical release artifact remained intact and independently verified.
- EDL disappeared before mandatory readback twice during this session. No
  reboot was accepted until USB was restored and every affected range was
  reread and compared.
- The first final image scanned Manager as a system app and the first
  upgrade-safe keypad image retained version code `1`. Runtime gates caught
  both release defects; each correction changed only the smallest required
  system/vbmeta ranges and received a fresh backup and complete readback.

## Ending state

- Mode: booted Android on slot B, locked/green, enforcing.
- Display/keypad: stable display; baked keypad version `1.1` code `2` and C9
  bound; full physical gate passed; no navigation-bar inset.
- Root/debug: authenticated non-root ADB; shell UID 2000; application root
  denied by default; Manager installed under `/data/app`; no grants or root
  probe remain.
- Release components: system microG, Companion, C9 and Aurora; Signal preserved.
- Final installed image hashes:
  - `init_boot_b`:
    `2a660a1eaadfcab823f33fa86bb9ed09cbf099bbcaa902286e6093f02ef87efc`;
  - system:
    `9a9616da3b136c7d8c3dbf788871237ee114f9cf8ca872de9f2c875d0f8dfa1a`;
  - system extent 0:
    `ab110b2ffbe3677cd41b69ae55d9d164c6a0548f86d7187a9cccc8c6c1991b0e`;
  - system extent 1:
    `0588e3523bfa663109ddb0be8c3ebe78e0a2d11a7f308085e939db8579a960f4`;
  - ODM:
    `fc8039c407fdd41328d02e66c5b2a02e48bc857ea2adba3c274550b80178a437`;
  - super metadata:
    `730246d306c90aa474eb75e0d346c2ee9eeec49726d9171dc70f51c5ef85eecf`;
  - `vbmeta_system_b`:
    `852ce9b924b61171900a6acd88700c887b5bf73663f487a82a6afd50821171ea`;
  - `vbmeta_b`:
    `734030bc9080e14037ec0ef76b00fa1b785828a43a3b95e32c13adad6ed9852b`.
- Modified storage: `init_boot_b`, system extents at LBAs `3698688` and
  `6254592`, `odm_b`, super metadata, `vbmeta_system_b`, and `vbmeta_b`.
  Fresh rollback sets are recorded in observations 22, 38, 43, 48, and 52;
  the verified full-eMMC backup remains the catastrophic fallback.

## Safe next step

Perform no further device write in this session. The smallest next release
step is to package the byte-reproducible final-v2 artifacts, pinned Manager
installer, source/license material, hashes, and rollback instructions.
