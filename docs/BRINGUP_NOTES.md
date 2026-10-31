# TCL Flip 4 5G (T440W) - Phase 1 Findings & Phase 2 Bringup Runbook

> **Experimental / brick risk.** Writing to `super`, `vbmeta`, or `vbmeta_system`
> over EDL can render the device unbootable if interrupted or mis-addressed.
> Always verify `backups/flip4-full-emmc.img` exists before running any write,
> never pass `--skipresponse` on EDL writes, and always read back and compare
> SHA-256 digests before rebooting.

---

## 1. Critical Hardware & Software Findings from Stock Partitions

Offline analysis of the TCL Flip 4 5G (`T440W`, `gflip5gtmo` / `pitti_32go`)
partitions (`boot_b`, `init_boot_b`, `vendor_boot_b`, `system_a`, `system_ext_b`,
`product_b`, `vendor_b`, `odm_b`, and `super`) uncovered five critical facts that
govern Android 14 bringup on this device:

### Finding 1: Architecture is **`a64` (`arm32_binder64`)**, NOT 64-bit userspace (`arm64`)

- **Kernel (`boot_b`):** 64-bit ARM64 Linux `6.1.90-android14` (`CONFIG_64BIT=y`,
  `CONFIG_COMPAT=y`, `CONFIG_COMPAT_BINFMT_ELF=y`, `CONFIG_ANDROID_BINDER_IPC=y`).
- **First-stage `init` (`init_boot_b`) & `vendor_b` / `odm_b` (`pitti_32go`):**
  32-bit ARM (`ELF 32-bit LSB executable, ARM, EABI5`):
  - `ro.vendor.product.cpu.abilist=armeabi-v7a,armeabi`
  - `ro.bionic.arch=arm`
  - `ro.vndk.version=34` / `ro.board.api_level=34`
- **Implication:** Flashing a 64-bit (`arm64_bvN`) GSI will fail to load 32-bit
  vendor HALs (`hwservicemanager` / `vndservicemanager` / passthrough `same_process_hal`).
  The required GSI architecture is **`a64_bvN` (`arm32_binder64`, A/B, vanilla,
  Android 14 / SDK 34)**.

### Finding 2: How Stock KaiOS 4 Replaced Android Userspace

- Stock `system` (`qssi_32go`) is an Android 14 build containing standard AOSP
  daemons (`surfaceflinger`, `servicemanager`, `audioserver`, `cameraserver`,
  `mediaserver`, `netd`, `vold`, `installd`, `keystore2`, `wificond`, `rild`,
  `com.android.vndk.v34`, `com.android.art`, `framework.jar`, `services.jar`),
  with `ro.config.low_ram=true`.
- However, TCL stripped `SystemUI.apk` and `Settings.apk` and added
  `/system/etc/init/b2g.rc` (`service b2g /system/bin/b2g.sh`, `api-daemon`,
  `updater-daemon`, `b2gkillerd`).
- Meanwhile, `vendor_b` (`device/qcom/pitti_32go/manifest_pitti.xml`) exposes a
  complete, standard **Android 14 Treble target-level 8 (VNDK 34)** HAL set
  (`audio@7.1`, `bluetooth@1.1`, `gatekeeper` AIDL, `keymint` AIDL, `health`
  AIDL, `power` AIDL, `sensors-multihal` AIDL, `usb` AIDL, `wifi` AIDL,
  `radio.*` AIDL, `display.composer`/`allocator` AIDL).

### Finding 3: Stock `system_ext_b` & `product_b` Must Be Zero-Length in `super` for GSIs

- In `vendor_boot_b`'s `fstab.emmc`, `system`, `system_ext`, and `product` are
  listed as `wait,slotselect,avb=vbmeta_system,logical,first_stage_mount`.
- In an Android 14 GSI, `/system/system_ext` (`SystemUI.apk`, `Settings.apk`,
  etc.) and `/system/product` (`Launcher3`, `Dialer`, `Messaging`, etc.) are
  bundled **inside `system.img`** (with root symlinks `/system_ext -> /system/system_ext`
  and `/product -> /system/product`).
- If `system_ext_b` and `product_b` remain mapped to stock extents in `super`,
  `first_stage_init` mounts stock KaiOS `system_ext_b` and `product_b` **over**
  `/system_ext` and `/product`, hiding the GSI's `SystemUI.apk`, `Settings.apk`,
  and `Launcher3`!
