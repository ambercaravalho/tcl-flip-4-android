# 2026-07-17 to 2026-07-19: Stock-root project inheritance

Status: complete

## Objective

Establish a recoverable EDL workflow for the TCL Flip 4 5G and obtain root ADB
plus permissive SELinux on its stock KaiOS userspace.

## Starting state

- Stock KaiOS 4 on a locked-bootloader T440W.
- No Android GSI had been flashed.
- Qualcomm EDL and the device's signed firehose programmer were the available
  recovery path.

## Artifacts

- Git history: `ec35cd1`, `6f8dad7`, `fa949e8`, `8b136bb`, `f2c4e10`,
  `e9c328b`.
- Full eMMC backup now referenced at
  `../../artifacts/backups/flip4-full-emmc.img`.
- Signed programmer now stored at
  `../../tooling/loader/flip-4-edl.bin`.
- Original detailed stock-root runbook:
  [tcl-flip-4-root/docs/ROOT.md](https://github.com/ambercaravalho/tcl-flip-4-root/blob/main/docs/ROOT.md).

## Actions and observations

- The vendored EDL client was reduced and patched for the T440W loader.
- Reads were found to require `--skipresponse`.
- Writes were found to require the normal response handshake. Passing
  `--skipresponse` could print success while leaving flash unchanged.
- Stock ODM was rebuilt with a permissive `precompiled_sepolicy` and debug/ADB
  properties, then its AVB descriptor was re-signed.
- On rooted stock KaiOS, later capture confirmed:
  `ro.debuggable=1`, `service.adb.root=1`, and `ro.adb.secure=1`.

## Conclusions

- EDL is a viable backup and recovery path on the reference unit.
- Publicly available AOSP test keys cover the AVB images needed for the stock
  ODM modification.
- ODM debug properties worked in the stock KaiOS property-loading environment.
- EDL output is not proof of persistence; read-back comparison is mandatory.

## Disproven assumptions

- “The same `--skipresponse` workaround is safe for reads and writes” is false.
- “A successful write message proves the target changed” is false.

## Mistakes and process corrections

The stock success of ODM `ro.debuggable=1` was later generalized to generic
Android GSIs. That generalization was unsupported. The reusable conclusion is
only that ODM worked on this stock build; every other userspace must be checked
at runtime.

## Ending state

- A full stock backup and repeatable EDL path existed.
- Stock KaiOS could run with permissive SELinux and root ADB.
- The repository still primarily described rooting stock KaiOS.

## Safe next step

Before replacing userspace, map the complete AVB chain, ABI, dynamic-partition
layout, and rollback requirements offline.
