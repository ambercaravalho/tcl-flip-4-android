# Install T440W Android v0.1.0

This is the frozen installation procedure for the `v0.1.0` alpha release. It
targets slot B on the TCL Flip 4 5G / Go Flip 5G model T440W only.

EDL writes can permanently brick the phone. The release has been validated on
one reference unit. Stop if any identity, geometry, hash, backup, or read-back
check differs from this guide.

## Requirements

- a T440W (`gflip5gtmo` / `pitti_32go`), not another TCL flip-phone model;
- a macOS or Linux host with Python 3 and at least 65 GiB free space;
- a data-capable USB cable connected directly, not through a hub;
- all `v0.1.0` release assets;
- a phone whose active slot is already B;
- a protected location outside this repository for the full eMMC backup.

The target identity is Qualcomm HWID `0x002980e100420071`, 512-byte eMMC with
61,079,552 sectors, and the reference GPT recorded in
[the device reference](../reference/device-and-abi.md). The installer verifies
the allowlisted image assets and ignores unrelated non-image files, but it
cannot make a different phone safe.

## 1. Get the repository and release

Clone the tag and install the host dependencies:

```bash
git clone --branch v0.1.0 \
  https://github.com/ambercaravalho/tcl-flip-4-android.git
cd tcl-flip-4-android
tooling/scripts/setup.sh
```

Download the assets from the
[`v0.1.0` release](https://github.com/ambercaravalho/tcl-flip-4-android/releases/tag/v0.1.0)
into an empty directory:

```bash
mkdir -p artifacts/releases/v0.1.0
gh release download v0.1.0 \
  --repo ambercaravalho/tcl-flip-4-android \
  --dir artifacts/releases/v0.1.0
```

Browser downloads are also supported. Do not rename the image files.

Verify every required file and print the no-write flash plan:

```bash
.venv/bin/python tooling/scripts/install-release.py \
  artifacts/releases/v0.1.0
```

The monolithic `system_b-rooted-release.img` is intentionally not distributed.
The two system extents are the complete flash payload.

## 2. Enter EDL

The phone must enumerate as Qualcomm `05c6:9008`.

Try, in order:

1. `adb reboot edl` if authorized ADB is available.
2. `fastboot oem edl` if fastboot is reachable.
3. Power off fully, hold both volume keys, and connect USB.
4. Use the hardware EDL test point only if you already understand that method.

Confirm detection:

```bash
tooling/scripts/check-device.sh
```

On Linux, install the udev rules if USB permissions block access:

```bash
sudo cp tooling/linux/51-edl.rules tooling/linux/50-android.rules \
  /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## 3. Make the mandatory full backup

The device read takes roughly 15 minutes and produces a file of about 29 GiB.
The script then validates both GPT CRCs, hashes the complete image with visible
progress, and creates a device-bound receipt:

```bash
tooling/scripts/backup.sh artifacts/backups/flip4-full-emmc.img
```

Copy both `flip4-full-emmc.img` and
`flip4-full-emmc.img.receipt.json` to protected storage outside the repository
before continuing. The receipt records the backup hash and the connected
phone's chip/eMMC serials. The backup contains personal data and device
identifiers.

The reference phone's Region A was overwritten during development. A
metadata-only rollback is not sufficient; a full verified backup is the
catastrophic recovery path.

## 4. Probe and back up every target

Run the read-only identity/GPT probe:

```bash
.venv/bin/python tooling/scripts/install-release.py \
  artifacts/releases/v0.1.0 \
  --probe-edl
```

Stop unless the tool reports the expected T440W identity, exact GPT geometry,
target ranges, and active slot B. `v0.1.0` does not change GPT slot metadata;
an active-slot-A phone is unsupported by this installer.

Create fresh target-range backups in the current EDL session:

```bash
.venv/bin/python tooling/scripts/install-release.py \
  artifacts/releases/v0.1.0 \
  --full-backup artifacts/backups/flip4-full-emmc.img \
  --backup-targets
```

The command prints the timestamped backup directory. Preserve it until the
phone has passed every post-boot gate.

## 5. Flash and verify

Use the exact backup directory printed by the prior step:

```bash
.venv/bin/python tooling/scripts/install-release.py \
  artifacts/releases/v0.1.0 \
  --full-backup artifacts/backups/flip4-full-emmc.img \
  --target-backup artifacts/backups/pre-v0.1.0/<timestamp> \
  --flash
```

The tool:

1. rechecks the release assets, full backup, EDL identity, GPT, and target
   backups;
2. asks for an explicit destructive-action confirmation;
3. writes `init_boot_b`, both system extents, `vendor_dlkm_b`, ODM, and super
   metadata before either vbmeta image;
4. writes both vbmeta images with raw `ws`, never name-based writes;
5. reads every complete target range back with `--skipresponse`;
6. compares every read-back byte-for-byte and confirms slot B remained active.

Writes never use `--skipresponse`. If EDL disconnects, a command fails, or any
comparison differs, do not reboot. Reconnect, preserve the logs and partial
receipt, and restore the affected ranges from the timestamped target backup.

To leave EDL on this non-removable-battery phone, hold Power for roughly ten
seconds until it vibrates and boots.

## 6. Accept the boot

Do not judge success only from the Android UI. Run:

```bash
adb wait-for-device
adb shell getprop ro.boot.slot_suffix
adb shell getprop ro.build.fingerprint
adb shell getprop ro.build.version.sdk
adb shell getprop ro.debuggable
adb shell getprop ro.force_debuggable
adb shell getprop service.adb.root
adb shell id
adb root
adb shell id
adb shell getenforce
adb shell 'su -c id; echo exit=$?'
```

The accepted release state is:

- slot `_b`, SDK `34`, ABI `armeabi-v7a`;
- stable physical display after startup;
- Back, Home, Messages, CONTACTS cursor toggle, D-pad movement/click/scroll,
  and cursor disable all work physically;
- SELinux `Enforcing`;
- `ro.debuggable=0`, empty `ro.force_debuggable`, and
  `service.adb.root=0`;
- ADB remains UID 2000 after `adb root`;
- shell `su` is denied.

Install Magisk Manager normally only after those checks pass:

```bash
adb shell pm install -r -g \
  /system/etc/t440w/release/Magisk-v31.1.apk
adb shell pm path com.topjohnwu.magisk
```

Its path must be under `/data/app`, not `/system/app`.

Continue with [Using the ROM](using-the-rom.md). For rollback rules, see
[Backup and restore](../runbooks/backup-and-restore.md).

## Redistribution caveat

The release includes a prebuilt `vendor_dlkm_b` with a binary-patched GPL
`msm_drm.ko`. TCL's available disclosures contain unrelated 4.19/5.15 trees,
not the exact shipped 6.1 SPI module source. The release includes the
hash-locked patch tooling and available reconstruction evidence, but the
missing corresponding source remains an unresolved GPL compliance risk.
