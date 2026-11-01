# 2026-11-01 05: SPI driver control selection

Status: complete

## Objective

Select and validate the smallest reversible SPI-driver control that follows
from the completed GSI traces. Do not write the device until the exact
single-variable experiment, target bytes, read-back verification, and rollback
commands are recorded and the user confirms the current physical state and
EDL transition.

## Starting state

- Captured at `2026-11-01T16:08:44Z`.
- Device mode and active slot: booted Android GSI over ADB, slot B (`_b`).
- Running OS:
  - fingerprint:
    `TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys`
  - system fingerprint: same as runtime fingerprint
  - SDK: `34`
  - ABI: `armeabi-v7a`
  - flavor: `treble_a64_bvN-userdebug`
  - verified-boot state: locked/green
- Runtime image identity:
  - top-level vbmeta digest:
    `fa818c9ccb99bfce94979e2b449a8404e5ab140f9e9f0077bad94cb470c6f657`
  - system root digest:
    `07d1de5bd1fcecf354df054908904872455d4af72e364dfbe580873a3cf533f0`
  - ODM root digest:
    `606838a37231d46c4e60a48f1ab987f7f4a16c27b3e1469dd926135422213711`
  - vendor-DLKM root digest:
    `571852c55a293dbcf65c58a44ac7ae1206afcfb013b9d2dc797e74993ff6d7eb`
  - loaded `/vendor_dlkm/lib/modules/msm_drm.ko` SHA-256:
    `39f972853c5acb061a3964a48cf6bf0ff375b55dc216e537c69e76c290755065`
- Exact target-partition bytes have not yet been read back in this session.
  Host filenames are not treated as proof of currently flashed bytes.
- Backup/rollback state:
  - verified full eMMC backup SHA-256, rechecked this session:
    `ec16365c0b1147a98d08a39e2557b0d0ac5415aa48db8efcde29b0fe736118b3`
  - Region A remains overwritten; stock rollback is not metadata-only.
  - a fresh read-back of every proposed target remains mandatory before a
    write.
- ADB/root/trace gate:
  - serial: `830f21d`
  - `ro.debuggable=0`
  - `ro.force.debuggable=0`
  - `service.adb.root=1`
  - identity: `uid=0(root)`, context `u:r:su:s0`
  - `tracing_on=0`, `current_tracer=nop`, empty `kprobe_events`
- Android state:
  - `org.tclflip4.fullscreencontrol` remains installed and resumed
  - last direct physical observation at the prior-session handoff was a gray
    panel with the backlight on
  - Android's last captured screenshot was the correct green/magenta pattern
  - the current physical panel outcome awaits user reconfirmation before any
    state-changing step

## Artifacts

- Baseline host inputs:
  - `../../artifacts/build/vendor_dlkm_b.img`:
    `3293e02acf9ccf1e2a39835f849fdf5b46704602c7201e17aa6e2cde78a42e0d`
  - `../../artifacts/build/dtbo_b.img`:
    `82bce888a5a389d67927b17c5a9e5023f783a0ecda398f3dae8f28d151caec75`
  - `../../artifacts/build/vbmeta_b.img`:
    `3cfb8e2e821916209d9b078b966f777a9db0b4001200313ba6e0495f2b3d50f5`
  - `../../artifacts/build/odm_b-dbg-patched.img`:
    `b182c49c9f0c58c7a21038c8c06a2b0635f2cfe74afce9603db8b45f37dd1e39`
  - signed EDL loader:
    `4161aae496c91a584c58542cc539f9538f8ff5281f470eba18dd49b004020e0a`
- Immutable control:
  - module:
    `fad244e7c83a166145fc84f84af921edb97ce8abd0ec0fd1366339e8dbb2f14b`
  - vendor-DLKM image:
    `c0c95b3913a0d70c0f449813e25cfcad113c012fa2d83e74aaf2e5bdcba8916a`
  - top-level vbmeta image:
    `eef06811d2ba0d5da51d95923155cb348b214922f7216cde2af24b59d0b3be2c`
  - corrected top-level vbmeta based on the exact current host-matched image:
    `0308b1b14712b68a05100565083e6aed3cd6d6667fa7e77348c944151bd1ff7b`
