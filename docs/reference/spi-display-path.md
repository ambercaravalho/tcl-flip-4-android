# SPI display path reference

## Physical topology

- Panel: Sitronix ST7789P3
- TCL panel string: `ST7789P3:YKL:240*320:AUA0320206C1`
- Resolution: `240x320`
- Command line:
  `msm_drm.spi_display0=qcom,mdss_spi_st7789p3_qvga_cmd`
- SPI mode: 0
- Stock clock: 50 MHz
- Transport format: RGB565, 16 bits per pixel
- Full transfer: 153,600 bytes
- Minimum wire time at 50 MHz: 24.576 ms
- Android client buffers observed as 240x320 content in 256-pixel,
  1024-byte RGBA/XRGB rows

## Shipped module

- Path: `/vendor_dlkm/lib/modules/msm_drm.ko`
- SHA-256:
  `39f972853c5acb061a3964a48cf6bf0ff375b55dc216e537c69e76c290755065`
- Build ID: `16a087f90cb9910424c673719e9c575b97d637a4`
- Vermagic: `6.1.78-android14-11-maybe-dirty-gki`

No exact matching public source has been found. The unstripped binary is the
authoritative implementation for this device. Evidence:
[`2026-10-31-05-spi-driver-reconstruction.md`](../findings/2026-10-31-05-spi-driver-reconstruction.md).

## Reconstructed contract

`_sde_plane_atomic_update()` calls `spi_display_update_fb()` once for every
plane. The private call receives dimensions, pitch, and fourcc but not position,
crop, alpha, blend, z-order, damage, or a composed CRTC output. It converts each
plane into the same full-screen RGB565 buffer at `(0,0)` and queues a complete
panel transfer.

The worker copies that staging frame to an immutable backup under a mutex,
waits for TE, programs a full-screen `CASET`/`RASET`/`RAMWR` window, and uses
synchronous `spi_sync()`. There is no packed ROI path.

The confirmed binary defect is a plane-to-frame contract violation. The GSI
trace below directly demonstrates that violation on the flickering boot.

## Stock control

One deterministic D-pad event on stock KaiOS produced:

- 16 plane updates
- every plane `240x320`
- every framebuffer `256x320`, pitch 512
- every format `DRM_FORMAT_BGR565` (`BG16`)
- 18 SPI transfers including boundary work
- median SPI transfer 25.016 ms
- median TE interval 16.746 ms

Stock is stable because the bridge receives one precomposed full-screen RGB565
plane per animation frame, not because the transfer fits inside 60 Hz.
Evidence:
[`2026-11-01-01-stock-kaios-control.md`](../findings/2026-11-01-01-stock-kaios-control.md).

## GSI comparison

One deterministic D-pad-down event (`code=108`) on the Android 14 GSI
produced:

- 102 plane-update entries and 96 calls into `spi_display_update_fb`
- 93 full-screen `240x320` submissions
- three `31x14` submissions with mixed `256x32` and `256x320` buffers
- every submission in `AB24` with 1024-byte pitch
- repeated paired full-screen submissions within the same atomic commits
- 98 completed frame transfers from `spi_kickoff_thread`
- ten command transfers from two full-window resets
- median SPI duration 24.894 ms and median TE interval 16.789 ms

The 96 submissions versus 98 frame transfers differ by trace-boundary work,
while the ten short panel-window commands are accounted for separately. This
is materially different from stock's one full-screen, precomposed `BG16`
submission per animation frame.

Evidence:
[`2026-11-01-03-gsi-adb-root.md`](../findings/2026-11-01-03-gsi-adb-root.md)
and `../../evidence/captures/gsi-rooted/spi-one-key.txt`.

## Full-screen client control

A minimal hardware-accelerated full-screen Android client initially produced a
correct, stable physical blue/yellow pattern. One D-pad event changed the
logical output to green/magenta and produced:

- six plane updates;
- four framebuffer submissions: two `240x21` and two `240x320`;
- `AB24` with 1024-byte pitch for all four submissions;
- five frame transfers plus five commands from one full-window reset.

The physical panel showed the new pattern briefly, jumped around, and ended
backlit gray. Android's post-failure screenshot remained the correct
green/magenta output. The workload reduced the prior GSI burst from 96
framebuffer submissions to four, but still did not deliver one composed frame
for the one intended state change, and the panel remained unstable.

This closes the pre-patch trace gate: submission geometry and count change
with the Android workload, frame transfers follow submissions within boundary
work, and multiple independent submissions remain destructive even for a
controlled full-screen client.

Evidence:
[`2026-11-01-04-fullscreen-client-control.md`](../findings/2026-11-01-04-fullscreen-client-control.md)
and `../../evidence/captures/gsi-fullscreen-control/spi-one-key.txt`.

The root/tracefs gate passes through the GSI's built-in Rooted debugging
control. Prepared immutable, coalescing, full-height-client, and lower-clock
profiles remain experiments, not confirmed fixes; each still requires a
single-variable, hash-locked, read-back-verified test.

## Immutable driver control

The one-instruction immutable profile prevents framebuffer updates from
replacing the driver's RGB565 staging contents while preserving queueing, TE,
and synchronous SPI transfers. On the same full-screen one-key workload it
produced:

- the same six plane updates;
- the same four framebuffer submissions: two `240x21` and two `240x320`;
- five frame transfers plus five full-window commands;
- median TE interval `16.787 ms`;
- full-frame SPI duration up to `25.087 ms`.

Android correctly changed from blue/yellow to green/magenta, but the physical
panel remained stable gray because no current content reached the staging
frame. The unchanged submission/transfer workload no longer jumped or
flickered. Transfer cadence alone is therefore insufficient to explain the
failure; changing independent per-plane staging contents is required for the
observed physical instability.

The immutable profile is a diagnostic control, not a fix. It was restored
byte-for-byte to the stock module and original vbmeta after testing.

The original prepared profile vbmeta was also found unsafe for the current
GSI because it contained a stale ODM descriptor. Any later profile must derive
top-level vbmeta from bytes proven identical to the current device and compare
all untargeted descriptors before writing.

Evidence:
[`2026-11-01-05-spi-driver-control-selection.md`](../findings/2026-11-01-05-spi-driver-control-selection.md)
and `../../evidence/captures/gsi-spi-immutable/spi-one-key.txt`.
