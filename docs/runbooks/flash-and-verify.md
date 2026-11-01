# Flash and verify over EDL

Community installs use the [guided installer](../guides/install.md). This is
the generic protocol for research and recovery.

Writing the wrong sectors can permanently brick the phone. Before writing,
confirm the device, active slot, exact GPT, source hashes, full device-bound
backup, target backups, and rollback commands.

## Rules

- Reads use `--skipresponse`.
- Writes never use `--skipresponse`.
- Both vbmeta partitions use raw `ws`, not name-based `w`.
- Payloads and metadata precede verification images.
- Read every complete written range back and compare it before reboot.

```bash
EDL=tooling/scripts/edl
LOADER=tooling/loader/flip-4-edl.bin
```

Example raw vbmeta cycle:

```bash
$EDL rs 2080768 128 artifacts/backups/current/vbmeta_system_b.img \
  --loader="$LOADER" --memory=emmc --skipresponse

$EDL ws 2080768 artifacts/build/android-flash/vbmeta_system_b.img \
  --loader="$LOADER" --memory=emmc

$EDL rs 2080768 128 /tmp/verify-vbmeta-system.img \
  --loader="$LOADER" --memory=emmc --skipresponse

cmp artifacts/build/android-flash/vbmeta_system_b.img \
  /tmp/verify-vbmeta-system.img
```

Use only verified GPT/image geometry. Compare exactly the written byte range,
not an assumed partition size.

## Failure

If a command fails or a read-back differs, do not reboot. Preserve logs and
the partial receipt, reconnect in EDL, and restore only from a hash-recorded
backup for the same phone and geometry.

After a release boot, run:

```bash
tooling/scripts/verify-post-boot.sh
```

Then physically verify the display and controls. See [Using the ROM](../guides/using-the-rom.md).
