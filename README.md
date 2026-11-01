# T440W Android 14

An experimental Android 14 ROM for the TCL Flip 4 5G / Go Flip 5G (T440W).
The `v0.1.0` alpha release has a stable physical display, keypad navigation,
toggleable D-pad cursor, microG, Aurora Store, and Magisk-managed application
root. It boots locked/green on the stock Android 14 kernel and Qualcomm vendor
stack; no bootloader unlock or data wipe is intended.

This release has been installed and validated on one T-Mobile T440W. It is not
validated on other TCL flip-phone models, carrier variants, storage layouts, or
firmware bases.

For stock KaiOS root research, use
[tcl-flip-4-root](https://github.com/ambercaravalho/tcl-flip-4-root).

## Read this before installing

Qualcomm EDL writes can permanently brick a phone. Before any write, make a
full verified eMMC backup and copy it to protected storage outside this
repository. The current stock rollback requires that full backup; a
metadata-only rollback is not sufficient.

The T440W firehose rule is absolute:

- reads use `--skipresponse`;
- writes do not use `--skipresponse`; and
- every write is read back and compared before reboot.

Name-based writes have falsely reported success for `vbmeta_system_b` and
`vbmeta_b`. The release installer uses raw sectors, reads every write back, and
refuses to continue after a mismatch. Do not substitute hand-written commands
unless you understand the complete write and rollback sets.

The AVB chain is signed with public AOSP test keys. It verifies and boots
locked/green, but it is not a private production trust anchor.

## Install

1. Read the complete [`v0.1.0` installation guide](docs/guides/install-v0.1.0.md).
2. Install host dependencies with `tooling/scripts/setup.sh`.
3. Download every `v0.1.0` release asset and verify it with the tracked release
   manifest.
4. Enter EDL, make the mandatory full backup, and run the guarded installer.
5. Complete the post-boot physical and security checks before relying on the
   phone.

The release targets slot B and the exact reference T440W GPT geometry. The
installer starts in read-only plan mode, binds the full backup receipt to the
connected phone's chip/eMMC serials, and requires a typed confirmation before
the flash phase. Slot B must already be active; the installer never modifies
GPT slot metadata.

## What works

- Android 14 / SDK 34 `a64_bvN` userspace
- stable 240x320 physical display with forced client composition
- physical Back, Home, Messages, and D-pad navigation
- C9 cursor toggle, movement, click, and conditional scrolling
- hidden on-screen navigation bar
- enforcing SELinux and authenticated, non-root ADB
- Magisk 31.1 application root, denied by default until explicitly granted
- microG Services and Companion
- Aurora Store anonymous browsing, downloads, and Session Installer

Telephony, carrier behavior, cameras, Bluetooth, and every daily-use workload
have not received a release acceptance gate. Treat anything not listed above
as unverified rather than working.

## Supported target

- Model: T440W (`gflip5gtmo` / `pitti_32go`)
- Base: Android 14 / SDK 34, Linux `6.1.90-android14`
- Userspace ABI: 32-bit ARM with 64-bit binder (`a64` /
  `arm32_binder64`), not arm64
- GSI target: Android 14 `a64_bvN`
- Storage: eMMC, A/B, Virtual A/B, dynamic partitions in `super`
- Reference slot: B
- EDL USB ID: `05c6:9008`
- Display: 240x320 ST7789P3 over a private Qualcomm/TCL SPI DRM path

Do not flash if the model, HWID, GPT geometry, sector size, or release hashes
differ from the guide.

## Repository layout

- `docs/guides/` — versioned community install and usage guides
- `docs/findings/` — chronological session evidence and conclusions
- `docs/reference/` — durable device, AVB, EDL, and SPI facts
- `docs/runbooks/` — guarded repeatable procedures
- `device/t440w/` — extracted hardware and configuration references
- `artifacts/backups/` — ignored device backups and pre-write snapshots
- `artifacts/build/` — ignored carved images, prepared GSIs, and test outputs
- `artifacts/downloads/` — ignored upstream archives and extracted sources
- `evidence/captures/` — ignored stock/GSI capture sets
- `evidence/logs/` — ignored tool and flash logs
- `tooling/scripts/` — preparation, capture, backup, and flashing helpers
- `tooling/tools/` — AVB, boot-image, and policy utilities
- `tooling/vendor/` — patched vendored EDL client
- `tooling/loader/` — signed T440W firehose programmer
- `tooling/linux/` — Linux udev rules

## After installation

Read [Using the ROM](docs/guides/using-the-rom.md) for keypad controls,
first-boot setup, Magisk Manager, microG, Aurora Store, and the expected
non-root ADB security state.

Magisk Manager is carried in the image outside Android's package-scan
directories. Install it normally only after the flash read-backs and release
boot gates pass:

```bash
adb shell pm install -r -g \
  /system/etc/t440w/release/Magisk-v31.1.apk
```

Application root is denied by default. Grant it per app in Manager; ADB shell
must remain unprivileged.

## Build and research

- [Documentation hub](docs/README.md)
- [Build and release runbook](docs/runbooks/build-and-release.md)
- [Accepted release components](docs/reference/release-components.md)
- [Release evidence](docs/findings/2026-11-01-10-rooted-release-stack.md)
- [Partition and AVB reference](docs/reference/partitions-and-avb.md)

The findings directory remains the chronological evidence record. It is useful
for porting and auditing, but community installers should follow the frozen
release guide rather than reconstructing commands from a research session.

Future agents and maintainers must also follow [AGENTS.md](AGENTS.md).

## Credits and license

Prior work and project lineage:
[tcl-flip-4-root](https://github.com/ambercaravalho/tcl-flip-4-root).
AVB key identification builds on
[Ryjelsum's QM215 research](https://ryjelsum.me/homelab/qm215-kaios-flips/)
and [tcl-flip-4-root issue #3](https://github.com/ambercaravalho/tcl-flip-4-root/issues/3).
The vendored EDL client derives from
[bkerler/edl](https://github.com/bkerler/edl) and remains GPLv3.

See [LICENSE](LICENSE) and [NOTICE](NOTICE).
