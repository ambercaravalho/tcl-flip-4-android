# Backup and restore

The guided installer creates the required backups automatically. This page is
for manual recovery.

Backups contain personal data and device identifiers. Keep them in protected
storage outside the repository and never publish them.

## Full backup

With the phone in EDL:

```bash
tooling/scripts/backup.sh artifacts/backups/t440w-full-emmc.img
```

The script reads the complete eMMC, validates both GPT copies, hashes the
image, and creates an adjacent receipt bound to the phone's chip and eMMC
serials. Preserve both files.

## Target backups

Before each write session, record and back up every modified raw range. The
record must include device identity, GPT, active slot, LBA, sector count,
output hash, source hash, and rollback command.

Reads use `--skipresponse`.

## Restore

Restore only from a verified backup belonging to the connected phone. Region A
was overwritten during development, so a metadata-only stock rollback is not
sufficient; stock recovery requires the full backup.

Writes omit `--skipresponse`. Read each restored range back with
`--skipresponse`, compare exact bytes, and leave EDL only after every match.
For protocol details, see [Flash and verify](flash-and-verify.md).

On the non-removable-battery T440W, hold Power for about ten seconds to leave
EDL and reboot.
