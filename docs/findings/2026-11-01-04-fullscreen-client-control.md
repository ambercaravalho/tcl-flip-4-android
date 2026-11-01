# 2026-11-01 04: Full-screen client control

Status: complete

## Objective

Determine whether a controlled real full-screen Android client changes the
GSI's plane/submission count and physical-panel behavior without modifying the
display driver.

## Starting state

- Captured at `2026-11-01T15:58:19Z`.
- Device mode and active slot: booted Android GSI over ADB, slot B (`_b`).
- Running OS:
  - fingerprint:
    `TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys`
  - system fingerprint: same as runtime fingerprint
  - SDK: `34`
  - ABI: `armeabi-v7a`
  - flavor: `treble_a64_bvN-userdebug`
- Runtime AVB identity:
  - top-level vbmeta digest:
    `fa818c9ccb99bfce94979e2b449a8404e5ab140f9e9f0077bad94cb470c6f657`
  - system root digest:
    `07d1de5bd1fcecf354df054908904872455d4af72e364dfbe580873a3cf533f0`
  - ODM root digest:
    `606838a37231d46c4e60a48f1ab987f7f4a16c27b3e1469dd926135422213711`
- Backup/rollback state:
  - verified full eMMC backup SHA-256:
    `ec16365c0b1147a98d08a39e2557b0d0ac5415aa48db8efcde29b0fe736118b3`
  - Region A remains overwritten; stock rollback is not metadata-only.
  - This session does not authorize a partition or driver write.
- ADB/root/trace gate:
  - serial: `830f21d`
  - `ro.debuggable=0`
  - `ro.force.debuggable=0`
  - `service.adb.root=1`
  - `adb shell id`: `uid=0(root)`, context `u:r:su:s0`
  - `adb root`: already running as root
  - `kprobe_events`: writable
  - capture start was clean: `tracing_on=0`, empty `kprobe_events`
- Relevant Android settings:
  - `policy_control=null`
  - `stay_on_while_plugged_in=7`
  - `screen_off_timeout=1800000`
- Known unresolved symptom: the user directly reports that the original
  display issues remain present **in full**. The panel is still stable when
  static and severely flickers/corrupts during redraw.

## Artifacts

- Prior GSI comparison:
  `../../evidence/captures/gsi-rooted/spi-one-key.txt`
- Full-screen client source:
  `../../tooling/fullscreen-control/`
  - manifest SHA-256:
    `7e6ca2e775a89f1f2887c5e71275f2e096f532ebe8d779093ee0747c6b9a1567`
  - Java source SHA-256:
    `1ba557da2f93a39137946c84432df00a011d79e867e280a073176a0e39b2ec09`
- Build script:
  `../../tooling/scripts/build-fullscreen-control.sh`
  - SHA-256:
    `a51ad09bf50695f5dd05a5689141c82db238f2a475b865a31afbd25020a0200b`
- Prepared APK:
  `../../artifacts/build/fullscreen-control/fullscreen-control.apk`
  - SHA-256:
    `ecd5ee6178aaab159c6652e6ca237a53c2f7f15908bffd99c0fc6bb6af5ba332`
  - package: `org.tclflip4.fullscreencontrol`
  - min/target SDK: `34` / `34`
  - signer certificate SHA-256:
    `75bf070214c45673b63851fac9b503a5768d998a5bad1cf7dd41d80081279f58`
- New control artifacts:
  `../../evidence/captures/gsi-fullscreen-control/`
  - baseline manifest timestamp: `2026-11-01T16:02:52Z`
  - baseline manifest SHA-256:
    `892873496906933cd3e571f770ff3d92203dbf54666ace6e9d5f7f12549c24ea`
  - trace SHA-256:
    `aa361abba9f373b876fc69d827d2e37432835b4723a9ed3e03910e967885cad9`
  - saved trace-analysis SHA-256:
    `9028563f630bb7f9a34ce231984aff8b34fafa49f257d8c69672444c3c0c6ba2`
  - post-failure manifest timestamp: `2026-11-01T16:05:24Z`
  - post-failure screenshot SHA-256:
    `1d2f8f4a7e7819c601167240c5e2bafa74d36f9603caa01f3394e2893be95a88`

## Actions and observations

1. **Observation:** the root/trace gate still passes without rebooting or
   changing partitions.
2. **Observation:** no previous immersive-policy override is active.
3. **Observation:** the user's physical-panel result has not improved after
   enabling root or capturing the prior trace; the complete display symptom
   remains.
4. **Action:** prepared an offline, test-signed Android control app. It uses one
   hardware-accelerated full-screen `View`, requests immersive system bars,
   draws a deterministic two-color pattern, and changes that pattern exactly
   once for a D-pad direction press.
