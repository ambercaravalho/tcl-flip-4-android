# Backup and restore

Backups can contain personal data and device identifiers. They remain ignored
under `artifacts/backups/` and should also be copied to protected storage
outside the repository.

## Full eMMC backup

With the phone in EDL:

```bash
tooling/scripts/check-device.sh
tooling/scripts/backup.sh artifacts/backups/flip4-full-emmc.img
```

The script performs a read-only full dump, checks 512-byte alignment, and
requires both primary and backup GPT signatures. Record the final SHA-256 and
copy the image off the working machine.

The repository path may be a symlink to the prior `tcl-flip-4-root` workspace.
Verify it resolves before relying on it:

```bash
test -e artifacts/backups/flip4-full-emmc.img
shasum -a256 artifacts/backups/flip4-full-emmc.img
```

## Before every write session

Create a timestamped directory and read back every target that will change.
Use raw sectors when a name-based operation is known to be unreliable. Record:

- device identity and GPT;
- active slot;
- raw LBA and sector count;
- output path and SHA-256;
- source image and SHA-256;
- expected rollback command.

Reads include `--skipresponse`.

## Restore scope

Choose the smallest restore that actually covers all modified bytes:

- A single-partition restore is valid only when no linked verification metadata
  or dynamic-partition metadata also changed.
- The original single-extent TrebleDroid test could be reverted with `super`
  metadata, ODM, and vbmeta images because stock Region A was untouched.
- That shortcut is no longer valid after the two-extent Lineage test overwrote
  Region A. Current stock rollback must restore Region A/system data from the
  full backup in addition to metadata and AVB state, or restore the entire
  verified eMMC image.

Never restore a whole image without re-confirming that it belongs to the same
physical unit and has a valid GPT at both ends.

## Restore verification

Writes omit `--skipresponse`. Read restored targets back with
`--skipresponse`, compare exact bytes/hashes, and only then leave EDL. A
software reset is unreliable. On the non-removable-battery T440W, hold Power
for roughly ten seconds until vibration/reboot.

See [`flash-and-verify.md`](flash-and-verify.md) and
[`../reference/partitions-and-avb.md`](../reference/partitions-and-avb.md).
