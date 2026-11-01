# 2026-11-01 09: Physical keypad navigation

Status: complete

## Objective

Make the physical keypad sufficient to complete Android setup: provide
Messages, Back, Home, a toggleable D-pad cursor with conditional scrolling,
inert application-reserved softkeys, and no unusable on-screen navigation bar.
Prototype entirely through reversible `/data` state before changing an image.

## Starting state

- Captured at `2026-11-01T17:33Z`.
- Device mode and active slot: booted Android GSI over ADB, slot B (`_b`).
- Running OS:
  - fingerprint:
    `TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys`
  - system fingerprint: same as runtime fingerprint
  - SDK: `34`
  - ABI: `armeabi-v7a` (`armeabi-v7a,armeabi`)
  - verified-boot state: locked/green with verity enabled
- Retained stable-display identity:
  - top-level vbmeta digest:
    `362827d0a97d4b386bf10fbcacc5d780d184a1bed76061c7ccad01a7aee8950c`
  - full-height module SHA-256:
    `89febd510f7aa939ce8a20943038f0beab67d1d59a49ce48110dc229b624cf50`
  - installed ODM image SHA-256:
    `f80d0c0b27d2b364050bd8a82dc5dfad7eba7fd8f51a89dcef9c6cd9a6bc2025`
  - installed `vbmeta_b` SHA-256:
    `779b1c409d5d4124261d5975410db5364c3f47d5e31e4f110f708ab79a864b7a`
  - bounded composition service: stopped normally
  - SurfaceFlinger transaction `1010`: forced client composition enabled
- Retained system host artifacts, unchanged by sessions 05 through 08:
  - `artifacts/build/android-lineage21-clean/system_b_android.img`:
    `42e9ae566f581e05f3763a37a3c6bd3214addde80f852619c4c40dbb4d726fb7`
  - `artifacts/build/android-lineage21-clean/vbmeta_system_b_android.img`:
    `e591ed5b7f982583b05401fa2512e1bcffea4eb057bb10b4e06b63ac536d85e2`
  - these host identities must not substitute for same-session raw reads
    before an image write.
- Backup/rollback state:
  - verified full eMMC backup SHA-256:
    `ec16365c0b1147a98d08a39e2557b0d0ac5415aa48db8efcde29b0fe736118b3`
  - immediate display-profile rollback:
    `artifacts/backups/pre-spi-persistence-v4/20261101T171056Z/`
  - original pre-persistence stable profile:
    `artifacts/backups/pre-spi-persistence/20261101T165459Z/`
- ADB/root/trace gate:
  - serial: `830f21d`
  - `ro.debuggable=0`
  - `ro.force_debuggable` is empty
  - `service.adb.root=1`
  - identity: `uid=0(root)`, context `u:r:su:s0`
  - `tracing_on=0`, `current_tracer=nop`, empty `kprobe_events`
- Input state:
  - `soc_matrix_keypad0` uses
    `/odm/usr/keylayout/soc_matrix_keypad0.kl`
  - current relevant mappings are `30 ENVELOPE`, `48 DEL`,
    `116 ENDCALL WAKE`, `138 CONTACTS`, `139 MENU`, `158 BACK`, and
    `231 CALL`
  - keys 139 and 158 are the physical left/right softkeys and must become
    inert by default while retaining their scan codes for later app shims
- Android navigation/accessibility state:
  - `qemu.hw.mainkeys=0`
  - secure `navigation_mode=0`
  - global `policy_control=null`
  - accessibility is disabled and no services are enabled
  - the visible navigation bar occupies the bottom 36 pixels
- Messaging resolution:
  - main messaging activity:
    `com.android.messaging/.ui.conversationlist.ConversationListActivity`
  - `smsto:` activity:
    `com.android.messaging/.ui.conversation.LaunchConversationActivity`
- Android activity state is inconsistent in the live dumps:
  `dumpsys activity top` identifies
  `org.lineageos.setupwizard/.DateTimeActivity`, while window focus identifies
  `com.android.contacts/.activities.PeopleActivity`. Do not infer successful
  setup completion from either alone.

## Artifacts

- Repository starting commit:
  `fcef1a9c92106c0024e981d2d2141e6cf66775e5`
- Planned prototype package:
  `tooling/keypad-cursor/`