- Coalescing control:
  - module:
    `0ea57fdcd501c820692329e67459ded94b7a27f4373215a98ae7dd6c26d7decb`
  - vendor-DLKM image:
    `638c96cb26827666405fa96d12ea4693ea510fa6b53ab7e268755b58be49e80d`
  - top-level vbmeta image:
    `8c232eff8cc200bb3e4dcf5620edc376ede09dbabf6b97855a0c6167860c20b0`
- Full-height-client control:
  - module:
    `89febd510f7aa939ce8a20943038f0beab67d1d59a49ce48110dc229b624cf50`
  - vendor-DLKM image:
    `ac2f2a35dc3e21f38ba51f8e8076812cbddea7b31ef7959f2d929f94b5bba116`
  - top-level vbmeta image:
    `487e00a8f517fc359d355992211be7a8edd5b4b7ae554132f45d033a654d947e`
- Immutable runtime evidence:
  `../../evidence/captures/gsi-spi-immutable/`
  - baseline manifest:
    `de984d0be8deea8a897853c7a1571be0603dd0530212d4fe544069b086b1c8e1`
  - baseline host screenshot:
    `04af40a52c6a76534f19f1085c6d7830101c50475908b9c7b55ef9d804a76548`
  - settled control screenshot:
    `79857471e437653a17257481078290f3dc661c5f98b77ac48a08a70bfe1ce636`
  - one-key trace:
    `455d75ca3da4f950997dc6bed59a50bcad882a5364449be5946309af1d29bf17`
  - saved analysis:
    `255e4345b7a74e074aaccc8b004b9e503f810f2d559fdd4943702f16a3224dac`
  - post-key host screenshot:
    `1d2f8f4a7e7819c601167240c5e2bafa74d36f9603caa01f3394e2893be95a88`
  - post-restore manifest:
    `16873672c650df350326b0e6338e22052ffb2e1c331d12a0ab05bd0ea93f843c`
  - post-restore host screenshot:
    `10126a4aed5fe05c338cacdc28c6266f4e4b7bb2159c0b5a13f3a02307c02259`

## Actions and observations

1. **Action:** committed the completed root and full-screen-control sessions as
   `70f419e` and pushed `main` to `origin`.
2. **Observation:** the booted device still loads the exact stock
   `msm_drm.ko`. No partition or sector has changed since the prior session.
3. **Observation:** the prepared profiles differ materially:
   - `immutable` changes one instruction so framebuffer updates no longer
     replace the RGB565 staging contents, while queueing and SPI transfers
     continue;
   - `coalesce` changes four instructions to collapse pending work but still
     accepts independent planes and does not compose them;
   - `full-height-client` changes nine instructions, combining full-height
     filtering, a fixed client stride, and coalescing;
   - lower-clock profiles change transport timing rather than the demonstrated
     plane-to-frame contract.
4. **Inference:** `immutable` is the smallest first diagnostic control. It
   changes one mechanism—source-frame mutation—while preserving the observed
   queue and transport path. It can distinguish content/composition effects
   from TE/SPI sequencing without claiming to be a display fix.
5. **Observation:** the existing `flash-spi-test.sh` writes vendor-DLKM, DTBO,
   and vbmeta for every profile. An immutable-module test does not require a
   DTBO change. Writing DTBO would enlarge the write set and must not be part
   of the first single-variable control unless a same-session read-back proves
   that the write is byte-identical and there is a documented reason to retain
   it.
6. **Observation:** read-only hashes of the running device's target bytes
   matched these host artifacts:
   - raw vendor-DLKM extent:
     `3293e02acf9ccf1e2a39835f849fdf5b46704602c7201e17aa6e2cde78a42e0d`
   - `vbmeta_b`:
     `044944e54b8a8e63129924e49cb3724933204c5d65bb31e54f16df8813bb29f6`,
     matching
     `artifacts/build/android-lineage21-clean/vbmeta_b_android.img`
   - `dtbo_b`:
     `82bce888a5a389d67927b17c5a9e5023f783a0ecda398f3dae8f28d151caec75`
7. **Observation:** the immutable module embedded in its vendor-DLKM image is
   byte-identical to the standalone module and hashes to `fad244e7...f14b`.
   Its AVB footer and SHA-256 hashtree verify successfully.
8. **Observation:** the previously prepared immutable vbmeta image is unsafe
   for the current GSI. It describes ODM root digest `b8640c76...17b1`,
   whereas the running device and exact current vbmeta require
   `606838a3...3711`. It also came from a different top-level vbmeta source.
   That prepared vbmeta must not be flashed.
