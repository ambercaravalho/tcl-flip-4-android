# 2026-11-01 01: Stock KaiOS display control

Status: complete

## Objective

Measure the known-good stock KaiOS contract at the private SPI bridge for one
deterministic D-pad event.

## Starting state

- The device had been restored to rooted stock KaiOS on slot B.
- Root ADB and tracefs kprobe access were available in the stock environment.
- The driver mechanism predicted that stock should provide one precomposed,
  full-screen RGB565 plane per visual frame.

## Artifacts

- Capture directory: `../../evidence/captures/stock-kaios/`
- Manifest timestamp: `2026-11-01T05:27:44Z`
- ADB serial: `830f21d`
- Runtime fingerprint:
  `TCL/Gflip_5G_TMO/Gflip_5G_TMO:14/UKQ1.241125.001/eng.jenkin.20251223.092955:user/test-keys`
- System fingerprint:
  `TCL/gflip5gtmo/gflip5gtmo:14/UKQ1.241125.001/jenkins12230928:user/test-keys`
- Primary trace:
  `../../evidence/captures/stock-kaios/spi-one-key.txt`

## Actions and observations

- Installed temporary kprobes on the unstripped plane, framebuffer, fence, TE,
  and SPI symbols.
- Injected one deterministic D-pad event.
- Recorded 16 animated plane updates.
- Every update used:
  - CRTC plane `240x320`
  - framebuffer `256x320`
  - pitch `512` bytes
  - `DRM_FORMAT_BGR565` (`BG16`)
- Recorded 18 SPI transfers, including work at trace boundaries.
- Median SPI transfer duration was 25.016 ms.
- Median TE interval was 16.746 ms.
- Fence waits were approximately 0.011-0.105 ms.
- Runtime properties showed `ro.debuggable=1`,
  `service.adb.root=1`, and `ro.adb.secure=1`.

## Conclusions

- Stock does not depend on partial ROI or on fitting one full transfer inside a
  60 Hz interval.
- Stock is stable because every animation frame reaches the private bridge as
  exactly one already flattened, full-screen RGB565 plane.
- The stock trace independently supports the reconstructed driver's assumed
  input contract.
- ODM debug properties are proven for this stock build only.

## Disproven assumptions

- Stock stability is not due to fewer redraws; one key event generated 16
  animation frames.
- Stock transfer time does not fit in the nominal 16.667 ms frame interval.

## Mistakes and process corrections

The first baseline collection scanned overly broad sysfs paths and could hang.
The capture script was narrowed to known display paths. Future baseline scripts
must avoid recursive or unbounded device-file scans.

## Ending state

- Complete known-good stock display baseline captured.
- Device remained on rooted stock KaiOS after the control.
- A matching GSI trace was still required.

## Safe next step

Flash a clean, identity-verified SDK-34 GSI, verify root/trace prerequisites at
runtime, and collect the same one-key trace before testing driver variants.
