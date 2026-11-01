# 2026-10-31 05: Private SPI driver reconstruction

Status: complete

## Objective

Recover enough of TCL's private `msm_drm.ko` SPI additions to explain the GSI
flicker and define evidence gates for any kernel-side experiment.

## Starting state

- GSI families and high-level display properties had failed to remove flicker.
- Correct screenshots showed that logical composition remained intact.
- Exact matching TCL kernel source was not available.

## Artifacts

- Stock module: `/vendor_dlkm/lib/modules/msm_drm.ko`
- Size: `3,669,800` bytes
- SHA-256:
  `39f972853c5acb061a3964a48cf6bf0ff375b55dc216e537c69e76c290755065`
- Build ID: `16a087f90cb9910424c673719e9c575b97d637a4`
- Vermagic:
  `6.1.78-android14-11-maybe-dirty-gki SMP preempt mod_unload modversions aarch64`
- Downloaded disclosures now under `../../artifacts/downloads/`:
  - `OT_T440G_20260324`, SHA-256
    `605bfce7f0a887919b067a3ed5f314f6572c42f58ecda2d5d9f73ba7d8207a3d`
  - `OT_gflip65dish_20260309`, SHA-256
    `49604211c4d529cc0fd6d868e1b27eed3c9d79dad28fdf972ed2865b53b1e2f6`

## Actions and observations

- The similarly named TCL disclosures contained generic 5.15 and 4.19 trees,
  not the shipped 6.1 module's SPI/SDE source.
- The unstripped module retained symbols and relocations sufficient to recover
  the private path.
- `_sde_plane_atomic_update()` calls `spi_display_update_fb()` for every DRM
  plane.
- The call passes source address, CRTC dimensions, framebuffer dimensions,
  pitch, and fourcc, but no plane position, crop, alpha, blend mode, z-order,
  damage, or composed CRTC output.
- Every accepted plane is converted/copied to destination `(0,0)` in one global
  full-screen RGB565 staging buffer and queues a transfer.
- The worker snapshots that buffer into a second immutable frame under a mutex,
  waits for TE, programs a full-panel window, and performs synchronous
  `spi_sync()`.
- The path has no packed ROI transport. Every kickoff sends 153,600 bytes.
- A 50 MHz transfer has a wire-time floor of 24.576 ms; per-plane queueing
  multiplies this cost.

## Conclusions

- The stock binary contains a plane-to-frame contract violation: it treats each
  atomic plane update as an already composed full display frame.
- A producer/DMA ownership race is not the leading explanation because the
  worker snapshots an immutable full frame and uses synchronous transfer.
- A valid fix must provide one composed 240x320 RGB565 image per atomic commit,
  preserve pitch/format/fences, and coalesce superseded work.
- Source reconstruction is evidence of mechanism, but a GSI-side trace is
  still required before claiming it is the observed runtime cause.

## Disproven assumptions

- The similarly named TCL source archives are not the T440W module source.
- Malformed partial-window packing is not the shipped path; it is full-frame.
- Basic SPI serialization alone does not solve the composition contract.

## Mistakes and process corrections

Binary patch variants were prepared before root ADB/tracefs access was reliably
verified on the GSI. Future test plans must prove the diagnostic prerequisite
first and must not treat prepared patches as confirmed fixes.

## Ending state

- Instrumentation and hash-locked experimental variants existed on the host.
- No kernel-side fix was confirmed.
- The decisive GSI plane/transfer trace remained missing.

## Safe next step

Capture a deterministic stock control trace, then obtain the same trace on the
clean GSI. Only patch if the GSI demonstrates the predicted multi-plane,
multi-transfer behavior.
