# TCL Flip 4 5G Android bringup

Research, evidence, and tooling for running full Android 14 on the TCL Flip 4
5G (T440W) while retaining its stock Android 14 GKI kernel and Qualcomm vendor
BSP.

The device's locked bootloader trusts public AOSP test keys across the relevant
AVB chain, making a verified userspace replacement possible without a
bootloader unlock. Android boots, and a retained full-height SPI profile paired
with forced SurfaceFlinger client composition now renders correctly and
stably.

For stock KaiOS root research, use
[tcl-flip-4-root](https://github.com/ambercaravalho/tcl-flip-4-root).

## Warning

This is experimental work on one reference phone. EDL writes can permanently
brick a device. Keep a full verified backup outside this repository, inspect
every command, and stop when the observed state differs from the documented
preconditions.

The T440W firehose rule is absolute:

- reads use `--skipresponse`;
- writes do not use `--skipresponse`; and
- every write is read back and compared before reboot.

Name-based writes have falsely reported success for `vbmeta_system_b` and
`vbmeta_b`. Use raw writes at the verified LBAs in the runbook.

## Start here

Read [`docs/README.md`](docs/README.md). It contains the current state, required
reading order, chronological session findings, durable references, runbooks,
and the “do not infer” checks.

Future agents must also follow [`AGENTS.md`](AGENTS.md).

## Device summary

- Model: T440W (`gflip5gtmo` / `pitti_32go`)
- Base: Android 14 / SDK 34, Linux `6.1.90-android14`
- Userspace ABI: 32-bit ARM with 64-bit binder (`a64` /
  `arm32_binder64`), not arm64
- GSI target: Android 14 `a64_bvN`
- Storage: eMMC, A/B, Virtual A/B, dynamic partitions in `super`
- Reference slot: B
- EDL USB ID: `05c6:9008`
- Display: 240x320 ST7789P3 over a private Qualcomm/TCL SPI DRM path

## Repository layout

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

## Host setup

```bash
tooling/scripts/setup.sh
```

On Linux:

```bash
sudo cp tooling/linux/51-edl.rules tooling/linux/50-android.rules \
  /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Check for an EDL device:

```bash
tooling/scripts/check-device.sh
```

Make the mandatory full backup:

```bash
tooling/scripts/backup.sh
```

## Current research state

- Clean Android 14 `treble_a64_bvN` boots on slot B.
- The stock SPI bridge is unstable when Android supplies independent hardware
  planes because it treats each plane as a complete frame.
- Correct host screenshots place the defect after logical composition.
- The stock binary calls the SPI framebuffer update once per DRM plane while
  assuming every input is a full-screen precomposed RGB565 frame.
- Stock KaiOS actually supplies that contract: one full-screen BG16 plane per
  animation frame.
- The GSI's built-in Rooted debugging setting provides root adbd and writable
  tracefs without changing `ro.debuggable=0`.
- The matching GSI trace confirms the contract violation: one D-pad event
  generated 96 `AB24` framebuffer submissions and 98 frame transfers, versus
  stock's 16 `BG16` submissions and 18 transfers.
- A controlled full-screen client reduced one transition to four submissions,
  but the panel still jumped and ended backlit gray while the Android
  screenshot remained correct.
- An immutable driver control kept the same submissions and transfers but
  prevented changing plane contents from replacing the staging frame; the
  physical panel stayed stable gray. Transfer cadence alone is not sufficient
  to cause the failure.
- A pending-counter coalescing control reduced five transfers to four and
  remained physically incorrect; it did not establish an atomic-commit
  boundary.
- The full-height-client driver still failed under default composition. With
  SurfaceFlinger forced to client composition, one controlled transition
  became one full-height client-target submission and remained correct and
  stable. The animated Lineage welcome screen also passed.
- The full-height driver and matching vbmeta are retained. Forced client
  composition is runtime-only and must be reapplied after a reboot or
  SurfaceFlinger restart until persistence is implemented and validated.
- Lineage testing overwrote Region A; metadata-only rollback is no longer
  sufficient.

The next work is to persist forced client composition at boot as a
single-variable change, then reboot and repeat both physical display gates.

## Credits and license

Prior work and project lineage:
[tcl-flip-4-root](https://github.com/ambercaravalho/tcl-flip-4-root).
AVB key identification builds on
[Ryjelsum's QM215 research](https://ryjelsum.me/homelab/qm215-kaios-flips/)
and [tcl-flip-4-root issue #3](https://github.com/ambercaravalho/tcl-flip-4-root/issues/3).
The vendored EDL client derives from
[bkerler/edl](https://github.com/bkerler/edl) and remains GPLv3.

See [LICENSE](LICENSE) and [NOTICE](NOTICE).
