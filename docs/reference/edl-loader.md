# EDL loader reference

The T440W uses the signed programmer at
`../../tooling/loader/flip-4-edl.bin` through the vendored wrapper
`../../tooling/scripts/edl`.

## Non-negotiable protocol rule

- Read commands (`r`, `rs`, `rf`, `rl`, `printgpt`) use
  `--skipresponse`.
- Write and erase commands (`w`, `ws`, `wf`, `wl`, `e`) do not use
  `--skipresponse`.

On reads, the programmer omits an XML ACK expected by upstream `edl`, so
skipping that response is required to reach raw data. On writes, the response
is the ready-for-data handshake. Skipping it can print success without
committing bytes and can desynchronize the next command.

Every write must be followed by a fresh read-back and exact comparison before
reboot. For `vbmeta_system_b` and `vbmeta_b`, use raw-sector writes at LBAs
`2080768` and `3377152`; name-based writes have returned false success.

Evidence:
[`2026-07-17-01-root-project-inheritance.md`](../findings/2026-07-17-01-root-project-inheritance.md)
and [`2026-10-31-03-first-android-flash.md`](../findings/2026-10-31-03-first-android-flash.md).

## Vendored client changes

The repository carries bounded, device-specific read-path fixes for:

- mixed dict/bytes ACK data;
- an infinite USB timeout retry loop;
- endless loops on empty raw reads; and
- missing response keys after raw data.

These fixes do not make a write safe and do not replace read-back validation.
See the compatibility document [`../PATCHES.md`](../PATCHES.md).

## Observed identity

- HWID: `0x002980e100420071`
- MSM ID: `0x002980e1`
- Loader build date observed: May 14, 2025
- Storage: eMMC, 512-byte sectors
- USB EDL ID: `05c6:9008`

## Known control behavior

Software reset is unreliable with this programmer. The T440W reference phone
has a non-removable battery. The verified EDL exit is to hold Power for roughly
ten seconds until the phone vibrates and reboots.

Evidence:
[`2026-11-01-08-persistent-client-composition.md`](../findings/2026-11-01-08-persistent-client-composition.md).