- Disassembly and string inspection of `init_boot_b`'s `/init` confirms standard
  AOSP `FirstStageMount::CreateLogicalPartitions()` behavior: when a logical
  partition in `super` has **zero extents (`num_extents = 0`, size = 0)**, `init`
  logs `"Skipping zero-length logical partition: <name>"` and **removes it from
  `fstab_` in memory** without touching `vendor_boot_b`!
- `scripts/lp_make.py --surgical` sets `product_b` and `system_ext_b` to
  `num_extents = 0` by default while leaving their stock sectors on disk
  untouched.

### Finding 4: `vendor_sepolicy.cil` References KaiOS `_34_0` Types (Solved via Merged `precompiled_sepolicy`)

- Stock `vendor_b` (`/vendor/etc/selinux/vendor_sepolicy.cil` and
  `/vendor/etc/selinux/plat_pub_versioned.cil`) references KaiOS-specific
  versioned types (`b2g_34_0`, `b2gkillerd_34_0`, `api-daemon_34_0`,
  `gonksched_34_0`, `gonkservices_34_0`, `telephonyservice4b2g_34_0`, etc.).
- A generic GSI's `/system/etc/selinux/mapping/34.0.cil` does not define those
  KaiOS types. If `/system/bin/init` (`selinux_setup`) falls back to running
  `secilc` at boot, `secilc` will fail on `b2g_34_0` and reboot-loop!
- Furthermore, the stock kernel (`boot_b`) is compiled with
  `# CONFIG_SECURITY_SELINUX_BOOTPARAM is not set`, so `androidboot.selinux=permissive`
  on the kernel command line is ignored; permissive SELinux must come from the
  loaded binary policy (`permissive_map`).
- **Solution (`scripts/prepare_gsi.py`):**
  1. Generates `device/t440w/selinux/t440w_compat.cil` (196 lines declaring the
     missing KaiOS/QTI `_34_0` attributes and stub types).
  2. Compiles a **merged binary policy** combining the GSI's `plat_sepolicy.cil`
     + `mapping/34.0.cil` + `system_ext_sepolicy.cil`, `vendor_b`'s
     `plat_pub_versioned.cil` + `vendor_sepolicy.cil`, and `t440w_compat.cil`,
     then runs `setpermissive` so all **3,058 types** (every GSI type + every
     vendor type) are permissive.
  3. Writes the merged `/etc/selinux/precompiled_sepolicy`, the GSI's exact
     `.sha256` mapping hashes (`precompiled_sepolicy.plat_sepolicy_and_mapping.sha256`
     and `precompiled_sepolicy.system_ext_sepolicy_and_mapping.sha256`, omitting
     `product` when the GSI has no separate `product` sepolicy), and
     `/etc/selinux/odm_sepolicy.cil` into `odm_b_android.img`.
  4. At boot, `/system/bin/init` (`FindPrecompiledSplitPolicy()`) sees all
     `.sha256` hashes match and loads the permissive `/odm/etc/selinux/precompiled_sepolicy`
     directly without invoking `secilc`.

### Finding 5: Physical Flip Keypad & GPIO Key Mappings

- On stock KaiOS, the device-specific keylayout files (`soc_matrix_keypad0.kl`,
  `gpio-keys.kl`, `pm8941_pwrkey.kl`, `pm8941_resin.kl`) lived in
  `/system/usr/keylayout/` (not `/vendor`), and used non-AOSP keycode names
  (`MESSAGE`, `FAVORITE_CONTACTS`, `FLIP`, `QD_CALL`) that cause standard
  Android `libinput` `KeyLayoutMap` to reject the entire `.kl` file.
- Even worse, in standard AOSP `Generic.kl`:
  - Scancode `352` (Center OK button) is commented out (`# key 352 "KEY_OK"`).
  - Scancode `48` (physical Clear/Back button on the keypad) is mapped to letter `B`!
  - Scancode `30` (physical Message shortcut button) is mapped to letter `A`!
  - Scancode `138` (physical Contacts shortcut button) is commented out!
- **Solution (`scripts/prepare_gsi.py` & `device/t440w/keylayout/android/`):**
  1. Installs clean AOSP-valid `.kl` files (`soc_matrix_keypad0.kl`,
     `gpio-keys.kl`, `pm8941_pwrkey.kl`, `pm8941_resin.kl`) into
     `/odm/usr/keylayout/` inside `odm_b_android.img` (which `libinput` searches
     before `/vendor` and `/system`).
  2. Also patches `/system/usr/keylayout/Generic.kl` in-place inside
     `system_b_android.img` so scancodes `352 -> DPAD_CENTER`, `48 -> DEL`,
     `30 -> ENVELOPE`, and `138 -> CONTACTS` work even under `Generic.kl`
     fallback.