- Planned ignored build output:
  `artifacts/build/keypad-cursor/`

## Actions and observations

1. **Observation:** the repository was clean and synchronized with
   `origin/main` before this session.
2. **Observation:** the running device retained the complete session-08
   display profile, root ADB, writable tracing context, and clean trace state.
3. **Observation:** Android currently exposes a visible 36-pixel three-button
   navigation bar even though the phone has no touch input.
4. **Observation:** the stock AOSP Messaging package resolves both a generic
   messaging launcher and `smsto:` intent.
5. **Inference:** an AccessibilityService can prototype all requested actions
   without a partition write, while the final static Back/Home and inert
   softkey mappings still belong in the device keylayout.
6. **Direct physical observation:** before any prototype installation, the
   user confirmed that the display was correct and stable.
7. **Action:** built and installed the first reversible AccessibilityService
   prototype, preserving the original accessibility and policy settings.
8. **Observation:** the shorthand accessibility component was rejected from
   `enabled_accessibility_services`; the full component name enabled and bound
   the service successfully.
9. **Direct physical observation:** the first bound prototype did not respond
   to any physical keys. Its metadata requested the filter-key-events flag but
   omitted the separate `canRequestFilterKeyEvents` capability declaration.
10. **Direct physical observation:** global
    `policy_control=immersive.navigation=*` did not hide the navigation bar;
    `dumpsys window` also continued to report it visible.
11. **Action:** added the missing filter-key-events capability, rebuilt with
    the same signing key, reinstalled, and rebound the service.
12. **Observation:** Android then reported capability `40` and the corrected
    service received physical key events.
13. **Direct physical observation:** Messages, Back, both inert softkeys, the
    cursor toggle, one-press D-pad movement, center click, page-up, and
    page-down all worked.
14. **Direct physical observation:** the physical End key still invoked Power
    policy rather than Home. This establishes that the hardware event follows
    the separate `pm8941_pwrkey` mapping and is consumed before accessibility,
    not the matrix `ENDCALL` mapping assumed by the initial plan.
15. **User correction:** the cursor should be an arrow, and holding a D-pad
    direction should move continuously instead of requiring repeated presses.
16. **Action:** changed the cursor to an arrow, added key-down/key-up tracking
    with a 180 ms initial delay and 50 ms movement interval, and reinstalled.
17. **Direct physical observation:** the arrow, held-direction movement,
    click, scrolling, and physical display all passed. The user then requested
    black fill with a small white border.
18. **Action:** changed only the arrow colors and border width, rebuilt, and
    reinstalled.
19. **Direct physical observation:** the final black arrow with white border
    and the stable physical display both passed.
20. **Action:** set the live `qemu.hw.mainkeys` property to `1` and performed
    one controlled zygote/framework restart to test the actual Android
    navigation policy without writing a partition.
21. **Observation:** after framework services returned, `dumpsys window`
    contained no navigation-bar inset source, the cursor service rebound with
    filter-key capability `40`, and forced client composition remained active.
22. **Direct physical observation:** the navigation bar was gone and the
    physical display remained correct and stable.

## Prototype result

- APK SHA-256:
  `93b3ef7600d2070a59e58bce38835903df6bc456068ac6bd5679b3c087196dc5`
- APK signing-certificate SHA-256:
  `c3cddbb6e69fa957a606600725ef4e75d390142ed5f68608861e4102beb862e2`
- Passed without a partition write:
  - Messages launch;
  - Back;
  - inert left/right softkeys;
  - cursor toggle, arrow overlay, held D-pad movement, center click;
  - page up/down on left-softkey/Call only while cursor mode is active;
  - normal Call behavior while cursor mode is inactive;
  - navigation-bar removal after a framework restart with
    `qemu.hw.mainkeys=1`;
  - stable physical output.
- Not achievable through the prototype layer:
  - the physical End/Power event is consumed by Android power policy before
    AccessibilityService filtering. Its device-specific pwrkey keylayout must
    map scancode 116 to `HOME WAKE`.

## Preliminary durable build

