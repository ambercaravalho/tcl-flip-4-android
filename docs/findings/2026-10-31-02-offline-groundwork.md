# 2026-10-31 02: Offline groundwork and GSI preparation

Status: complete

## Objective

Determine the exact GSI architecture and build flash-ready Android 14 artifacts
without connecting the phone.

## Starting state

- Device remained on stock KaiOS and was not connected.
- A full eMMC backup and carved stock images were available.
- Android userspace requirements, `super` allocation, SELinux compatibility,
  and keypad behavior still needed to be resolved.

## Artifacts

- Commit `70ba3d8`.
- Stock hardware references under `../../device/t440w/`.
- Preparation and image tools under `../../tooling/scripts/`.
- Prepared output was produced outside the repository under
  `/tmp/t440w-gsi/`; it must be regenerated or accompanied by its manifest
  before reuse.

## Actions and observations

1. **ABI**
   - Kernel is ARM64 with compat support.
   - First-stage init and vendor/ODM userspace are 32-bit ARM.
   - Vendor reports VNDK and board API 34.
   - Required GSI is Android 14 / SDK 34 `a64_bvN`
     (`arm32_binder64`), not `arm64`.
2. **Dynamic partitions**
   - A GSI contains `system_ext` and `product` inside `system.img`.
   - Leaving stock `system_ext_b` and `product_b` mapped would hide those GSI
     directories.
   - `lp_make.py --surgical` therefore emits zero-length logical entries for
     both partitions.
3. **SELinux**
   - Stock vendor policy references KaiOS-specific `_34_0` types absent from a
     generic GSI.
   - The kernel ignores a SELinux command-line permissive request.
   - The pipeline builds a merged, permissive ODM
     `precompiled_sepolicy` with compatibility declarations.
4. **Keypad**
   - Several stock KaiOS key names are invalid to AOSP.
   - Device-specific ODM keylayouts and selected `Generic.kl` corrections were
     prepared.
5. **Storage layout**
   - `super` begins at eMMC LBA `3686400`.
   - A 1.43 GiB TrebleDroid image fit entirely in free Region B at LBA
     `6254592`.
   - A larger Lineage image required Region A at `3698688` plus Region B.

## Conclusions

- The preparation pipeline must reject non-SDK-34 and non-32-bit-ARM-system
  inputs.
- Surgical zero-length `system_ext_b` and `product_b` entries are part of the
  boot design, not an optional cleanup.
- ODM is the practical carrier for keylayouts and merged SELinux policy.
- The single-extent TrebleDroid layout initially preserved stock system sectors
  and offered the lowest-risk first boot.

## Disproven assumptions

- “A 64-bit kernel means an arm64 GSI” is false on this device.
- “Stock `system_ext_b` and `product_b` can remain mounted under a GSI” is
  false.
- “`androidboot.selinux=permissive` is sufficient” is false for this kernel.

## Mistakes and process corrections

The first pipeline documentation bundled ODM debug properties with the
statement that root adbd would result. No GSI runtime had verified that claim.
The correct output of this session was a requested configuration, not proof of
runtime root.

## Ending state

- Device still stock and recoverable.
- Flash-ready Android 14 `a64_bvN` artifacts existed on the host.
- No on-device behavior had yet been validated.

## Safe next step

Flash the single-extent build with pre-write backups and read-back verification,
then record runtime identity, boot behavior, ADB state, and display output.
