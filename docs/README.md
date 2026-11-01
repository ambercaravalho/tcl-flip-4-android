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

Last recorded device state: Android 14 `treble_a64_bvN-userdebug` on slot B,
captured at `2026-11-01T15:20:28Z`. It boots, but redraws still cause severe
physical-panel flicker. ADB is available, but root ADB and tracefs write access
are not: runtime reported `ro.debuggable=0`, `service.adb.root=0`, and
`adb root` refused. The ODM image's requested values did not override the
already-frozen read-only properties.

Lineage testing used both free `super` regions and overwrote the old stock
system sectors in Region A. A metadata-only rollback is no longer sufficient;
restoring stock requires the full eMMC backup or the affected system sectors.

The next safe research step is to fix and verify the debug/root property path
without assuming ODM wins, then capture an equivalent SPI trace on the GSI.
Do not patch the display driver merely because the reconstructed mechanism is
plausible; the GSI-side trace gate remains open.

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