- Path: `artifacts/build/keypad-profile-preliminary/`
- Exact retained inputs:
  - ODM:
    `f80d0c0b27d2b364050bd8a82dc5dfad7eba7fd8f51a89dcef9c6cd9a6bc2025`
  - system:
    `42e9ae566f581e05f3763a37a3c6bd3214addde80f852619c4c40dbb4d726fb7`
  - `vbmeta_b`:
    `779b1c409d5d4124261d5975410db5364c3f47d5e31e4f110f708ab79a864b7a`
  - `vbmeta_system_b`:
    `e591ed5b7f982583b05401fa2512e1bcffea4eb057bb10b4e06b63ac536d85e2`
- Preliminary outputs:
  - ODM:
    `08ab4dd5668093320c68a0687186ea795920737e0a23a118179a647087eb6e99`
  - system:
    `e8abb001c99333082137c6861d017abedaf8f137284956d94c01c10f91d02269`
  - `vbmeta_b`:
    `8fad0193d7da0730b4e260e4c8ed5ecb583dd045fa20ccda68126b9a195a674d`
  - `vbmeta_system_b`:
    `eeb0b562a7734175973cd69e4acea34efb898ce897ce5daeed63c16f9a26dd51`
- Offline validation:
  - complete ODM and system hashtrees verify;
  - both vbmeta signatures and embedded keys verify;
  - only ODM descriptor index 21 and system descriptor index 12 changed in
    their respective vbmeta images;
  - retained vendor-DLKM root remains
    `baa4df9bb3dc6d068c34ff4720a23a8c8d861db1046494ad4933a37f9144719d`;
  - retained composition init/helper compare byte-for-byte with source;
  - embedded APK, keypad helper, init file, keylayouts, modes, ownership, and
    SELinux labels match their sources;
  - system and ODM output sizes exactly match the current partition images.
- This is an offline control only. Same-session EDL reads remain mandatory
  before deriving or authorizing the final write set.

## Fresh current-state backup and final build

- Backup:
  `artifacts/backups/pre-keypad-profile/20261101T174853Z/`
- Fresh raw reads, all made with `--skipresponse`:
  - ODM, LBA `3688448`, `2872` sectors:
    `f80d0c0b27d2b364050bd8a82dc5dfad7eba7fd8f51a89dcef9c6cd9a6bc2025`
  - system extent 0, LBA `3698688`, `1240920` sectors:
    `9e44b3809a90d1126c361fa5b9522329f1f507c00792a381b09ed68ecc676ee2`
  - system extent 1, LBA `6254592`, `2810024` sectors:
    `f3940842841f80270afce28c60237af4dd6e819750e8c2ca0ce6139d4a4cf619`
  - concatenated system:
    `42e9ae566f581e05f3763a37a3c6bd3214addde80f852619c4c40dbb4d726fb7`
  - `vbmeta_system_b`, LBA `2080768`, `128` sectors:
    `e591ed5b7f982583b05401fa2512e1bcffea4eb057bb10b4e06b63ac536d85e2`
  - `vbmeta_b`, LBA `3377152`, `128` sectors:
    `779b1c409d5d4124261d5975410db5364c3f47d5e31e4f110f708ab79a864b7a`
- Every fresh read exactly matches its retained host artifact or the expected
  concatenation of the two current system extents.
- Current-derived build:
  `artifacts/build/keypad-profile-current/`
- Final outputs:
  - ODM:
    `663d7fae9123e80fc4c3c2759dfb553ff1aa9b746d91e66a3c619b4f0db39c3b`
  - system:
    `d20e2c86bd2ac4bae24384f9a53ad68f872d5b1cd21a6c2dc5baad534a172112`
  - system extent 0:
    `859eef0beb12ba832d2c827ca4f9dff1c672ebc145fb82dd9e59a268411e7160`
  - system extent 1:
    `291aeb3ae9ec8928755d7afad47ca418db3df1ab50e3518c902977654a3d8eeb`
  - `vbmeta_system_b`:
    `5bb155cde647c2d275ecdec48587c0e181aab44d9f7b55c4126f5bd39c31b44c`
  - `vbmeta_b`:
    `d59a24838c254df85ea639aaab9658f07abf01c4166f88caeebc5d795fd3ec6a`
- Final root digests:
  - ODM:
    `7ed1e33645288a7a327796edabab2e5cf22aedbc6eb5bf1284743987732944e8`
  - system:
    `0b96d47029aea415a2aaec4e083d6a279bd8830303d2771f972cb2bf25546acf`