5. **Observation:** the app requests no permissions, does not contain network
   code, and is excluded from recents. Its package is removable with a normal
   `adb uninstall`.
6. **Observation:** Android build tools verified the APK's v3 signature,
   package identity, SDK bounds, and launchable activity. No device state was
   changed during preparation.
7. **Action:** after user confirmation, installed the APK to `/data` and
   launched `org.tclflip4.fullscreencontrol/.MainActivity`. No partition or
   sector was written.
8. **Observation:** the activity was the resumed full-screen client.
   SurfaceFlinger exposed its `VRI[MainActivity]` buffers as `240x320`,
   fourcc `AB24`, 1024-byte stride. The initial host screenshot showed the
   intended blue/yellow pattern, and the user reported that the physical
   display was correct and stable.
9. **Action:** after a second user confirmation, captured a ten-second trace
   while the user pressed D-pad Up exactly once. The trace recorded one
   `code=103` press and release.
10. **Observation:** that one controlled visual change produced:
    - six `_sde_plane_atomic_update` entries;
    - four `spi_display_update_fb` calls: two `240x21` and two `240x320`;
    - `AB24` and 1024-byte pitch for all four framebuffer submissions;
    - five completed frame transfers from `spi_kickoff_thread`;
    - five command transfers from one full-window reset;
    - median TE interval `16.808 ms`;
    - full-frame SPI duration up to `25.008 ms`.
11. **Observation:** the first commit submitted a `240x21` plane, a
    `240x320` plane, and another `240x21` plane. A second commit then submitted
    another `240x320` plane. The private SPI bridge therefore still received
    several independent planes/frames for one intended app-state change.
12. **Direct physical observation:** the user reported that the panel showed
    the changed pattern for a split second, then jumped around, and ended as a
    gray panel with the backlight still on.
13. **Observation:** a post-failure Android screenshot remained logically
    correct, showing the intended green/magenta pattern. The app process and
    resumed activity also remained present. This separates the gray physical
    panel state from the app and SurfaceFlinger output.
14. **Observation:** capture cleanup left `tracing_on=0`,
    `current_tracer=nop`, and an empty `kprobe_events`.

## Conclusions

- The controlled full-screen-client gate is complete.
- Replacing the earlier uncontrolled UI workload with one real full-screen
  client reduced the observed framebuffer submissions from 96 to four, but it
  did not produce one panel frame for the one intended visual transition.
- Even this minimal client generated two small `240x21` submissions and two
  full-screen submissions. The private bridge converted/queued those as
  independent panel frames, and the physical panel still failed.
- The correct post-failure screenshot and still-running activity make an app
  rendering failure an inadequate explanation for the backlit-gray panel.
- This result strengthens the reconstructed plane-to-frame contract defect:
  submission count changed with the workload, transfer count followed it
  within trace-boundary work, and multiple submissions remained physically
  destructive even at a much lower count.

## Disproven assumptions

- “A real full-screen Android client necessarily reaches this driver as one
  full-screen framebuffer per visual state” is false on this GSI.
- “Reducing the redraw burst from 96 framebuffer submissions to four is by
  itself sufficient for panel stability” is false for this controlled event.

## Mistakes and process corrections

The closing verification rebuilt the APK in its recorded output directory.
Although it used the same source and signing key, ZIP entry timestamps changed
the APK SHA-256 and temporarily replaced the exact tested artifact. The
installed package still retained the tested bytes, so its `base.apk` was
pulled back to the recorded artifact path and verified as
`ecd5ee6178aaab159c6652e6ca237a53c2f7f15908bffd99c0fc6bb6af5ba332`.
Future verification should build into a temporary output directory rather
than overwrite a hash-identified tested artifact.

## Ending state

- Device mode and active slot: booted GSI on slot B.
- Running OS/build: unchanged from starting state.
- Partitions or sectors changed: none.
- Verified rollback path: no partition rollback currently required.
- Android `/data` change: `org.tclflip4.fullscreencontrol` remains installed
  and resumed. Roll back with
  `adb uninstall org.tclflip4.fullscreencontrol`.
- Physical display: user reports a gray panel with the backlight on after the
  controlled transition; Android's screenshot remains the correct
  green/magenta pattern.
- ADB/root/trace access: root adbd (`uid=0`, `u:r:su:s0`), writable tracefs,
  `tracing_on=0`, and empty `kprobe_events`.
- Uncommitted host artifacts: this finding, control-app source/build tooling,
  and prior-session changes.

## Safe next step

In a new session, compare the prepared driver controls against this trace and
select one single-variable experiment. Before any flash, re-confirm device
mode and slot, exact source and target hashes, GPT geometry, verified
pre-write backup, raw-LBA write/read-back commands, and rollback path.
