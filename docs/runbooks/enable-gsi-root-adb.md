# Enable GSI rooted debugging

Use this only when the booted GSI provides Lineage/crDroid
`adbroot_service`. It does not apply to stock KaiOS or to a generic AOSP GSI
without that service.

## Confirm support

```bash
adb shell service list | grep adbroot_service
adb shell service call adbroot_service 1
adb shell service call adbroot_service 3
```

Transaction 1 is `isSupported()` and must return `1`. Transaction 3 is
`getEnabled()`. Do not use transaction 2 from an ADB shell: `setEnabled()`
requires the system UID and correctly rejects shell callers.

## Expose Developer options

Complete Android setup first. If this is a disposable bringup device whose
setup flow cannot be operated on the physical panel, record the change before
setting:

```bash
adb shell settings put global device_provisioned 1
adb shell settings put secure user_setup_complete 1
adb shell settings put global development_settings_enabled 1
```

Open Developer options:

```bash
adb shell am start -a android.settings.APPLICATION_DEVELOPMENT_SETTINGS
```

Use Settings search for **Rooted debugging**, then enable:

> Rooted debugging — Allow running Android debugging as root

The Settings process is the authorized system caller for
`adbroot_service.setEnabled(true)`.

## Runtime gate

Allow adbd to reconnect, then run:

```bash
adb wait-for-device
adb shell service call adbroot_service 3
adb root
adb wait-for-device
adb shell id
adb shell getprop ro.debuggable
adb shell getprop ro.force.debuggable
adb shell getprop service.adb.root
adb shell 'test -w /sys/kernel/tracing/kprobe_events && echo writable'
```

The observed successful GSI path had `uid=0`, `service.adb.root=1`, and
writable `kprobe_events` even though both read-only debug properties remained
`0`. Treat the live identity and permission checks as the gate.

## Failure handling

- If `isSupported()` returns false or the service is absent, stop. Do not
  infer that an ODM property or a `userdebug` flavor enables root.
- If Settings cannot display Developer options, finish or explicitly bypass
  setup before changing boot images.
- Do not add `/force_debuggable` to `init_boot` on a locked/green device and
  expect it to work. AOSP loads that debug ramdisk only for an
  unlocked/orange verified-boot state.

Evidence:
[`2026-11-01-03-gsi-adb-root.md`](../findings/2026-11-01-03-gsi-adb-root.md).