| Physical Key | Input Device | Scancode | Stock KaiOS `.kl` | Android Mapping |
|---|---|---|---|---|
| D-Pad Up / Down / Left / Right | `soc_matrix_keypad0` | `103` / `108` / `105` / `106` | `DPAD_*` | `DPAD_UP` / `DOWN` / `LEFT` / `RIGHT` |
| D-Pad Center (OK) | `soc_matrix_keypad0` | `352` | `ENTER` | `DPAD_CENTER` |
| Left Softkey | `soc_matrix_keypad0` | `139` | `SOFT_LEFT` | `MENU` |
| Right Softkey | `soc_matrix_keypad0` | `158` | `SOFT_RIGHT` | `BACK` |
| Clear / Backspace key | `soc_matrix_keypad0` | `48` | `DEL` | `DEL` |
| Call / Send key | `soc_matrix_keypad0` | `231` | `CALL` | `CALL` |
| End / Power key | `pm8941_pwrkey` / matrix | `116` | `ENDCALL` | `POWER` / `ENDCALL WAKE` |
| Message shortcut key | `soc_matrix_keypad0` | `30` | `MESSAGE` (invalid in AOSP) | `ENVELOPE` |
| Contacts shortcut key | `soc_matrix_keypad0` | `138` | `FAVORITE_CONTACTS` (invalid) | `CONTACTS` |
| Digits `1`..`9`, `0`, `*`, `#` | `soc_matrix_keypad0` | `2`..`11`, `522`, `523` | `1`..`0`, `STAR`, `POUND` | `1`..`0`, `STAR`, `POUND` |
| Volume Up / Down | `gpio-keys` / `pm8941_resin` | `115` / `114` | `VOLUME_UP` / `VOLUME_DOWN` | `VOLUME_UP` / `VOLUME_DOWN` |
| Flip Hall Sensor | `gpio-keys` + `/sys/hall_key/hall_value` | `252` | `FLIP` (invalid in AOSP) | `WAKEUP` |
| Side / SOS button | `gpio-keys` | `212` | `QD_CALL` (invalid in AOSP) | `ASSIST` |

---

## 2. Surgical `super` Layout: Zero-Move BSP & Instant Rollback

Inspecting `super_meta_live.img` (`super` starts at eMMC LBA `3686400`, size
`6,291,456` sectors = `3,072 MiB`) revealed that once the dead VABC `-cow`
extents (`2566664..2741984`) are dropped, `super` has two large free regions
without moving `odm_b`, `product_b`, `system_dlkm_b`, `system_ext_b`, `vendor_b`,
or `vendor_dlkm_b`:

| `super` Region | Start Sector (in `super`) | eMMC LBA (`3686400 + start`) | Sectors | Size |
|---|---|---|---|---|
| Region A (stock `system_a/b` primary) | `12288` | `3698688` | `1,240,920` | `635,351,040 B` (605.9 MiB) |
| Region B (tail free space after `vendor_b`) | `2568192` | `6254592` | `3,723,264` | `1,906,311,168 B` (1,818.0 MiB) |
| **Combined surgical capacity** | — | — | **`4,964,184`** | **`2,541,662,208 B` (2,423.9 MiB)** |

This gives us two prepared, signed, flash-ready Android 14 (`a64_bvN`) builds:

1. **`build/android-trebledroid/` (Recommended first boot test - 1.43 GiB):**
   - Based on **TrebleDroid AOSP 14 `arm32_binder64-ab-vanilla`** (`2024-11-05`
     security patch level, matching stock `vbmeta_system` SPL `2024-11-05`).
   - Fits entirely inside **Region B (1 single contiguous extent at eMMC LBA
     `6254592`)**!
   - **Stock KaiOS `system` (Region A, sectors `12288..1253208`), `product_b`,
     and `system_ext_b` are NOT overwritten on disk!** Rolling back to stock
     KaiOS takes <5 seconds by restoring the 512 KB `super_meta_live.img`,
     64 KB `vbmeta_system_b.img`, and 1.4 MB `odm_b` + `vbmeta_b`.
2. **`build/android-lineage21/` (LineageOS 21 / crDroid 10.13 `a64_bvN` - 2.07 GiB):**
   - Full LineageOS 21 (`a64_bvN` vanilla) environment; uses two linear extents
     (Region A `eMMC LBA 3698688` + Region B `eMMC LBA 6254592`).

---

## 3. Phase 2 Runbook: Flashing & Testing on the Device

### Prerequisites (when phone is connected in EDL mode `05c6:9008`)

```bash
scripts/check-device.sh
```