9. **Action:** generated
   `artifacts/build/spi-driver-tests/vbmeta_b-immutable-current.img` from the
   exact current host-matched vbmeta, changing only the vendor-DLKM descriptor
   to the immutable image's root digest and zero-FEC geometry.
10. **Observation:** the corrected vbmeta is 65,536 bytes, hashes to
    `0308b1b1...ff7b`, and its RSA-4096 signature and embedded public key
    verify. Descriptor comparison against the current vbmeta shows only the
    intended vendor-DLKM FEC geometry and root-digest changes; the current ODM
    descriptor remains intact.
11. **Direct physical observation:** at the session gate, the user reported
    that the panel was showing the correct green/magenta pattern. It recovered
    from the prior backlit-gray state without a reboot or driver write. The
    static physical output and Android screenshot are therefore aligned again;
    this does not resolve the redraw failure.
12. **Action:** with user confirmation, ran `adb reboot edl`. The first USB
    check occurred before enumeration and found no device; three seconds later
    `05c6:9008` appeared normally. EDL identified the expected unit:
    - HWID `0x002980e100420071`
    - serial `0xa2676da1`
    - PK hash beginning `b43d6b7d...`
    - 32 GB eMMC with 512-byte sectors
13. **Observation:** GPT confirmed `vbmeta_b` at byte offset `0x67100000`
    (LBA `3377152`) with length `0x10000` (`128` sectors), and `super` at
    `0x70800000` (LBA `3686400`). The known vendor-DLKM logical extent starts
    `2451456` sectors into `super`, yielding raw LBA `6137856`, length `105072`
    sectors.
14. **Action:** before any write, read both target ranges to
    `artifacts/backups/pre-spi-immutable/20261101T161357Z/`.
15. **Observation:** fresh backup hashes matched the booted-device reads and
    exact current host artifacts:
    - vendor-DLKM:
      `3293e02acf9ccf1e2a39835f849fdf5b46704602c7201e17aa6e2cde78a42e0d`
    - `vbmeta_b`:
      `044944e54b8a8e63129924e49cb3724933204c5d65bb31e54f16df8813bb29f6`
16. **Action:** after a separate final user authorization, wrote the immutable
    vendor-DLKM image first and corrected `vbmeta_b` last. Neither write used
    `--skipresponse`.
17. **Observation:** while remaining in EDL, read back both complete target
    ranges with `--skipresponse` and compared them byte-for-byte. Both matched:
    - vendor-DLKM:
      `c0c95b3913a0d70c0f449813e25cfcad113c012fa2d83e74aaf2e5bdcba8916a`
    - `vbmeta_b`:
      `0308b1b14712b68a05100565083e6aed3cd6d6667fa7e77348c944151bd1ff7b`
18. **Observation:** no DTBO, super metadata, vbmeta-system, or other range was
    written. The phone remains in EDL; the modified state has not yet booted.
19. **Action:** after byte verification, the user removed the battery for
    roughly ten seconds, reinstalled it, and booted normally.
20. **Observation:** Android completed boot on slot B with locked/green AVB:
    - top-level vbmeta digest:
      `5f6d7607a87ed5c3eeea6b03579bef7496beee35c020957f26ef836731039c36`
    - system and ODM root digests were unchanged;
    - vendor-DLKM root digest became
      `668b5d840594fb0fda22c3789505429f8b0580f7fe14dd578c12ce5f7eba0f14`;
    - loaded `msm_drm.ko` matched the immutable module:
      `fad244e7c83a166145fc84f84af921edb97ce8abd0ec0fd1366339e8dbb2f14b`.
21. **Observation:** Rooted debugging persisted as a supported setting, but
    adbd initially came up as shell with `service.adb.root=0`. The required
    post-boot `adb root` check succeeded, yielding `uid=0`, `u:r:su:s0`,
    `service.adb.root=1`, and writable clean tracefs.
22. **Direct physical observation:** the user reported a stable backlit-gray
    panel after boot. Android's host screenshot remained correct and showed
    the Lineage setup UI.
23. **Action:** launched the same full-screen control app. Its settled Android
    screenshot correctly showed the blue/yellow pattern, while the user
    reported that the physical panel stayed gray and stable.
24. **Action:** captured a ten-second trace while the user pressed D-pad Right
    exactly once (`code=106` press and release).