- Final validation passed:
  - the two output system extents concatenate exactly to the signed system
    output;
  - complete system and ODM hashtrees verify;
  - both vbmeta signatures and embedded keys verify;
  - only ODM descriptor index 21 and system descriptor index 12 changed;
  - all untargeted descriptors, including the retained full-height
    vendor-DLKM root, are unchanged;
  - embedded files compare byte-for-byte with source and have the intended
    modes, ownership, and SELinux labels;
  - APK signature verifies;
  - all payload and vbmeta sizes exactly match the current raw ranges.

## Planned write and rollback set

- Write without `--skipresponse`, payloads first and verification metadata
  last:
  1. system extent 0 at LBA `3698688`;
  2. system extent 1 at LBA `6254592`;
  3. ODM at LBA `3688448`;
  4. `vbmeta_system_b` at raw LBA `2080768`;
  5. `vbmeta_b` at raw LBA `3377152`.
- Read all five complete ranges back with `--skipresponse` and compare
  byte-for-byte before reboot.
- Immediate rollback uses the same-session files above in the same order:
  system payloads, ODM, `vbmeta_system_b`, then `vbmeta_b`, followed by complete
  read-back comparisons.
- Super metadata, vendor-DLKM, DTBO, and every other range remain untouched.

23. **Direct physical observation:** immediately before EDL, the user
    confirmed the final black-arrow prototype, absent navigation bar, and
    stable physical display.
24. **Action:** entered EDL and reconfirmed HWID
    `0x002980e100420071`, serial `0xa2676da1`, the reference PK hash, 512-byte
    eMMC geometry, and all raw target LBAs.
25. **Action:** read the five complete current target ranges with
    `--skipresponse`.
26. **Observation:** all fresh reads exactly matched the retained host images
    and established the current two-extent system mapping without changing
    super metadata.
27. **Action:** rebuilt the final profile only from those fresh reads and
    passed all recorded offline validation gates.
28. **Action:** after independent user authorization, wrote the two system
    extents, ODM, `vbmeta_system_b`, and finally `vbmeta_b`. No write used
    `--skipresponse`.
29. **Observation:** read all five complete ranges back with
    `--skipresponse`; every read-back compared byte-for-byte and reproduced the
    expected final SHA-256 value.
30. **Observation:** Android booted normally on slot B, locked/green, with new
    top-level vbmeta digest
    `93109f2ccaaf1d64d576128c95fe9c931fec259f26c6d2353fa0352e4d082ef5`.
    Root adbd required the expected post-boot `adb root` transition and then
    returned to `uid=0`, `u:r:su:s0`.
31. **Observation:** the baked APK, helper, init file, keylayouts, retained
    composition files, and full-height module all matched their expected
    hashes on the running device. The accessibility service was enabled and
    bound.
32. **Direct physical observation:** Messages, Back, Home, cursor toggle,
    arrow movement/click, scrolling, and the stable display passed after the
    full reboot.
33. **Negative result:** both supposedly inert `BUTTON_1`/`BUTTON_2` softkeys
    opened the currently selected Calendar app. Android treats those gamepad
    button keycodes as activation input, so they are not inert.
34. **Negative result:** the navigation bar returned. TrebleDroid's
    `/system/etc/init/vndk.rc` copies `persist.sys.phh.mainkeys` over
    `qemu.hw.mainkeys`; the persistent PHH value remained `0` and defeated the
    ODM build-property default.
35. **Action:** changed the reserved softkeys to `F1`/`F2`, which a live
    injected-key control showed caused no activity transition.
36. **Action:** added an ODM `post-fs-data` override for both
    `persist.sys.phh.mainkeys=1` and `qemu.hw.mainkeys=1`, before zygote and
    system-server startup. Also retained both defaults in ODM `build.prop`.
37. **Action:** applied the corrected persistent PHH value live and performed
    the same controlled framework restart; no partition was changed by this
    runtime correction.
38. **Direct physical observation:** the navigation bar disappeared again and
    the physical display remained correct and stable.
39. **Action:** with separate user authorization, entered EDL and read only the
    current ODM and `vbmeta_b` ranges with `--skipresponse`.
