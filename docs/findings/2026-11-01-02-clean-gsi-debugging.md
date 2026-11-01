# 2026-11-01 02: Clean GSI capture and debugging failure

Status: complete

## Objective

Return to a clean Android 14 GSI, establish the GSI-side display baseline, and
obtain the root/trace access required for a stock-versus-GSI SPI comparison.

## Starting state

- A stock control trace had been captured.
- A clean SDK-34 `a64_bvN` GSI and patched ODM were prepared.
- Documentation and planning assumed ODM `ro.debuggable=1` and
  `service.adb.root=1` would produce root adbd as they had on stock KaiOS.

## Artifacts

- Capture directory: `../../evidence/captures/gsi-clean/`
- Manifest timestamp: `2026-11-01T15:20:28Z`
- ADB serial: `830f21d`
- Active slot: B
- Runtime fingerprint:
  `TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys`
- Build flavor reported:
  `treble_a64_bvN-userdebug`

## Actions and observations

- The clean Android 14 GSI was flashed and read back successfully.
- Android booted; physical display flicker was unchanged.
- ADB became available through the diagnostic/ConfigFS path.
- Runtime property capture showed:
  - `ro.debuggable=0`
  - `ro.force.debuggable=0`
  - `service.adb.root=0`
  - `ro.adb.secure=0`
- `adb root` refused and directed enabling root in Developer options.
- The shell lacked the tracefs write access needed to install kprobes.
- Kernel log showed the ODM/property-loading attempt but also:
  `Could not set 'ro.debuggable' to '1' ... Read-only property was already set`.
- SELinux audit entries were permissive, so permissive policy did not make the
  frozen read-only property change succeed.
- No equivalent GSI SPI trace was captured.

## Conclusions

- ODM debug properties are not sufficient on this GSI. `ro.debuggable` was
  fixed earlier by the GSI property surface and could not be overridden later.
- A running `adbd` service and `ro.adb.secure=0` do not prove root ADB.
- Permissive SELinux does not bypass Android's read-only property semantics.
- Any trace or patch plan that requires root must verify root and exact tracefs
  permissions after boot before proceeding.
- The SPI mechanism remains strongly supported by binary reconstruction and the
  stock control, but its GSI-side runtime gate is still unmet.

## Disproven assumptions

- “ODM loads last, therefore its `ro.debuggable=1` overrides system” is false
  for this GSI.
- “A `userdebug` build flavor means runtime `ro.debuggable=1`” is false here.
- “ADB available” is not equivalent to “root ADB available.”
- “Permissive SELinux implies tracefs write access” is false.

## Mistakes and process corrections

The work repeatedly planned root-only actions without first checking runtime
root. The documentation also stated the ODM inference as fact. This session
stopped without further writes when the user requested a pause.

New mandatory gate after every boot:

```bash
adb shell getprop ro.debuggable
adb shell getprop ro.force.debuggable
adb shell getprop service.adb.root
adb shell id
adb root
adb shell id
adb shell 'test -w /sys/kernel/tracing/kprobe_events && echo writable'
```

The observed output, not the image recipe, decides whether root-only work can
continue.

## Ending state

- Android 14 GSI booted on slot B.
- Original redraw-triggered display flicker remained.
- ADB worked without root; tracefs instrumentation was blocked.
- Region A rollback caveat remained in force.
- No further device write occurred after the stop request.

## Safe next step

Design and verify an earlier debug/root mechanism appropriate to the GSI
property-loading order. Reboot, run the mandatory gate, and only then attempt
the GSI SPI trace.