25. **Observation:** the immutable trace retained the unpatched workload and
    transport behavior:
    - six plane updates;
    - four framebuffer submissions: two `240x21` and two `240x320`;
    - all `AB24`, 1024-byte pitch;
    - five frame transfers plus five full-window commands;
    - median TE interval `16.787 ms`;
    - full-frame SPI duration up to `25.087 ms`.
26. **Observation:** Android's post-key screenshot correctly changed to
    green/magenta. The user reported that the physical panel remained gray and
    stable throughout the same submissions and transfers.
27. **Observation:** trace cleanup left `tracing_on=0`,
    `current_tracer=nop`, and empty `kprobe_events`.
28. **Action:** because the immutable control intentionally cannot display
    current content, the user authorized restoration. Re-entered EDL with
    `adb reboot edl` and selected only the two verified pre-test backups.
29. **Action:** restored the vendor-DLKM extent first and original `vbmeta_b`
    last. Neither write used `--skipresponse`.
30. **Observation:** read both restored ranges back with `--skipresponse` and
    compared them byte-for-byte before reboot:
    - vendor-DLKM restored to
      `3293e02acf9ccf1e2a39835f849fdf5b46704602c7201e17aa6e2cde78a42e0d`;
    - `vbmeta_b` restored to
      `044944e54b8a8e63129924e49cb3724933204c5d65bb31e54f16df8813bb29f6`.
31. **Action:** the user performed the battery-removal EDL exit and booted
    normally.
32. **Observation:** the restored runtime exactly recovered:
    - top-level vbmeta digest `fa818c9c...f657`;
    - vendor-DLKM root digest `571852c5...7eb`;
    - stock module SHA-256 `39f97285...5065`;
    - unchanged system and ODM root digests;
    - locked/green AVB on slot B.
33. **Observation:** the complete post-boot root gate passed after `adb root`:
    `ro.debuggable=0`, `ro.force.debuggable=0`, `service.adb.root=1`,
    `uid=0`, `u:r:su:s0`, writable tracefs, `tracing_on=0`, and no probes.
34. **Direct physical observation:** the user reported that the restored
    physical panel was correct and stable. The final host screenshot also
    correctly showed the Lineage language screen.
35. **Action:** changed `flash-spi-test.sh` to fail closed for `immutable`,
    `coalesce`, and `full-height-client`. Their prebuilt top-level vbmeta files
    cannot be trusted across GSI states; a module profile now requires a
    same-session target read-back and explicitly recorded raw-LBA procedure.

## Planned gated write

This procedure is recorded but not yet authorized or executed. It changes
exactly two raw ranges:

- vendor-DLKM extent: LBA `6137856`, `105072` sectors;
- `vbmeta_b`: LBA `3377152`, `128` sectors.

It does not write DTBO, super metadata, or either `vbmeta_system` partition.
After the user confirms the physical state and places the phone in EDL:

```bash
EDL=tooling/scripts/edl
LOADER=tooling/loader/flip-4-edl.bin
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP=artifacts/backups/pre-spi-immutable/$STAMP
VERIFY=artifacts/build/spi-driver-tests/verify-immutable-$STAMP
VENDOR=artifacts/build/spi-driver-tests/vendor_dlkm_b-immutable.img
VBMETA=artifacts/build/spi-driver-tests/vbmeta_b-immutable-current.img

tooling/scripts/check-device.sh
$EDL printgpt --loader="$LOADER" --memory=emmc --skipresponse

mkdir -p "$BACKUP"
$EDL rs 6137856 105072 "$BACKUP/vendor_dlkm_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse
$EDL rs 3377152 128 "$BACKUP/vbmeta_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse
shasum -a 256 "$BACKUP/vendor_dlkm_b.img" "$BACKUP/vbmeta_b.img"

# Stop unless those hashes are exactly:
# vendor_dlkm_b 3293e02acf9ccf1e2a39835f849fdf5b46704602c7201e17aa6e2cde78a42e0d
# vbmeta_b      044944e54b8a8e63129924e49cb3724933204c5d65bb31e54f16df8813bb29f6

# Data first, verification metadata last. Writes never use --skipresponse.
$EDL ws 6137856 "$VENDOR" --loader="$LOADER" --memory=emmc
$EDL ws 3377152 "$VBMETA" --loader="$LOADER" --memory=emmc

# Do not reboot until both read-backs compare exactly.
$EDL rs 6137856 105072 "$VERIFY-vendor_dlkm_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse
$EDL rs 3377152 128 "$VERIFY-vbmeta_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse
cmp "$VENDOR" "$VERIFY-vendor_dlkm_b.img"
cmp "$VBMETA" "$VERIFY-vbmeta_b.img"
```

