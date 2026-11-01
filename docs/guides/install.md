# Install T440W Android

This installs the latest supported release on slot B of the TCL Flip 4 5G /
Go Flip 5G model T440W.

EDL writes can permanently brick a phone. Stop if the installer reports a
different model, HWID, storage layout, active slot, image hash, or read-back.
Returning to stock requires the same phone's full verified eMMC backup.

## Requirements

- a T440W already active on slot B
- macOS or Linux with Python 3, ADB, and about 65 GiB free
- a direct, data-capable USB connection
- protected storage outside this repository for the backup

## Run

From the repository root:

```bash
tooling/scripts/install-release.sh
```

The installer:

1. sets up its local tools and downloads the latest supported release;
2. verifies every image, the phone identity, GPT, and active slot;
3. creates a full device-bound backup and asks you to protect it;
4. backs up every target range;
5. asks for typed confirmation, flashes in safe order, and reads every range
   back before allowing reboot; and
6. can run the post-boot security checks.

Rerun the same command after an interruption. It revalidates saved state and
the connected phone before resuming.

## Enter EDL when prompted

Use `adb reboot edl` if authorized ADB works. Otherwise power off, hold both
volume keys, and connect USB. The installer continues only when Qualcomm
`05c6:9008` is visible.

After a successful flash, hold Power for about ten seconds to boot.

## Stop or recover

If a write, connection, or read-back fails, do not reboot. Preserve the
installer output and backup directory. Reconnect in EDL and rerun the installer;
it checks already-written ranges before continuing.

For manual recovery, use [Backup and restore](../runbooks/backup-and-restore.md)
and [Flash and verify](../runbooks/flash-and-verify.md). Do not improvise
name-based vbmeta writes or change slot metadata.
