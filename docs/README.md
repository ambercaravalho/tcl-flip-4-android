# Documentation

This repository records the effort to run Android 14 on the TCL Flip 4 5G
(T440W, `gflip5gtmo` / `pitti_32go`). Documentation is split by purpose:

- [`findings/`](findings/) contains chronological records of what happened in
  each research or device session. Completed findings are historical evidence.
- [`reference/`](reference/) contains facts that remain useful across sessions.
  Each non-obvious claim points back to a finding or captured artifact.
- [`runbooks/`](runbooks/) contains guarded, repeatable procedures. A runbook is
  not evidence that a procedure succeeded on a particular boot.

## Current state

Last recorded device state: Android 14 `treble_a64_bvN-userdebug` on slot B.
The GSI's built-in **Rooted debugging** setting was enabled through Developer
options. Runtime then provided root adbd and writable tracefs while
`ro.debuggable` and `ro.force.debuggable` remained `0`. No partition write was
required.

The first equivalent GSI SPI trace is now captured. One D-pad event produced
96 framebuffer submissions: 93 full-screen and three `31x14`, all `AB24` with
1024-byte pitch. It generated 98 frame SPI transfers plus ten panel-window
commands. This contrasts with stock's 16 full-screen `BG16` submissions and 18
frame transfers, and directly confirms the multi-plane/format contract
mismatch on the flickering GSI.

The controlled full-screen-client gate is also complete. One intended visual
transition produced four framebuffer submissions—two `240x21` and two
`240x320`—and five frame transfers. The physical panel briefly changed, then
jumped and ended backlit gray, while Android's screenshot remained correct.
Reducing the burst from 96 submissions to four was not sufficient; the private
bridge still received multiple independent planes instead of one composed
frame.

The immutable driver control preserved the same four submissions and five
frame transfers while preventing new per-plane contents from replacing the
RGB565 staging frame. Android still rendered correctly, and the physical panel
remained stable gray instead of jumping. This rules out transfer cadence alone
as a sufficient explanation and strengthens the content-contract diagnosis.
The control was fully restored; the device again runs the stock module and
original vbmeta with correct, stable static output.

Lineage testing used both free `super` regions and overwrote the old stock
system sectors in Region A. A metadata-only rollback is no longer sufficient;
restoring stock requires the full eMMC backup or the affected system sectors.

The next safe research step is the smaller coalescing control. Its vbmeta must
be rebuilt from the exact current image: the old prepared profile vbmeta was
found to contain a stale ODM descriptor. A prepared variant is not a confirmed
fix; all raw-LBA, backup, rollback, descriptor-comparison, and read-back gates
still apply before any write.

## Read this before device work

1. Read the latest applicable file in [`findings/`](findings/).
2. Read the relevant reference and runbook.
3. Confirm the phone's current mode, active slot, image identity, and available
   backups with the user.
4. Record the new session's starting state before changing anything.

## Do not infer

- Do not infer runtime ADB root from properties written into an image. After
  every boot, check `ro.debuggable`, `ro.force.debuggable`,
  `service.adb.root`, `adb shell id`, `adb root`, and the exact permissions
  needed for the planned capture.
- Do not trust an EDL success message. Writes omit `--skipresponse`; every
  target is read back with `--skipresponse` and compared byte-for-byte before
  reboot.
- Do not infer image identity from a filename. Record the source SHA-256,
  fingerprint, SDK, ABI, build manifest, and hashes of flashed artifacts.
- Do not assume Option A's metadata-only rollback remains valid. Region A was
  overwritten during the two-extent Lineage test.
- Do not repeat a disproven display override without naming the earlier result
  and stating what new variable the repeat isolates.

## Chronological findings

- [`2026-07-17-01-root-project-inheritance.md`](findings/2026-07-17-01-root-project-inheritance.md)
- [`2026-10-31-01-repository-reorientation.md`](findings/2026-10-31-01-repository-reorientation.md)
- [`2026-10-31-02-offline-groundwork.md`](findings/2026-10-31-02-offline-groundwork.md)
- [`2026-10-31-03-first-android-flash.md`](findings/2026-10-31-03-first-android-flash.md)
- [`2026-10-31-04-display-experiments.md`](findings/2026-10-31-04-display-experiments.md)
- [`2026-10-31-05-spi-driver-reconstruction.md`](findings/2026-10-31-05-spi-driver-reconstruction.md)
- [`2026-11-01-01-stock-kaios-control.md`](findings/2026-11-01-01-stock-kaios-control.md)
- [`2026-11-01-02-clean-gsi-debugging.md`](findings/2026-11-01-02-clean-gsi-debugging.md)
- [`2026-11-01-03-gsi-adb-root.md`](findings/2026-11-01-03-gsi-adb-root.md)
- [`2026-11-01-04-fullscreen-client-control.md`](findings/2026-11-01-04-fullscreen-client-control.md)
- [`2026-11-01-05-spi-driver-control-selection.md`](findings/2026-11-01-05-spi-driver-control-selection.md)

Use [`findings/SESSION_TEMPLATE.md`](findings/SESSION_TEMPLATE.md) for the next
session.

## Reference

- [`reference/device-and-abi.md`](reference/device-and-abi.md)
- [`reference/partitions-and-avb.md`](reference/partitions-and-avb.md)
- [`reference/spi-display-path.md`](reference/spi-display-path.md)
- [`reference/edl-loader.md`](reference/edl-loader.md)

## Runbooks

- [`runbooks/prepare-gsi.md`](runbooks/prepare-gsi.md)
- [`runbooks/flash-and-verify.md`](runbooks/flash-and-verify.md)
- [`runbooks/backup-and-restore.md`](runbooks/backup-and-restore.md)
- [`runbooks/capture-display-trace.md`](runbooks/capture-display-trace.md)
- [`runbooks/enable-gsi-root-adb.md`](runbooks/enable-gsi-root-adb.md)