40. **Observation:** both reads exactly match the first keypad-profile
    read-backs:
    - ODM:
      `663d7fae9123e80fc4c3c2759dfb553ff1aa9b746d91e66a3c619b4f0db39c3b`;
    - `vbmeta_b`:
      `d59a24838c254df85ea639aaab9658f07abf01c4166f88caeebc5d795fd3ec6a`.
41. **Action:** rebuilt an ODM-only correction from those fresh current bytes.
42. **Observation:** corrected outputs:
    - ODM:
      `2e66c8535449f239c180947a592434e452e3a979cfc89f8bf0ebe90433100c89`;
    - `vbmeta_b`:
      `e909b1735c3b1f1de342933735921124f7beee4fcfabe2ee06051fedaa574a90`;
    - ODM root:
      `1b0a0a1543b957cdb220f5c80d7d10b5439b7af527c7543860eed3530c8e237a`.
43. **Observation:** the correction passed complete ODM hashtree and top-level
    signature/key verification; only ODM descriptor index 21 changed; every
    untargeted descriptor remained identical; embedded init, helper, F1/F2
    keylayout, pwrkey layout, modes, ownership, and labels matched source.

### ODM correction write and rollback

- Write without `--skipresponse`:
  1. corrected ODM at LBA `3688448`, `2872` sectors;
  2. matching `vbmeta_b` at raw LBA `3377152`, `128` sectors.
- Read both complete ranges back with `--skipresponse` and compare
  byte-for-byte before reboot.
- Immediate rollback:
  `artifacts/backups/pre-keypad-odm-correction/20261101T180015Z/`, restored ODM
  first and vbmeta last, followed by complete read-back comparisons.
- The already-verified system, `vbmeta_system_b`, super metadata,
  vendor-DLKM, and every other range remain untouched.
44. **Action:** after separate user authorization, wrote corrected ODM first
    and current-derived `vbmeta_b` last; neither write used `--skipresponse`.
45. **Observation:** the EDL client printed its known post-program
    `'NoneType' object is not callable` library message, but both complete raw
    read-backs matched byte-for-byte:
    - ODM:
      `2e66c8535449f239c180947a592434e452e3a979cfc89f8bf0ebe90433100c89`;
    - `vbmeta_b`:
      `e909b1735c3b1f1de342933735921124f7beee4fcfabe2ee06051fedaa574a90`.
    The read-backs, not the client success text, are the acceptance evidence.
46. **Observation:** Android booted normally on slot B, locked/green, with
    final top-level vbmeta digest
    `814b5fe5df5bc29bc761e2dc33957483d0408f38cb04cab1e5e8dfa0e4062689`.
47. **Observation:** `persist.sys.phh.mainkeys=1` and
    `qemu.hw.mainkeys=1` were active before framework validation. No
    navigation-bar inset source existed.
48. **Observation:** the keypad enabler stopped normally, the accessibility
    service was enabled and bound, and the composition helper stopped normally
    with transaction `1010` still enabled.
49. **Direct physical observation:** every requested keypad and cursor action,
    inert F1/F2 softkeys, absent navigation bar, and stable display passed.
50. **Action:** removed the temporary `/data` APK update and fell back to the
    byte-identical baked `/system/app/T440WKeypadCursor` package.
51. **Observation:** the baked system package remained enabled and bound.
52. **Direct physical observation:** cursor toggle, movement, click, scrolling,
    softkeys, and stable display all passed with only the baked package.
53. **Action:** performed one final full phone reboot.
54. **Observation:** after that reboot:
    - slot B remained locked/green;
    - both bounded helpers stopped normally;
    - the baked accessibility service was enabled and bound;
    - the navigation bar remained absent;
    - forced client composition remained enabled;
    - root adbd and clean writable tracefs were recovered through `adb root`;
    - all installed file hashes matched the final sources.
55. **Direct physical observation:** the complete keypad/cursor gate and the
    correct, stable display passed after the final reboot.
56. **Observation:** Android reports `device_provisioned=1` and
    `user_setup_complete=1`.
57. **Action:** normalized APK ZIP timestamps and made the signing-scheme
    selection explicit for reproducible future builds.
58. **Observation:** two clean consecutive host builds both produced
    `89052332c1f7ceb33e862f121c45f6148bf531f9e53be826e7f01d1966cb419e`.
    The installed historical APK differs only in packaging timestamps; its
    `classes.dex` SHA-256 exactly matches the deterministic build:
    `994cda659d965a3402210b2641d02977bbe3b56d5348c9c458266c831d14f393`.

