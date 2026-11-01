# Flash and verify over EDL

Writing the wrong sectors can permanently brick the phone. Stop if the device,
slot, GPT, source hashes, or rollback path differs from the session record.

## Preconditions

- User confirms the phone is in EDL mode.
- `tooling/scripts/check-device.sh` identifies `05c6:9008`.
- A full verified eMMC backup exists outside the working copy.
- Current target sectors/partitions have been backed up for this session.
- Active slot and GPT layout are known.
- Every source image has a recorded SHA-256.
- The planned write set and rollback set are written in the current finding.

## Protocol

- READ: include `--skipresponse`.
- WRITE: never include `--skipresponse`.
- Both vbmeta images use raw `ws`, not name-based `w`.
- Write payloads first and verification metadata last.
- Do not reboot until every read-back matches.

Common arguments:

```bash
EDL=tooling/scripts/edl
LOADER=tooling/loader/flip-4-edl.bin
```

## Raw vbmeta example

```bash
# Back up
$EDL rs 2080768 128 artifacts/backups/current/vbmeta_system_b.img \
  --loader="$LOADER" --memory=emmc --skipresponse
$EDL rs 3377152 128 artifacts/backups/current/vbmeta_b.img \
  --loader="$LOADER" --memory=emmc --skipresponse

# Write: no --skipresponse
$EDL ws 2080768 artifacts/build/android-flash/vbmeta_system_b_android.img \
  --loader="$LOADER" --memory=emmc
$EDL ws 3377152 artifacts/build/android-flash/vbmeta_b_android.img \
  --loader="$LOADER" --memory=emmc

# Read back
$EDL rs 2080768 128 /tmp/verify-vbmeta-system.img \
  --loader="$LOADER" --memory=emmc --skipresponse
$EDL rs 3377152 128 /tmp/verify-vbmeta.img \
  --loader="$LOADER" --memory=emmc --skipresponse

cmp artifacts/build/android-flash/vbmeta_system_b_android.img /tmp/verify-vbmeta-system.img
cmp artifacts/build/android-flash/vbmeta_b_android.img /tmp/verify-vbmeta.img
```

Adjust sector counts only from verified GPT/image geometry. A partition may be
larger than its image; comparison must cover exactly the bytes intended.

## Failure handling

- If a write reports success but read-back differs, do not reboot.
- Preserve the logs and mismatching read-back in the session evidence.
- Re-establish a fresh EDL session if the protocol became desynchronized.
- Restore only from a hash-recorded backup whose target geometry is known.

## Post-boot gate

Record:

```bash
adb shell getprop ro.boot.slot_suffix
adb shell getprop ro.build.fingerprint
adb shell getprop ro.system.build.fingerprint
adb shell getprop ro.build.version.sdk
adb shell getprop ro.debuggable
adb shell getprop ro.force.debuggable
adb shell getprop service.adb.root
adb shell id
adb root
adb shell id
adb shell 'test -w /sys/kernel/tracing/kprobe_events && echo writable'
```

Root and trace access are observations only if these checks succeed on the
running boot.

For a release profile, `adb root` may return no useful text; the authoritative
gate is that the subsequent identity remains UID 2000, `service.adb.root=0`,
and shell `su` is denied. SELinux must be enforcing, tracing must be off with
the `nop` tracer and no kprobes, both bounded helpers must have stopped
normally, and no navigation-bar inset may exist.

If Magisk Manager is carried outside package-scanned directories, install it
normally only after all image readbacks and the successful boot:

```bash
adb shell pm install -r -g \
  /system/etc/t440w/release/Magisk-v31.1.apk
```

Confirm its package path is under `/data/app`; a system-app path is a release
failure. Test application root as a separate deny/grant/cleanup gate and leave
no test policy or probe installed.