If write verification fails, remain in EDL and restore data first, metadata
last:

```bash
$EDL ws 6137856 "$BACKUP/vendor_dlkm_b.img" \
  --loader="$LOADER" --memory=emmc
$EDL ws 3377152 "$BACKUP/vbmeta_b.img" \
  --loader="$LOADER" --memory=emmc
$EDL rs 6137856 105072 "$VERIFY-rollback-vendor_dlkm_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse
$EDL rs 3377152 128 "$VERIFY-rollback-vbmeta_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse
cmp "$BACKUP/vendor_dlkm_b.img" "$VERIFY-rollback-vendor_dlkm_b.img"
cmp "$BACKUP/vbmeta_b.img" "$VERIFY-rollback-vbmeta_b.img"
```

## Conclusions

- The immutable control behaved as designed and is not a usable display fix:
  it prevents any new composed content from reaching the panel, leaving a
  stable gray output.
- With staging-buffer mutation disabled, the same four framebuffer
  submissions, five frame transfers, TE cadence, and full-frame wire time no
  longer produced jumping or flicker.
- This separates the failure from transfer cadence alone. The physical
  instability requires the changing per-plane staging contents that the stock
  bridge creates; repeated synchronous SPI transfers of unchanged contents
  were physically stable in this control.
- The result further supports correcting the plane-to-frame content contract,
  while reducing the priority of lower-clock experiments. It does not prove
  that coalescing alone or full-height filtering is sufficient.

## Disproven assumptions

- “The prepared immutable vbmeta is compatible with the current GSI because
  it was built for slot B” is false. Its untargeted ODM descriptor was stale.
- “SPI transfer count or timing alone is sufficient to explain the jumping
  output” is false for this control. The same submission and transfer pattern
  was physically stable when staging contents did not change.
- The immutable profile is not a display fix; it deliberately prevents valid
  current content from reaching the panel.

## Mistakes and process corrections

The first attempt to query per-partition root digests used an unsupported
`avbctl get-verity-digest` command. It made no state change. The correction was
to read the existing `partition.<name>.verified.root_digest` properties.

The first direct `avbtool verify_image` call used the suffixed filename
`vendor_dlkm_b-immutable.img`; `avbtool` looked for a sibling named
`vendor_dlkm.img` from the descriptor and exited after verifying the footer.
Repeating verification through a temporary correctly named symlink verified
the complete hashtree. No artifact was changed.

The first fail-closed guard in `flash-spi-test.sh` ran after generation of an
unused baseline vbmeta host artifact. It did not connect to or change the
device. The guard was moved ahead of all artifact generation so rejected
module profiles now exit without side effects.

The prepared manifests label paths under `build/spi-driver-tests/`, while the
files currently reside under `artifacts/build/spi-driver-tests/`. Their
recorded hashes match the actual files, but future manifests should use
repository-relative paths that resolve directly.

More importantly, the original prepared vbmeta was based on an obsolete ODM
image. The guardrail is to derive verification metadata from a same-session
read-back or a host image proven byte-identical to it, then compare all
untargeted descriptors before authorizing a write.

## Ending state

- Device mode and active slot: booted Android GSI on slot B.
- Running OS/build: unchanged starting GSI with the stock `msm_drm.ko`
  restored.
- Partitions or sectors changed:
  - LBA `6137856`, `105072` sectors: changed to immutable, then restored
    exactly to the pre-test backup;
  - LBA `3377152`, `128` sectors: changed to corrected immutable vbmeta, then
    restored exactly to the pre-test backup.
- Verified rollback path:
  rollback completed from
  `artifacts/backups/pre-spi-immutable/20261101T161357Z/`; both restored
  read-backs matched before boot.
- ADB/root/trace access: root adbd and clean, writable tracefs.
- Physical display: user reports correct and stable output after restoration.
- Android state: Lineage setup is resumed; the full-screen control package
  remains installed but is not foreground.
- Uncommitted host artifacts: this finding; ignored build, backup, log, and
  capture evidence.

## Safe next step

In a new session, rebuild the coalescing control's top-level vbmeta from the
exact current `044944e5...29f6` image rather than its stale prepared vbmeta.
Validate untargeted descriptors before considering a write. The coalescing
control is the next smaller isolation step; do not jump directly to the
multi-variable full-height-client profile.
