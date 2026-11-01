# 2026-10-31 03: First Android flash and boot

Status: complete

## Objective

Boot the prepared single-extent TrebleDroid Android 14 userspace while
preserving the stock kernel, vendor BSP, and stock system sectors.

## Starting state

- Phone was placed in EDL mode (`05c6:9008`), active slot B.
- Stock KaiOS occupied the device.
- The intended system payload fit only in unused Region B.
- Full eMMC backup and a fresh pre-flash partition set were available.

## Artifacts

Pre-flash files now under `../../artifacts/backups/pre-flash-android/`:

- `odm_b.img`:
  `b182c49c9f0c58c7a21038c8c06a2b0635f2cfe74afce9603db8b45f37dd1e39`
- `super_meta.img`:
  `f6e5b3acfd04b3a814ce12d3e114362d30ed67d5fb07dddc4d3363cf0f26f37f`
- `vbmeta_b.img`:
  `765e0086229261b6112c28147345f451977d988ec2bb6417744176c80d95b08c`
- `vbmeta_system_b.img`:
  `cda8beec6039caf34396842c1ddeb17fab389b2b607d134a71013406f2edccc2`

## Actions and observations

- Backed up current `super` metadata, ODM, and both vbmeta images.
- Wrote prepared `odm_b`, `vbmeta_b`, `vbmeta_system_b`, `super` metadata, and
  `system_b` using raw-sector writes without `--skipresponse`.
- Used these exact raw vbmeta starts:
  - `vbmeta_system_b`: LBA `2080768`
  - `vbmeta_b`: LBA `3377152`
- Read targets back and compared them before reboot.
- Android reached lock screen and launcher. The boot chain, ABI choice,
  zero-length overlays, policy bridge, and basic keypad path were viable.
- The physical panel flickered severely during redraw. It could be stable while
  nothing moved.
- USB debugging/root access was not reliably established during the first boot.

## Conclusions

- Full Android userspace can boot on the locked T440W with the stock Android 14
  kernel and Qualcomm BSP.
- Name-based EDL writes are not acceptable for the two vbmeta partitions on
  this loader; raw `ws` plus read-back is the known-good method.
- The primary bringup blocker moved from boot/AVB to physical display
  presentation.

## Disproven assumptions

- “A booting GSI will have a usable display because the stock Android composer
  HAL is present” is false.
- “Requested USB debug properties guarantee immediate usable ADB” was not
  supported by this boot.

## Mistakes and process corrections

Runtime ADB/root properties were not captured as a formal post-boot gate.
Future flashes must verify the exact running build and debug state before
planning root-only diagnostics.

## Ending state

- Android booted on slot B.
- Stock system sectors were still preserved at this point.
- UI was visible but severe redraw-triggered flicker remained.
- Immediate rollback was still possible by restoring the small metadata/ODM/
  vbmeta set.

## Safe next step

Capture correct screenshots, input events, compositor state, and controlled
one-variable display experiments before modifying the kernel path.