Ensure `backups/flip4-full-emmc.img` is present and verified before writing.

### Option A: Flash the Single-Extent TrebleDroid AOSP 14 Build (`build/android-trebledroid/`)

Because this build places `system_b` entirely in the unused tail of `super`
(LBA `6254592`), stock `system` is untouched on eMMC.

```bash
mkdir -p backups/pre-flash-android

# 1. Dump current metadata/partitions from device for instant rollback (READ = --skipresponse)
scripts/edl rs 3686400 1024 backups/pre-flash-android/super_meta.img      --loader=loader/flip-4-edl.bin --memory=emmc --skipresponse
scripts/edl rs 3688448 2872 backups/pre-flash-android/odm_b.img           --loader=loader/flip-4-edl.bin --memory=emmc --skipresponse
scripts/edl r  vbmeta_b        backups/pre-flash-android/vbmeta_b.img        --loader=loader/flip-4-edl.bin --memory=emmc --skipresponse
scripts/edl r  vbmeta_system_b backups/pre-flash-android/vbmeta_system_b.img --loader=loader/flip-4-edl.bin --memory=emmc --skipresponse

# 2. Flash odm_b, vbmeta_b, vbmeta_system_b, super_meta, and system_b (WRITE = NO --skipresponse!)
scripts/edl ws 3688448 build/android-trebledroid/odm_b_android.img           --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl w  vbmeta_b build/android-trebledroid/vbmeta_b_android.img       --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl w  vbmeta_system_b build/android-trebledroid/vbmeta_system_b_android.img --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl ws 3686400 build/android-trebledroid/super_meta_android.img      --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl ws 6254592 build/android-trebledroid/system_b_android.img        --loader=loader/flip-4-edl.bin --memory=emmc

# 3. Verify metadata & vbmeta writes committed (READ = --skipresponse)
scripts/edl rs 3686400 1024 /tmp/verify_super_meta.img --loader=loader/flip-4-edl.bin --memory=emmc --skipresponse
scripts/edl rs 3688448 2872 /tmp/verify_odm_b.img      --loader=loader/flip-4-edl.bin --memory=emmc --skipresponse
scripts/edl r  vbmeta_b        /tmp/verify_vbmeta_b.img        --loader=loader/flip-4-edl.bin --memory=emmc --skipresponse
scripts/edl r  vbmeta_system_b /tmp/verify_vbmeta_system_b.img --loader=loader/flip-4-edl.bin --memory=emmc --skipresponse
shasum -a256 /tmp/verify_*.img build/android-trebledroid/{super_meta_android,odm_b_android,vbmeta_b_android,vbmeta_system_b_android}.img
```

### Option B: Flash the Two-Extent LineageOS 21 Build (`build/android-lineage21/`)

```bash
scripts/edl ws 3688448 build/android-lineage21/odm_b_android.img           --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl w  vbmeta_b build/android-lineage21/vbmeta_b_android.img       --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl w  vbmeta_system_b build/android-lineage21/vbmeta_system_b_android.img --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl ws 3686400 build/android-lineage21/super_meta_android.img      --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl ws 3698688 build/android-lineage21/system_b_extent0.img        --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl ws 6254592 build/android-lineage21/system_b_extent1.img        --loader=loader/flip-4-edl.bin --memory=emmc
```

### First Boot & userdata Note

1. Pull the battery for ~10s, reinsert, and power on normally.
2. Watch `adb wait-for-device && adb logcat` (since `odm_b_android.img` sets
   `ro.debuggable=1`, `ro.adb.secure=0`, `persist.sys.usb.config=adb`, and
   `service.adb.root=1`, `adbd` starts early during boot).
3. If `vold` / `system_server` refuses to mount `/data` due to KaiOS keymaster /
   FBE metadata mismatch, format `userdata` + `metadata` from recovery or over
   ADB/EDL (after backing up any needed data).

### Instant Rollback to Stock KaiOS 4 (from Option A)

If you flashed Option A (`build/android-trebledroid/`), stock `system_b`,
`product_b`, and `system_ext_b` were never overwritten on disk! Restore stock
in <5 seconds over EDL:

```bash
scripts/edl ws 3686400 backups/pre-flash-android/super_meta.img      --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl ws 3688448 backups/pre-flash-android/odm_b.img           --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl w  vbmeta_b        backups/pre-flash-android/vbmeta_b.img        --loader=loader/flip-4-edl.bin --memory=emmc
scripts/edl w  vbmeta_system_b backups/pre-flash-android/vbmeta_system_b.img --loader=loader/flip-4-edl.bin --memory=emmc
```
