# Capture a display baseline and SPI trace

Use this runbook only on a booted, authorized ADB device. A baseline capture can
run without full root, but kernel kprobes require root adbd and writable
tracefs.

## Record the starting state

Before capture, record the running fingerprint, SDK, slot, exact flashed image
hashes, current display symptom, and whether the device is stock or GSI.

## Verify the privilege gate

```bash
adb shell getprop ro.debuggable
adb shell getprop ro.force.debuggable
adb shell getprop service.adb.root
adb shell id
adb root
adb wait-for-device
adb shell id
adb shell 'test -w /sys/kernel/tracing/kprobe_events && echo writable'
```

If root is refused or `kprobe_events` is not writable, stop. Capture the failed
gate in the session finding. Do not continue with a trace plan based on ODM
properties.

## Static baseline

```bash
tooling/scripts/capture-display-baseline.sh \
  evidence/captures/<session-name>
```

The output includes manifests, properties, process/module state, DRM and
SurfaceFlinger state, logs, and a host-side screenshot. Avoid broad recursive
sysfs scans; the script uses bounded, known display paths.

## Deterministic one-key SPI trace

Keep the device on a known static screen. Start:

```bash
tooling/scripts/capture-spi-trace.sh 10 \
  evidence/captures/<session-name>/spi-one-key.txt
```

During the ten-second window, press one D-pad direction once. Do not press
other keys or change the screen.

Analyze:

```bash
tooling/scripts/analyze-spi-trace.py \
  evidence/captures/<session-name>/spi-one-key.txt
```

Record plane count and geometry, framebuffer dimensions, pitch, fourcc, fence
waits, TE intervals, SPI transfer count, and transfer durations.

## Comparison gate

Compare the GSI result with
`../../evidence/captures/stock-kaios/spi-one-key.txt`. The stock control was 16
full-screen BG16 plane updates and 18 transfers, with median 25.016 ms SPI and
16.746 ms TE intervals.

The first GSI comparison is
`../../evidence/captures/gsi-rooted/spi-one-key.txt`: 96 framebuffer
submissions, including 93 full-screen and three `31x14` `AB24` planes, produced
98 frame transfers plus ten separately identified panel-window commands.

The controlled full-screen client is recorded in
`../../evidence/captures/gsi-fullscreen-control/spi-one-key.txt`: one intended
transition produced four framebuffer submissions and five frame transfers,
then left the physical panel backlit gray while the Android screenshot
remained correct. This completes the comparison prerequisite; it does not
validate a patch.

Prepared profiles are documented in
[`../reference/spi-display-path.md`](../reference/spi-display-path.md), but
they are not established fixes. Before testing one, begin a new finding and
apply every write, read-back, backup, and rollback gate in the applicable
flashing runbook.
