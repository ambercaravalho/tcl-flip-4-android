# Documentation

This repository records the effort to run Android 14 on the TCL Flip 4 5G
(T440W, `gflip5gtmo` / `pitti_32go`). Documentation is split by purpose:

- [`findings/`](findings/) contains chronological records of what happened in
  each research or device session. Completed findings are historical evidence.
- [`reference/`](reference/) contains facts that remain useful across sessions.
  Each non-obvious claim points back to a finding or captured artifact.
- [`runbooks/`](runbooks/) contains guarded, repeatable procedures. A runbook is
  not evidence that a procedure succeeded on a particular boot.

## Community documentation

The accepted `v0.1.0` profile is Android 14 on slot B, locked/green and
SELinux-enforcing, with a stable display, physical keypad/C9 cursor, microG,
Aurora Store, authenticated non-root ADB, and Magisk-managed application root.
It has been validated on one reference T440W.

- [Install `v0.1.0`](guides/install-v0.1.0.md)
- [Use the ROM](guides/using-the-rom.md)
- [Backup and restore](runbooks/backup-and-restore.md)
- [Generic flash protocol](runbooks/flash-and-verify.md)

Community installers should use the versioned guide and release manifest.
Findings document how the result was reached; they are not a substitute for a
frozen release procedure.

## Maintainer documentation

- [Build and publish a release](runbooks/build-and-release.md)
- [Prepare a GSI](runbooks/prepare-gsi.md)
- [Release components](reference/release-components.md)
- [Partitions and AVB](reference/partitions-and-avb.md)

The accepted image set is byte-reproducible and its AVB chain verifies, but the
chain is anchored in public AOSP test keys. Region A was overwritten during
development, so restoring the reference phone to stock requires its verified
full eMMC backup rather than a metadata-only rollback.

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
- [`2026-11-01-06-spi-coalescing-control.md`](findings/2026-11-01-06-spi-coalescing-control.md)
- [`2026-11-01-07-spi-full-height-client.md`](findings/2026-11-01-07-spi-full-height-client.md)
- [`2026-11-01-08-persistent-client-composition.md`](findings/2026-11-01-08-persistent-client-composition.md)
- [`2026-11-01-09-physical-keypad-navigation.md`](findings/2026-11-01-09-physical-keypad-navigation.md)
- [`2026-11-01-10-rooted-release-stack.md`](findings/2026-11-01-10-rooted-release-stack.md)

Use [`findings/SESSION_TEMPLATE.md`](findings/SESSION_TEMPLATE.md) for the next
session.

## Reference

- [`reference/device-and-abi.md`](reference/device-and-abi.md)
- [`reference/partitions-and-avb.md`](reference/partitions-and-avb.md)
- [`reference/spi-display-path.md`](reference/spi-display-path.md)
- [`reference/edl-loader.md`](reference/edl-loader.md)
- [`reference/release-components.md`](reference/release-components.md)

## Runbooks

- Community: [`runbooks/flash-and-verify.md`](runbooks/flash-and-verify.md)
  and [`runbooks/backup-and-restore.md`](runbooks/backup-and-restore.md)
- Maintainer: [`runbooks/prepare-gsi.md`](runbooks/prepare-gsi.md) and
  [`runbooks/build-and-release.md`](runbooks/build-and-release.md)
- Research only:
  [`runbooks/capture-display-trace.md`](runbooks/capture-display-trace.md) and
  [`runbooks/enable-gsi-root-adb.md`](runbooks/enable-gsi-root-adb.md)
