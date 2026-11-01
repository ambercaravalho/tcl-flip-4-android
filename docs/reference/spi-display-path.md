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

The confirmed binary defect is a plane-to-frame contract violation. Whether it
fully explains a particular GSI boot remains gated on the missing GSI trace.

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

## Required test gate

Before claiming or flashing a kernel fix, prove on the GSI that:

1. one visual frame generates multiple `spi_display_update_fb` calls;
2. those calls have different plane geometry or content roles;
3. SPI transfer count follows plane-update count; and
4. one real full-screen client target changes the count and physical result.

Root ADB and tracefs write access must pass the runtime gate first. Prepared
immutable, coalescing, full-height-client, and lower-clock profiles are
experiments, not confirmed fixes.
