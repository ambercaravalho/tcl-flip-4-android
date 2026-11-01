# Partitions, AVB, and `super`

## Verified AVB keys

Top-level `vbmeta` uses `SHA256_RSA4096` with the public AOSP
`testkey_rsa4096`:

`7728e30f50bfa5cea165f473175a08803f6a8346642b5aa10913e9d9e6defef6`

Chained `vbmeta_system` uses `SHA256_RSA2048` with public AOSP
`testkey_rsa2048`:

`22de3994532196f61c039e90260d78a93a4c57362c7e789be928036e80b77c8c`

Its recorded key SHA-1 is
`cdbb77177f731920bbe0a0f94f84d9038ae0617d`.

Keys are under `../../tooling/tools/avb/testkeys/`.
Evidence:
[`2026-10-31-01-repository-reorientation.md`](../findings/2026-10-31-01-repository-reorientation.md).

## Verification tree

- `vbmeta_{a,b}` covers chain descriptors for boot, recovery, and
  `vbmeta_system`; hash descriptors for `init_boot`, `vendor_boot`, and `dtbo`;
  and hashtrees for vendor-side partitions.
- `vbmeta_system_{a,b}` covers hashtrees for `system`, `system_ext`, and
  `product`.
- `dtbo` has a raw hash descriptor in top-level vbmeta and no standalone AVB
  footer.

Use surgical descriptor updates rather than rebuilding unrelated descriptors.

## Reference raw LBAs

- `vbmeta_system_b`: `2080768`
- `dtbo_b`: `3293184`
- `vbmeta_b`: `3377152`
- `super`: `3686400`
- `odm_b`: `3688448`
- Region A / first system extent: `3698688`
- `vendor_dlkm_b`: `6137856`
- Region B / TrebleDroid system extent: `6254592`

These values are for the reference unit's known layout. Confirm GPT and target
slot before using them on any other device.

## `super` layout

The two useful regions observed after removing dead VABC COW extents were:

- Region A: 1,240,920 sectors starting at in-super sector `12288`
  (eMMC LBA `3698688`)
- Region B: 3,723,264 sectors starting at in-super sector `2568192`
  (eMMC LBA `6254592`)

The first TrebleDroid image fit entirely in Region B and initially left stock
system sectors intact. The later Lineage test used both regions and overwrote
Region A. Current stock rollback therefore requires restoring those sectors
from the full backup; restoring only metadata/ODM/vbmeta is insufficient.

Evidence:
[`2026-10-31-03-first-android-flash.md`](../findings/2026-10-31-03-first-android-flash.md)
and [`2026-10-31-04-display-experiments.md`](../findings/2026-10-31-04-display-experiments.md).

## Operational constraints

- Reads use `--skipresponse`.
- Writes never use `--skipresponse`.
- Use raw `ws` for both vbmeta partitions. Name-based `w` reported success
  while leaving them unchanged.
- Read every target back and compare before reboot.
- Modify data partitions first and verification metadata last.

See [`../runbooks/flash-and-verify.md`](../runbooks/flash-and-verify.md).
