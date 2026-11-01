# 2026-10-31 04: GSI display experiments

Status: complete

## Objective

Localize the severe physical-panel flicker and determine whether it comes from
the GSI version, input, SurfaceFlinger, composition policy, or the lower display
path.

## Starting state

- Android could boot on slot B.
- A static physical frame was stable.
- Any D-pad-triggered redraw caused severe flicker or corruption.
- USB/ADB availability varied between builds and boots.

## Artifacts

- Host and device captures now live under `../../evidence/`.
- Display preparation profiles remain in
  `../../tooling/scripts/prepare_gsi.py` for reproducibility, not as defaults.
- Detailed mechanism work continued in
  [`2026-10-31-05-spi-driver-reconstruction.md`](2026-10-31-05-spi-driver-reconstruction.md).

## Actions and observations

- Android 15 TrebleDroid booted and flickered. It was an SDK mismatch and was
  not valid as the intended final baseline.
- Clean Android 14 TrebleDroid booted after userdata reset and flickered the
  same way.
- LineageOS 21/crDroid on SDK 34 also flickered.
- Host `screencap` remained correct while the physical panel was wrong.
- A physical D-pad press produced one clean key-down/up pair, ruling out input
  bounce as the redraw source.
- A 30 FPS cap removed random resizing but not flicker. A 20 FPS cap changed
  its apparent rate but did not fix it.
- Disabling Android UI animations improved usability but each update still
  flickered.
- Restoring stock UBWC/offline-rotator properties did not help.
- Forcing all-client composition produced random center pixels rather than a
  valid stable image.
- Disabling HWC partial update froze an old physical frame while Android stayed
  alive.
- Disabling speculative fences and SurfaceFlinger unsignaled-buffer latching
  made no improvement.
- During version/build changes, recovery reported “Can't load Android system.”
  The working explanation was userdata/FBE incompatibility after downgrade.
- The larger two-extent Lineage test overwrote Region A, ending the original
  metadata-only rollback guarantee.

## Conclusions

- Correct screenshots plus bad glass place the defect after logical
  composition, in HWC/DRM/RGB565/SPI presentation.
- The defect is not specific to SDK 35, Launcher3, one GSI family, keypad
  bounce, animation volume, speculative fences, or SF unsignaled latching.
- Timing affects presentation severity but is not itself a demonstrated root
  cause.
- The display path can retain a valid old frame when commits are suppressed.

## Disproven assumptions

- Android 14 vendor/API matching alone does not fix the display.
- Lower render rate does not make the SPI presentation correct.
- “All-client composition” is not a fix unless the private SPI bridge receives
  the correct full-screen buffer exactly once.
- The former instant rollback procedure is no longer sufficient after Region A
  was used.

## Mistakes and process corrections

- Android 15 was tested before the pipeline strictly validated SDK 34.
- Several unrelated display properties accumulated too easily. Diagnostic
  profiles must be explicit, one-variable, and excluded from the default.
- Version changes touched userdata without a sufficiently prominent rollback
  and FBE warning.

## Ending state

- Android remained bootable with the original redraw-triggered flicker.
- Region A stock system sectors had been overwritten by Lineage testing.
- Full eMMC restore, not only metadata restore, was now required for stock.
- Animations-off was retained only as a usability preference for this device.

## Safe next step

Recover the private SPI display path from the unstripped stock module, compare
its assumed input contract with Android's plane behavior, and design trace
gates before patching.
