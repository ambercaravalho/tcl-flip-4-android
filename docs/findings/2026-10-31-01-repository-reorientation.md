# 2026-10-31 01: Repository reorientation

Status: complete

## Objective

Reframe the repository from a stock-KaiOS rooting project into research and
tooling for booting full Android 14 on the T440W.

## Starting state

- The phone remained on stock KaiOS.
- Existing work focused on EDL, backup, permissive SELinux, and root ADB.
- Partition analysis showed that most of the relevant AVB tree used AOSP test
  keys, but the Android-userspace path was not yet organized.

## Artifacts

- Commit `e426dae` added `avbtool`, test keys, and the `vbmeta_system` finding.
- Commit `e170617` reoriented the README and partition documentation.
- Public test keys now live under
  `../../tooling/tools/avb/testkeys/`.

## Actions and observations

- Top-level `vbmeta` was matched to public AOSP `testkey_rsa4096`.
- Chained `vbmeta_system` was matched to public AOSP `testkey_rsa2048`.
- The architecture was reframed as a locked-bootloader userspace replacement:
  retain the Android 14 GKI kernel and Qualcomm BSP, replace the userspace
  logical partitions, regenerate verity metadata, and re-sign the chain.
- Stock-root instructions were moved conceptually to the upstream
  `tcl-flip-4-root` project.

## Conclusions

- A GSI/userspace swap is feasible without bootloader unlock if the replacement
  images remain compatible with the stock kernel/vendor boundary and the AVB
  descriptors are rebuilt correctly.
- This project must treat stock-root behavior as prior evidence, not as proof
  that an Android GSI will load properties or services identically.

## Disproven assumptions

No device experiment occurred in this session. Feasibility was established
from offline partition and key evidence, not from a successful Android boot.

## Mistakes and process corrections

The initial documentation mixed architecture claims, future plans, and
operational commands. Later sessions showed why those categories need separate
findings, references, and runbooks.

## Ending state

- Repository goal: full Android 14 bringup on T440W.
- Device: unchanged stock KaiOS.
- Next work could remain entirely offline.

## Safe next step

Inspect all stock partitions and build a reproducible SDK-34 `a64` GSI
preparation pipeline before touching the phone.