## Conclusions

- The physical keypad is sufficient to complete and operate Android setup.
- Static device keylayouts provide Back, Home, and inert app-reserved softkeys:
  - key 48: `BACK`;
  - physical/matrix key 116: `HOME WAKE`;
  - keys 139/158: `F1`/`F2`.
- The baked AccessibilityService provides Messages, a toggleable black-arrow
  cursor, held D-pad movement, center click, and conditional page scrolling.
- TrebleDroid navigation removal requires
  `persist.sys.phh.mainkeys=1`; its `vndk.rc` copies that value to
  `qemu.hw.mainkeys`. The ODM init hook asserts both before framework startup.
- The final profile survives a full reboot with the service automatically
  enabled, no navigation bar, and the retained stable-display pair unchanged.

## Disproven assumptions

- Requesting `flagRequestFilterKeyEvents` alone is sufficient: false; the
  service must also declare `canRequestFilterKeyEvents=true`.
- Global `policy_control=immersive.navigation=*` hides the Android 14 GSI
  navigation bar: false on this build.
- The physical End key follows only `soc_matrix_keypad0`: false; its effective
  event comes through `pm8941_pwrkey` and is consumed by Power policy.
- `BUTTON_1`/`BUTTON_2` are inert application-reserved keycodes: false;
  Launcher treats them as activation input.
- `qemu.hw.mainkeys=1` in ODM alone survives TrebleDroid startup: false;
  `vndk.rc` overwrites it from `persist.sys.phh.mainkeys`.

## Mistakes and process corrections

- The first enablement script used a shorthand component name that secure
  settings discarded. Use the fully qualified service component.
- The initial plan explicitly avoided the pwrkey map based on an unverified
  input-device assumption. Direct physical behavior overrode that assumption;
  both matrix and pwrkey maps now express Home.
- The first durable profile treated gamepad button keycodes as inert and set
  only the downstream navigation property. Both failures were recorded and
  corrected with a separately backed-up, ODM-only second write.

## Ending state

- Device mode and active slot: booted Android GSI on slot B.
- Running OS/build: retained Lineage/TrebleDroid Android 14 GSI with final
  physical-keypad profile and persistent stable-display profile.
- Final top-level vbmeta digest:
  `814b5fe5df5bc29bc761e2dc33957483d0408f38cb04cab1e5e8dfa0e4062689`.
- Final installed images:
  - ODM:
    `2e66c8535449f239c180947a592434e452e3a979cfc89f8bf0ebe90433100c89`;
  - system:
    `d20e2c86bd2ac4bae24384f9a53ad68f872d5b1cd21a6c2dc5baad534a172112`;
  - `vbmeta_system_b`:
    `5bb155cde647c2d275ecdec48587c0e181aab44d9f7b55c4126f5bd39c31b44c`;
  - `vbmeta_b`:
    `e909b1735c3b1f1de342933735921124f7beee4fcfabe2ee06051fedaa574a90`.
- Partitions or sectors changed:
  - system extent 0: LBA `3698688`, `1240920` sectors;
  - system extent 1: LBA `6254592`, `2810024` sectors;
  - ODM: LBA `3688448`, `2872` sectors;
  - `vbmeta_system_b`: LBA `2080768`, `128` sectors;
  - `vbmeta_b`: LBA `3377152`, `128` sectors.
- No super metadata, vendor-DLKM, DTBO, or other range was written.
- Verified rollback paths:
  - complete pre-keypad profile:
    `artifacts/backups/pre-keypad-profile/20261101T174853Z/`;
  - immediate pre-correction ODM/vbmeta pair:
    `artifacts/backups/pre-keypad-odm-correction/20261101T180015Z/`.
- ADB/root/trace access: root adbd and clean, writable tracefs.
- Physical state: navigation bar absent; complete keypad/cursor gate and
  display correct/stable by direct user observation.
- Android setup state: device provisioned and user setup complete.
- Uncommitted host artifacts: this finding; keypad app, keylayout, init,
  image-builder, runbook, and reference changes; ignored build/backup evidence.

## Safe next step

Commit this completed session. Future app shims can consume the reserved F1/F2
softkeys without changing the stable keypad, navigation, or display baseline.
