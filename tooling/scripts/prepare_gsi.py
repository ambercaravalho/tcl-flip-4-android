#!/usr/bin/env python3
"""Offline GSI preparation, keypad/SELinux patching, AVB signing, and super
metadata generation for the TCL Flip 4 5G (T440W).

Given an Android 14 `a64` (`arm32_binder64`) GSI image (`.img`, `.img.xz`, or
`.img.gz`, sparse or raw ext4), this script:
  1. Decompresses and unsparses the image to `<out-dir>/system_b_android.img`.
  2. Rejects non-SDK-34 inputs, records the GSI's actual fingerprint and hash,
     and confirms `/system/bin/init` is 32-bit ARM (`ELF 32-bit LSB ... ARM`,
     required by `init_boot` and 32-bit vendor HALs).
  3. Patches `/system/usr/keylayout/Generic.kl` in-place (preserving exact byte
     size so ext4 inode/block checksums stay untouched) to map the TCL Flip 4 5G
     physical keypad scancodes (`352 -> DPAD_CENTER`, `48 -> BACK`,
     `30 -> ENVELOPE`, `138 -> CONTACTS`).
  4. Embeds the signed T440W keypad-cursor AccessibilityService, its idempotent
     boot enabler, and the early hardware-navigation policy.
  5. Compiles a merged, 100% permissive SELinux policy (`precompiled_sepolicy`)
     combining the GSI's CIL policies (`plat` + `system_ext` + optional `product`),
     the TCL Flip 4 5G `vendor_b` CIL policies, and the KaiOS/QTI `_34_0`
     compatibility bridge (`t440w_compat.cil`), then populates
     `<out-dir>/odm_b_android.img` with:
       - `/etc/selinux/precompiled_sepolicy` (all GSI + vendor types permissive)
       - `/etc/selinux/precompiled_sepolicy.*.sha256` matching the GSI
       - `/etc/selinux/odm_sepolicy.cil` (fallback CIL bridge for `secilc`)
       - `/usr/keylayout/{soc_matrix_keypad0,gpio-keys,pm8941_pwrkey,pm8941_resin}.kl`
       - optional USB-only diagnostics (`ro.debuggable`, ADB properties, and
         the legacy ConfigFS fallback);
       - a separately selected, opt-in display diagnostic profile.
  6. Rebuilds the AVB hashtree footers on `odm_b_android.img` and
     `system_b_android.img` (`--do_not_generate_fec`) and surgically re-signs:
       - `<out-dir>/vbmeta_b_android.img` (`testkey_rsa4096.pem`)
       - `<out-dir>/vbmeta_system_b_android.img` (`testkey_rsa2048.pem`)
  7. Generates `<out-dir>/super_meta_android.img` via `tooling/scripts/lp_make.py --surgical`
     (mapping `product_b` and `system_ext_b` as zero-length so `first_stage_init`
     uses the GSI's internal `/system/product` and `/system/system_ext`).

Usage:
    tooling/scripts/prepare_gsi.py <gsi.img[.xz|.gz]> [--out-dir artifacts/build/android-flash]
"""
import argparse
import gzip
import hashlib
import json
import lzma
import os
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tooling", "scripts"))
from inspect_ext4 import Ext4Reader, EXT4_EXTENTS_FL

SPARSE_HEADER_MAGIC = 0xED26FF3A
CHUNK_TYPE_RAW = 0xCAC1
CHUNK_TYPE_FILL = 0xCAC2
CHUNK_TYPE_DONT_CARE = 0xCAC3
CHUNK_TYPE_CRC32 = 0xCAC4

DISPLAY_PROFILES = {
    "none": (),
    # Reproducibility profiles for already-disproven experiments. These are
    # deliberately opt-in and never part of the default USB debug profile.
    "wait-fences": (
        "debug.sf.latch_unsignaled=0",
        "debug.sf.auto_latch_unsignaled=0",
    ),
    "spec-fence-off": ("vendor.display.enable_spec_fence=0",),
}


def parse_android_properties(raw_bytes):
    """Parse Android property-file bytes into a last-definition-wins mapping."""
    props = {}
    for raw_line in raw_bytes.decode("utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = value.strip()
    return props


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while chunk := source.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def extract_or_copy(src_path, raw_tmp_path):
    """Decompress .xz/.gz if needed into raw_tmp_path."""
    if src_path.endswith(".xz"):
        print(f">> Decompressing XZ archive {src_path} -> {raw_tmp_path} ...")
        xz_bin = shutil.which("xz")
        if xz_bin:
            with open(raw_tmp_path, "wb") as out:
                # SECURITY-REVIEW: CLI tool invoking local xz binary with static flags
                subprocess.run([xz_bin, "-dc", "-T0", src_path], stdout=out, check=True)
        else:
            with lzma.open(src_path, "rb") as inp, open(raw_tmp_path, "wb") as out:
                while buf := inp.read(4 * 1024 * 1024):
                    out.write(buf)
    elif src_path.endswith(".gz"):
        print(f">> Decompressing GZ archive {src_path} -> {raw_tmp_path} ...")
        with gzip.open(src_path, "rb") as inp, open(raw_tmp_path, "wb") as out:
            while buf := inp.read(4 * 1024 * 1024):
                out.write(buf)
    else:
        if os.path.abspath(src_path) != os.path.abspath(raw_tmp_path):
            print(f">> Copying {src_path} -> {raw_tmp_path} ...")
            shutil.copyfile(src_path, raw_tmp_path)


def unsparse_if_needed(img_path):
    """If img_path is an Android sparse image, convert it in-place to raw."""
    with open(img_path, "rb") as fh:
        hdr = fh.read(28)
    magic = struct.unpack_from("<I", hdr, 0)[0]
    if magic != SPARSE_HEADER_MAGIC:
        return

    major, minor, file_hdr_sz, chunk_hdr_sz, blk_sz, total_blks, total_chunks, _ = (
        struct.unpack_from("<HHHHIIII", hdr, 4)
    )
    out_tmp = img_path + ".raw"
    print(f">> Unsparsing Android sparse image ({total_blks} blocks of {blk_sz} B) ...")
    with open(img_path, "rb") as inp, open(out_tmp, "wb") as out:
        out.truncate(total_blks * blk_sz)
        inp.seek(file_hdr_sz)
        cur_blk = 0
        for _ in range(total_chunks):
            chdr = inp.read(chunk_hdr_sz)
            ctype, _, chunk_blks, total_sz = struct.unpack_from("<HHII", chdr, 0)
            data_sz = total_sz - chunk_hdr_sz
            if ctype == CHUNK_TYPE_RAW:
                out.seek(cur_blk * blk_sz)
                rem = data_sz
                while rem > 0:
                    buf = inp.read(min(4 * 1024 * 1024, rem))
                    out.write(buf)
                    rem -= len(buf)
            elif ctype == CHUNK_TYPE_FILL:
                fill_val = inp.read(4)
                if fill_val != b"\x00\x00\x00\x00":
                    out.seek(cur_blk * blk_sz)
                    block_buf = fill_val * (blk_sz // 4)
                    for _ in range(chunk_blks):
                        out.write(block_buf)
            elif ctype == CHUNK_TYPE_DONT_CARE:
                if data_sz > 0:
                    inp.seek(data_sz, os.SEEK_CUR)
            elif ctype == CHUNK_TYPE_CRC32:
                inp.seek(data_sz, os.SEEK_CUR)
            else:
                raise SystemExit(f"error: unknown sparse chunk type {ctype:#x}")
            cur_blk += chunk_blks
    os.replace(out_tmp, img_path)


def strip_existing_avb_footer(img_path):
    """If the image has an AVB footer, truncate back to original_image_size."""
    sz = os.path.getsize(img_path)
    if sz < 64:
        return
    with open(img_path, "rb+") as fh:
        fh.seek(sz - 64)
        footer = fh.read(64)
        if footer[:4] == b"AVBf":
            orig_sz = struct.unpack_from(">Q", footer, 12)[0]
            print(f">> Stripping existing AVB footer on {os.path.basename(img_path)} ({sz} -> {orig_sz} bytes)")
            fh.truncate(orig_sz)


def get_file_extents(reader, path):
    inode = reader.resolve_path(path)
    if not (inode["flags"] & EXT4_EXTENTS_FL):
        raise SystemExit(f"error: {path} does not use ext4 extents")
    exts = sorted(reader._collect_extents(inode["i_block"]), key=lambda x: x[0])
    return inode, exts


def overwrite_ext4_file_same_size(img_path, file_path_in_img, new_bytes):
    """Overwrite an existing ext4 file in-place with identical byte length."""
    with open(img_path, "r+b") as fh:
        reader = Ext4Reader(fh)
        inode, exts = get_file_extents(reader, file_path_in_img)
        if len(new_bytes) != inode["size"]:
            raise SystemExit(
                f"error: size mismatch for in-place write on {file_path_in_img}: "
                f"got {len(new_bytes)} B, expected {inode['size']} B"
            )
        bs = reader.block_size
        covered_until = 0
        for ee_block, ee_len, pblock, uninit in exts:
            if uninit:
                raise SystemExit(f"error: {file_path_in_img} has uninitialized extent")
            logical_offset = ee_block * bs
            if any(new_bytes[covered_until:logical_offset]):
                raise SystemExit(
                    f"error: non-zero data for sparse hole in {file_path_in_img}"
                )
            chunk_len = min(ee_len * bs, len(new_bytes) - logical_offset)
            if chunk_len <= 0:
                break
            fh.seek(pblock * bs)
            fh.write(new_bytes[logical_offset:logical_offset + chunk_len])
            covered_until = logical_offset + chunk_len
            if covered_until >= len(new_bytes):
                break
        if any(new_bytes[covered_until:]):
            raise SystemExit(
                f"error: file extents do not cover non-zero tail of {file_path_in_img}"
            )


def patch_generic_kl_for_t440w(raw_kl_bytes):
    """Patch Generic.kl for the TCL Flip 4 5G keypad while preserving exact byte length."""
    orig_len = len(raw_kl_bytes)
    text = raw_kl_bytes.decode("utf-8")

    text, n1 = re.subn(r"^key\s+30\s+A\b", "key 30    ENVELOPE", text, count=1, flags=re.M)
    text, n2 = re.subn(
        r"^key\s+48\s+(?:B|DEL)\b",
        "key 48    BACK",
        text,
        count=1,
        flags=re.M,
    )
    text, n3 = re.subn(r"^#\s*key\s+138\s+.*$", "key 138   CONTACTS", text, count=1, flags=re.M)
    text, n4 = re.subn(r"^#\s*key\s+352\s+.*$", "key 352   DPAD_CENTER", text, count=1, flags=re.M)

    new_bytes = text.encode("utf-8")
    diff = len(new_bytes) - orig_len
    if diff > 0:
        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if diff == 0:
                break
            if line.startswith("# ") and len(line.rstrip("\r\n")) > 4:
                can_take = min(diff, len(line.rstrip("\r\n")) - 2)
                lines[i] = line.rstrip("\r\n")[:-can_take] + "\n"
                diff -= can_take
        new_bytes = "".join(lines).encode("utf-8")
    elif diff < 0:
        pad = " " * (-diff)
        new_bytes = (text + "#" + pad).encode("utf-8")

    if len(new_bytes) != orig_len:
        raise SystemExit(f"error: Generic.kl length {len(new_bytes)} != original {orig_len}")
    return new_bytes, (n1, n2, n3, n4)


def inject_keypad_system_files(system_img, keypad_apk):
    """Add the signed keypad APK and its idempotent boot enabler to system."""
    sources = {
        "/system/app/T440WKeypadCursor/T440WKeypadCursor.apk": keypad_apk,
        "/system/bin/t440w-enable-keypad.sh": os.path.join(
            REPO_ROOT, "device", "t440w", "init", "t440w-enable-keypad.sh"
        ),
        "/system/etc/init/init.t440w.keypad.rc": os.path.join(
            REPO_ROOT, "device", "t440w", "init", "init.t440w.keypad.rc"
        ),
    }
    for target, source in sources.items():
        if not os.path.isfile(source):
            raise SystemExit(f"error: missing keypad source for {target}: {source}")

    with open(system_img, "rb") as image:
        reader = Ext4Reader(image)
        for target in sources:
            try:
                reader.resolve_path(target)
            except FileNotFoundError:
                continue
            raise SystemExit(f"error: refusing to replace existing system path: {target}")

    original_size = os.path.getsize(system_img)
    image_dir = os.path.dirname(os.path.abspath(system_img))
    image_name = os.path.basename(system_img)
    with tempfile.TemporaryDirectory(prefix="t440w-keypad-system-") as work:
        shutil.copyfile(keypad_apk, os.path.join(work, "T440WKeypadCursor.apk"))
        shutil.copyfile(
            sources["/system/bin/t440w-enable-keypad.sh"],
            os.path.join(work, "t440w-enable-keypad.sh"),
        )
        shutil.copyfile(
            sources["/system/etc/init/init.t440w.keypad.rc"],
            os.path.join(work, "init.t440w.keypad.rc"),
        )
        with open(os.path.join(work, "ctx.system.bin"), "wb") as output:
            output.write(b"u:object_r:system_file:s0\x00")
        commands = [
            "mkdir /system/app/T440WKeypadCursor",
            "sif /system/app/T440WKeypadCursor mode 040755",
            "sif /system/app/T440WKeypadCursor uid 0",
            "sif /system/app/T440WKeypadCursor gid 0",
            "ea_set -f /work/ctx.system.bin /system/app/T440WKeypadCursor security.selinux",
            "write /work/T440WKeypadCursor.apk /system/app/T440WKeypadCursor/T440WKeypadCursor.apk",
            "sif /system/app/T440WKeypadCursor/T440WKeypadCursor.apk mode 0100644",
            "sif /system/app/T440WKeypadCursor/T440WKeypadCursor.apk uid 0",
            "sif /system/app/T440WKeypadCursor/T440WKeypadCursor.apk gid 0",
            "ea_set -f /work/ctx.system.bin /system/app/T440WKeypadCursor/T440WKeypadCursor.apk security.selinux",
            "write /work/t440w-enable-keypad.sh /system/bin/t440w-enable-keypad.sh",
            "sif /system/bin/t440w-enable-keypad.sh mode 0100755",
            "sif /system/bin/t440w-enable-keypad.sh uid 0",
            "sif /system/bin/t440w-enable-keypad.sh gid 0",
            "ea_set -f /work/ctx.system.bin /system/bin/t440w-enable-keypad.sh security.selinux",
            "write /work/init.t440w.keypad.rc /system/etc/init/init.t440w.keypad.rc",
            "sif /system/etc/init/init.t440w.keypad.rc mode 0100644",
            "sif /system/etc/init/init.t440w.keypad.rc uid 0",
            "sif /system/etc/init/init.t440w.keypad.rc gid 0",
            "ea_set -f /work/ctx.system.bin /system/etc/init/init.t440w.keypad.rc security.selinux",
        ]
        command_file = os.path.join(work, "debugfs.cmd")
        with open(command_file, "w") as output:
            output.write("\n".join(commands) + "\n")
        image_in_container = f"/image/{image_name}"
        shell_command = (
            f"e2fsck -fy {shlex.quote(image_in_container)} >/dev/null"
            f" && debugfs -w -f /work/debugfs.cmd {shlex.quote(image_in_container)} >/dev/null"
            f" && e2fsck -fy {shlex.quote(image_in_container)} >/dev/null"
        )
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{image_dir}:/image",
                "-v",
                f"{work}:/work:ro",
                "t440w-tools:local",
                "sh",
                "-c",
                shell_command,
            ],
            check=True,
        )

    if os.path.getsize(system_img) != original_size:
        raise SystemExit("error: keypad injection changed the raw system image size")
    with open(system_img, "rb") as image:
        reader = Ext4Reader(image)
        for target, source in sources.items():
            actual = reader.read_inode_data(reader.resolve_path(target))
            with open(source, "rb") as expected_file:
                expected = expected_file.read()
            if actual != expected:
                raise SystemExit(f"error: embedded keypad file mismatch: {target}")


def calc_partition_size_for_avb(raw_img_size):
    needed = raw_img_size + (raw_img_size // 120) + (512 * 1024)
    align = 1024 * 1024
    return ((needed + align - 1) // align) * align


def verify_vbmeta_signature(image_path, key_path):
    """Verify a standalone vbmeta signature and its embedded AVB public key.

    ``avbtool verify_image`` also verifies every referenced partition. This
    pipeline intentionally does not materialize unchanged stock partitions, so
    perform the cryptographic checks without ignoring descriptor failures.
    """
    data = open(image_path, "rb").read()
    if len(data) < 256 or data[:4] != b"AVB0":
        raise RuntimeError(f"{image_path}: not a standalone vbmeta image")

    auth_size = struct.unpack_from(">Q", data, 12)[0]
    aux_size = struct.unpack_from(">Q", data, 20)[0]
    hash_off, hash_size = struct.unpack_from(">QQ", data, 32)
    sig_off, sig_size = struct.unpack_from(">QQ", data, 48)
    key_off, key_size = struct.unpack_from(">QQ", data, 64)
    blob_size = 256 + auth_size + aux_size
    if blob_size > len(data):
        raise RuntimeError(f"{image_path}: truncated vbmeta blob")

    header = data[:256]
    auth = data[256:256 + auth_size]
    aux = data[256 + auth_size:blob_size]
    signed_input = header + aux
    if auth[hash_off:hash_off + hash_size] != hashlib.sha256(signed_input).digest():
        raise RuntimeError(f"{image_path}: vbmeta authentication hash mismatch")

    signature = auth[sig_off:sig_off + sig_size]
    embedded_key = aux[key_off:key_off + key_size]
    with tempfile.TemporaryDirectory(prefix="t440w-avb-verify-") as tmp:
        expected_key = os.path.join(tmp, "expected.avbpubkey")
        public_pem = os.path.join(tmp, "public.pem")
        signature_path = os.path.join(tmp, "signature.bin")
        signed_input_path = os.path.join(tmp, "signed-input.bin")

        subprocess.run(
            [
                sys.executable,
                "tooling/tools/avb/avbtool.py",
                "extract_public_key",
                "--key", key_path,
                "--output", expected_key,
            ],
            check=True,
        )
        if embedded_key != open(expected_key, "rb").read():
            raise RuntimeError(
                f"{image_path}: embedded AVB key does not match {key_path}"
            )

        with open(public_pem, "wb") as out:
            subprocess.run(
                ["openssl", "pkey", "-in", key_path, "-pubout"],
                stdout=out,
                check=True,
            )
        open(signature_path, "wb").write(signature)
        open(signed_input_path, "wb").write(signed_input)
        subprocess.run(
            [
                "openssl", "dgst", "-sha256",
                "-verify", public_pem,
                "-signature", signature_path,
                signed_input_path,
            ],
            check=True,
        )
    print(f"   verified signature and embedded key: {image_path}")


def build_odm_android_image(
    gsi_img,
    vendor_img,
    stock_odm_img,
    odm_out,
    plat_sha,
    sysext_sha,
    prod_sha,
    usb_diagnostics,
    display_profile,
):
    """Build odm_b_android.img with merged permissive SELinux policy, GSI sha256s,
    Android keypad .kl files, and bring-up debugging configuration."""
    with tempfile.TemporaryDirectory(prefix="t440w-odm-") as work:
        def dump_opt(img, src, dst):
            with open(img, "rb") as fh:
                r = Ext4Reader(fh)
                try:
                    data = r.read_inode_data(r.resolve_path(src))
                except FileNotFoundError:
                    return None
                with open(dst, "wb") as out:
                    out.write(data)
                return data.decode("utf-8")

        plat_cil = dump_opt(gsi_img, "/system/etc/selinux/plat_sepolicy.cil", f"{work}/plat_sepolicy.cil")
        if plat_cil and "(common cap2 (mac_override mac_admin syslog wake_alarm block_suspend audit_read perfmon ))" in plat_cil:
            plat_cil = plat_cil.replace(
                "(common cap2 (mac_override mac_admin syslog wake_alarm block_suspend audit_read perfmon ))",
                "(common cap2 (mac_override mac_admin syslog wake_alarm block_suspend audit_read perfmon checkpoint_restore bpf ))",
            )
            with open(f"{work}/plat_sepolicy.cil", "w") as out:
                out.write(plat_cil)
        plat_m34 = dump_opt(gsi_img, "/system/etc/selinux/mapping/34.0.cil", f"{work}/plat_34.0.cil")
        se_cil = dump_opt(gsi_img, "/system/system_ext/etc/selinux/system_ext_sepolicy.cil", f"{work}/system_ext_sepolicy.cil")
        se_m34 = dump_opt(gsi_img, "/system/system_ext/etc/selinux/mapping/34.0.cil", f"{work}/se_34.0.cil")
        se_compat = dump_opt(gsi_img, "/system/system_ext/etc/selinux/mapping/34.0.compat.cil", f"{work}/se_34.0.compat.cil")
        pr_cil = dump_opt(gsi_img, "/system/product/etc/selinux/product_sepolicy.cil", f"{work}/product_sepolicy.cil")
        pr_m34 = dump_opt(gsi_img, "/system/product/etc/selinux/mapping/34.0.cil", f"{work}/pr_34.0.cil")

        ven_pub = dump_opt(vendor_img, "/etc/selinux/plat_pub_versioned.cil", f"{work}/plat_pub_versioned.cil")
        ven_cil = dump_opt(vendor_img, "/etc/selinux/vendor_sepolicy.cil", f"{work}/vendor_sepolicy.cil")

        cil_parts = [x for x in (plat_cil, plat_m34, se_cil, se_m34, se_compat, pr_cil, pr_m34, ven_pub) if x]
        combined_gsi = "\n".join(cil_parts)
        declared_types = set(re.findall(r"\(type\s+([a-zA-Z0-9_\-]+)\)", combined_gsi))
        declared_attrs = set(re.findall(r"\(typeattribute\s+([a-zA-Z0-9_\-]+)\)", combined_gsi))

        ven_all = (ven_pub or "") + "\n" + (ven_cil or "")
        refs_34 = set(re.findall(r"\b([a-zA-Z0-9_\-]+_34_0)\b", ven_all))
        compat_lines = []
        for r34 in sorted(refs_34):
            if r34 not in declared_attrs and r34 not in declared_types:
                compat_lines.append(f"(typeattribute {r34})")
            base = r34[:-5]
            if not base.startswith("base_typeattr_") and base not in declared_types and base not in declared_attrs:
                compat_lines.append(f"(type {base})")
                compat_lines.append(f"(roletype object_r {base})")
                compat_lines.append(f"(typeattributeset {r34} ({base}))")
                declared_types.add(base)

        compat_path = f"{work}/t440w_compat.cil"
        with open(compat_path, "w") as out:
            out.write("\n".join(compat_lines) + "\n")

        secilc_inputs = ["/work/plat_sepolicy.cil", "/work/plat_34.0.cil"]
        if se_cil:
            secilc_inputs.append("/work/system_ext_sepolicy.cil")
        if se_m34:
            secilc_inputs.append("/work/se_34.0.cil")
        if se_compat:
            secilc_inputs.append("/work/se_34.0.compat.cil")
        if pr_cil:
            secilc_inputs.append("/work/product_sepolicy.cil")
        if pr_m34:
            secilc_inputs.append("/work/pr_34.0.cil")
        secilc_inputs.extend([
            "/work/plat_pub_versioned.cil",
            "/work/t440w_compat.cil",
            "/work/vendor_sepolicy.cil",
        ])

        shutil.copyfile(stock_odm_img, f"{work}/odm.img")
        strip_existing_avb_footer(f"{work}/odm.img")

        with open(f"{work}/plat.sha256", "wb") as f:
            f.write(plat_sha)
        if sysext_sha:
            with open(f"{work}/sysext.sha256", "wb") as f:
                f.write(sysext_sha)
        if prod_sha:
            with open(f"{work}/prod.sha256", "wb") as f:
                f.write(prod_sha)

        # Prepare build.prop with bringup debugging properties
        with open(f"{work}/odm.img", "rb") as fh:
            r = Ext4Reader(fh)
            bp = r.read_inode_data(r.resolve_path("/etc/build.prop")).decode("utf-8")
        extra_props = []
        extra_props.extend([
            "persist.sys.phh.mainkeys=1",
            "qemu.hw.mainkeys=1",
        ])
        if usb_diagnostics:
            extra_props.extend([
                "ro.debuggable=1",
                "ro.adb.secure=0",
                "persist.sys.usb.config=adb",
                "persist.vendor.usb.config=adb",
                "service.adb.root=1",
            ])
        extra_props.extend(DISPLAY_PROFILES[display_profile])
        for ep in extra_props:
            key = ep.split("=", 1)[0]
            if key in ("persist.sys.phh.mainkeys", "qemu.hw.mainkeys"):
                bp = re.sub(
                    rf"^{re.escape(key)}=.*$",
                    ep,
                    bp,
                    count=1,
                    flags=re.M,
                )
                if f"{key}=" not in bp:
                    bp = bp.rstrip("\n") + "\n" + ep + "\n"
            elif f"{key}=" not in bp:
                bp = bp.rstrip("\n") + "\n" + ep + "\n"
        with open(f"{work}/build.prop", "w") as f:
            f.write(bp)

        # Copy Android keylayout files into workdir
        kl_dir = os.path.join(REPO_ROOT, "device", "t440w", "keylayout", "android")
        kl_names = ["soc_matrix_keypad0.kl", "gpio-keys.kl", "pm8941_pwrkey.kl", "pm8941_resin.kl"]
        for kn in kl_names:
            shutil.copyfile(os.path.join(kl_dir, kn), f"{work}/{kn}")
        if usb_diagnostics:
            shutil.copyfile(
                os.path.join(REPO_ROOT, "device", "t440w", "init", "init.t440w.debug.rc"),
                f"{work}/init.t440w.debug.rc",
            )
            shutil.copyfile(
                os.path.join(
                    REPO_ROOT,
                    "device",
                    "t440w",
                    "init",
                    "t440w-force-client-composition.sh",
                ),
                f"{work}/t440w-force-client-composition.sh",
            )

        # Build debugfs script to update odm.img (expanded to 348 blocks = 1,425,408 B,
        # which fits comfortably inside the 1,470,464 B odm partition with AVB footer)
        dbg_cmds = [
            "rm /etc/NOTICE.xml.gz",
            "rm /etc/selinux/precompiled_sepolicy",
            "write /work/precompiled_sepolicy /etc/selinux/precompiled_sepolicy",
            "sif /etc/selinux/precompiled_sepolicy mode 0100644",
            "sif /etc/selinux/precompiled_sepolicy uid 0",
            "sif /etc/selinux/precompiled_sepolicy gid 0",
            "ea_set -f /work/ctx.sp.bin /etc/selinux/precompiled_sepolicy security.selinux",
            "write /work/t440w_compat.cil /etc/selinux/odm_sepolicy.cil",
            "sif /etc/selinux/odm_sepolicy.cil mode 0100644",
            "sif /etc/selinux/odm_sepolicy.cil uid 0",
            "sif /etc/selinux/odm_sepolicy.cil gid 0",
            "ea_set -f /work/ctx.sp.bin /etc/selinux/odm_sepolicy.cil security.selinux",
            "rm /etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256",
            "write /work/plat.sha256 /etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256",
            "sif /etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256 mode 0100644",
            "sif /etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256 uid 0",
            "sif /etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256 gid 0",
            "ea_set -f /work/ctx.sp.bin /etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256 security.selinux",
            "rm /etc/selinux/precompiled_sepolicy.system_ext_sepolicy_and_mapping.sha256",
            "rm /etc/selinux/precompiled_sepolicy.product_sepolicy_and_mapping.sha256",
            "rm /etc/build.prop",
            "write /work/build.prop /etc/build.prop",
            "sif /etc/build.prop mode 0100600",
            "sif /etc/build.prop uid 0",
            "sif /etc/build.prop gid 0",
            "ea_set -f /work/ctx.bp.bin /etc/build.prop security.selinux",
            "mkdir /usr",
            "sif /usr mode 040755",
            "sif /usr uid 0",
            "sif /usr gid 0",
            "ea_set -f /work/ctx.vf.bin /usr security.selinux",
            "mkdir /usr/keylayout",
            "sif /usr/keylayout mode 040755",
            "sif /usr/keylayout uid 0",
            "sif /usr/keylayout gid 0",
            "ea_set -f /work/ctx.kl.bin /usr/keylayout security.selinux",
        ]
        if usb_diagnostics:
            dbg_cmds.extend([
                "mkdir /bin",
                "sif /bin mode 040755",
                "sif /bin uid 0",
                "sif /bin gid 0",
                "ea_set -f /work/ctx.vf.bin /bin security.selinux",
                "write /work/t440w-force-client-composition.sh /bin/t440w-force-client-composition.sh",
                "sif /bin/t440w-force-client-composition.sh mode 0100755",
                "sif /bin/t440w-force-client-composition.sh uid 0",
                "sif /bin/t440w-force-client-composition.sh gid 0",
                "ea_set -f /work/ctx.vf.bin /bin/t440w-force-client-composition.sh security.selinux",
                "mkdir /etc/init",
                "sif /etc/init mode 040755",
                "sif /etc/init uid 0",
                "sif /etc/init gid 0",
                "ea_set -f /work/ctx.vf.bin /etc/init security.selinux",
                "write /work/init.t440w.debug.rc /etc/init/init.t440w.debug.rc",
                "sif /etc/init/init.t440w.debug.rc mode 0100644",
                "sif /etc/init/init.t440w.debug.rc uid 0",
                "sif /etc/init/init.t440w.debug.rc gid 0",
                "ea_set -f /work/ctx.bp.bin /etc/init/init.t440w.debug.rc security.selinux",
            ])
        if sysext_sha:
            dbg_cmds.extend([
                "write /work/sysext.sha256 /etc/selinux/precompiled_sepolicy.system_ext_sepolicy_and_mapping.sha256",
                "sif /etc/selinux/precompiled_sepolicy.system_ext_sepolicy_and_mapping.sha256 mode 0100644",
                "sif /etc/selinux/precompiled_sepolicy.system_ext_sepolicy_and_mapping.sha256 uid 0",
                "sif /etc/selinux/precompiled_sepolicy.system_ext_sepolicy_and_mapping.sha256 gid 0",
                "ea_set -f /work/ctx.sp.bin /etc/selinux/precompiled_sepolicy.system_ext_sepolicy_and_mapping.sha256 security.selinux",
            ])
        if prod_sha:
            dbg_cmds.extend([
                "write /work/prod.sha256 /etc/selinux/precompiled_sepolicy.product_sepolicy_and_mapping.sha256",
                "sif /etc/selinux/precompiled_sepolicy.product_sepolicy_and_mapping.sha256 mode 0100644",
                "sif /etc/selinux/precompiled_sepolicy.product_sepolicy_and_mapping.sha256 uid 0",
                "sif /etc/selinux/precompiled_sepolicy.product_sepolicy_and_mapping.sha256 gid 0",
                "ea_set -f /work/ctx.sp.bin /etc/selinux/precompiled_sepolicy.product_sepolicy_and_mapping.sha256 security.selinux",
            ])
        for kn in kl_names:
            dbg_cmds.extend([
                f"write /work/{kn} /usr/keylayout/{kn}",
                f"sif /usr/keylayout/{kn} mode 0100644",
                f"sif /usr/keylayout/{kn} uid 0",
                f"sif /usr/keylayout/{kn} gid 0",
                f"ea_set -f /work/ctx.kl.bin /usr/keylayout/{kn} security.selinux",
            ])

        with open(f"{work}/debugfs.cmd", "w") as f:
            f.write("\n".join(dbg_cmds) + "\n")

        with open(f"{work}/ctx.sp.bin", "wb") as f:
            f.write(b"u:object_r:sepolicy_file:s0\x00")
        with open(f"{work}/ctx.bp.bin", "wb") as f:
            f.write(b"u:object_r:vendor_configs_file:s0\x00")
        with open(f"{work}/ctx.vf.bin", "wb") as f:
            f.write(b"u:object_r:vendor_file:s0\x00")
        with open(f"{work}/ctx.kl.bin", "wb") as f:
            f.write(b"u:object_r:vendor_keylayout_file:s0\x00")

        secilc_cmd = (
            "secilc -m -M true -G -N -c 30 -o /work/policy.bin -f /dev/null "
            + " ".join(secilc_inputs)
            + " && /usr/local/bin/setpermissive /work/policy.bin /work/precompiled_sepolicy"
            + " && e2fsck -fy /work/odm.img >/dev/null"
            + " && resize2fs /work/odm.img 338 >/dev/null"
            + " && debugfs -w -f /work/debugfs.cmd /work/odm.img >/dev/null"
            + " && e2fsck -fy /work/odm.img >/dev/null"
        )
        print(">> Compiling merged GSI + vendor SELinux policy and building odm_b_android.img ...")
        # SECURITY-REVIEW: CLI tool invoking local docker container t440w-tools:local with temporary workdir
        subprocess.run(
            ["docker", "run", "--rm", "-v", f"{work}:/work", "t440w-tools:local", "sh", "-c", secilc_cmd],
            check=True,
        )
        shutil.copyfile(f"{work}/odm.img", odm_out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gsi", help="Path to GSI image (.img, .img.xz, or .img.gz)")
    ap.add_argument("--out-dir", default="artifacts/build/android-flash", help="Output directory")
    ap.add_argument("--stock-odm-dbg", default="artifacts/build/odm_b-dbg-patched.img", help="Base permissive odm_b image")
    ap.add_argument("--stock-vendor", default="artifacts/build/vendor_b.img", help="Stock vendor_b.img")
    ap.add_argument("--stock-vbmeta", default="artifacts/build/vbmeta_b.img", help="Stock vbmeta_b.img")
    ap.add_argument("--stock-vbmeta-system", default="artifacts/build/vbmeta_system_b.img", help="Stock vbmeta_system_b.img")
    ap.add_argument(
        "--keypad-apk",
        default="artifacts/build/keypad-cursor/keypad-cursor.apk",
        help="Signed T440W keypad-cursor APK to embed in system",
    )
    ap.add_argument(
        "--usb-diagnostics",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Install forced-ADB/root diagnostics (default: enabled)",
    )
    ap.add_argument(
        "--display-profile",
        choices=sorted(DISPLAY_PROFILES),
        default="none",
        help="Opt-in display experiment; kept separate from USB diagnostics",
    )
    args = ap.parse_args()

    # SECURITY-REVIEW: CLI tool creating output directory for user-specified output path
    os.makedirs(args.out_dir, exist_ok=True)
    sys_img = os.path.join(args.out_dir, "system_b_android.img")

    # 1. Extract and unsparse GSI
    extract_or_copy(args.gsi, sys_img)
    unsparse_if_needed(sys_img)
    strip_existing_avb_footer(sys_img)

    # 2. Inspect GSI ext4 image & verify version, identity, and architecture
    with open(sys_img, "rb") as fh:
        reader = Ext4Reader(fh)
        build_props = parse_android_properties(
            reader.read_inode_data(reader.resolve_path("/system/build.prop"))
        )
        sdk = (
            build_props.get("ro.system.build.version.sdk")
            or build_props.get("ro.build.version.sdk")
        )
        fingerprint = (
            build_props.get("ro.system.build.fingerprint")
            or build_props.get("ro.build.fingerprint")
        )
        os_version = (
            build_props.get("ro.system.build.version.release")
            or build_props.get("ro.build.version.release")
        )
        security_patch = (
            build_props.get("ro.system.build.version.security_patch")
            or build_props.get("ro.build.version.security_patch")
        )
        if sdk != "34":
            raise SystemExit(
                f"error: GSI reports SDK {sdk or '<missing>'}, not SDK 34. "
                "The stock T440W vendor boundary is Android 14 / SDK 34."
            )
        if not fingerprint:
            raise SystemExit(
                "error: GSI does not report ro.system.build.fingerprint or "
                "ro.build.fingerprint"
            )
        if not os_version or not security_patch:
            raise SystemExit(
                "error: GSI is missing Android release or security-patch metadata"
            )
        print(">> Verified GSI identity:")
        print(f"   SDK         : {sdk}")
        print(f"   release     : {os_version}")
        print(f"   fingerprint : {fingerprint}")
        print(f"   patch level : {security_patch}")

        init_ino = reader.resolve_path("/system/bin/init")
        init_hdr = reader.read_inode_data(init_ino)[:20]
        if init_hdr[:4] != b"\x7fELF":
            raise SystemExit("error: /system/bin/init is not an ELF binary")
        ei_class = init_hdr[4]  # 1 = 32-bit, 2 = 64-bit
        e_machine = struct.unpack_from("<H", init_hdr, 18)[0]  # 40 (0x28) = EM_ARM
        print(f">> Verified /system/bin/init: ELF class={ei_class} ({'32-bit' if ei_class == 1 else '64-bit'}), machine={e_machine:#x}")
        if ei_class != 1 or e_machine != 0x28:
            raise SystemExit(
                "error: GSI /system/bin/init is NOT 32-bit ARM (EM_ARM). "
                "The TCL Flip 4 5G requires an a64 (arm32_binder64) GSI!"
            )

        plat_sha = reader.read_inode_data(
            reader.resolve_path("/system/etc/selinux/plat_sepolicy_and_mapping.sha256")
        )
        try:
            sysext_sha = reader.read_inode_data(
                reader.resolve_path("/system/system_ext/etc/selinux/system_ext_sepolicy_and_mapping.sha256")
            )
        except FileNotFoundError:
            sysext_sha = None
        try:
            prod_sha = reader.read_inode_data(
                reader.resolve_path("/system/product/etc/selinux/product_sepolicy_and_mapping.sha256")
            )
        except FileNotFoundError:
            prod_sha = None

        print(f">> Extracted GSI SELinux mapping hashes:")
        print(f"   plat      : {plat_sha.decode().strip()}")
        print(f"   system_ext: {sysext_sha.decode().strip() if sysext_sha else '<none>'}")
        print(f"   product   : {prod_sha.decode().strip() if prod_sha else '<none>'}")

        generic_kl = reader.read_inode_data(reader.resolve_path("/system/usr/keylayout/Generic.kl"))

    source_sha256 = sha256_file(args.gsi)
    manifest = {
        "device": "TCL Flip 4 5G (T440W)",
        "input": {
            "path": os.path.abspath(args.gsi),
            "sha256": source_sha256,
            "sdk": int(sdk),
            "release": os_version,
            "fingerprint": fingerprint,
            "security_patch": security_patch,
            "elf_class": ei_class,
            "elf_machine": e_machine,
        },
        "diagnostics": {
            "usb": args.usb_diagnostics,
            "display_profile": args.display_profile,
        },
        "keypad": {
            "apk": os.path.abspath(args.keypad_apk),
            "apk_sha256": sha256_file(args.keypad_apk),
        },
    }
    with open(os.path.join(args.out_dir, "build-manifest.json"), "w") as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")
    print(f">> Recorded exact input identity (sha256={source_sha256})")

    # 3. Patch Generic.kl in-place for the TCL Flip 4 5G keypad
    patched_kl, counts = patch_generic_kl_for_t440w(generic_kl)
    overwrite_ext4_file_same_size(sys_img, "/system/usr/keylayout/Generic.kl", patched_kl)
    print(f">> Patched /system/usr/keylayout/Generic.kl in-place for T440W keypad (subs={counts})")
    inject_keypad_system_files(sys_img, args.keypad_apk)
    print(">> Embedded T440W keypad cursor APK and boot enabler in system")

    # 4. Build odm_b_android.img with merged permissive precompiled_sepolicy, keylayouts, and debuggable props
    odm_out = os.path.join(args.out_dir, "odm_b_android.img")
    build_odm_android_image(
        sys_img,
        args.stock_vendor,
        args.stock_odm_dbg,
        odm_out,
        plat_sha,
        sysext_sha,
        prod_sha,
        args.usb_diagnostics,
        args.display_profile,
    )

    # Add AVB hashtree footer to odm_b_android.img and sign vbmeta_b_android.img
    # SECURITY-REVIEW: CLI tool invoking local python3 and vendored avbtool.py with static arguments
    subprocess.run(
        [
            sys.executable,
            "tooling/tools/avb/avbtool.py",
            "add_hashtree_footer",
            "--image", odm_out,
            "--partition_name", "odm",
            "--partition_size", "1470464",
            "--hash_algorithm", "sha256",
            "--block_size", "4096",
            "--do_not_generate_fec",
            "--salt", "5ff3ad795b534f56467f3d40354fee9798d15819f7f9a0f71cbbbe1b4b5459d5",
            "--prop", "com.android.build.odm.os_version:14",
            "--prop", "com.android.build.odm.fingerprint:TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys",
        ],
        check=True,
    )
    vbmeta_out = os.path.join(args.out_dir, "vbmeta_b_android.img")
    subprocess.run(
        [
            sys.executable,
            "tooling/scripts/patch_vbmeta.py",
            args.stock_vbmeta,
            "odm",
            "auto",
            "tooling/tools/avb/testkeys/testkey_rsa4096.pem",
            vbmeta_out,
            "--zero-fec",
            f"--from-image={odm_out}",
        ],
        check=True,
    )

    # 5. Add AVB hashtree footer to system_b_android.img and sign vbmeta_system_b_android.img
    raw_sys_sz = os.path.getsize(sys_img)
    part_sys_sz = calc_partition_size_for_avb(raw_sys_sz)
    print(f">> Adding AVB hashtree footer to {sys_img} (raw={raw_sys_sz} B, partition_size={part_sys_sz} B) ...")
    subprocess.run(
        [
            sys.executable,
            "tooling/tools/avb/avbtool.py",
            "add_hashtree_footer",
            "--image", sys_img,
            "--partition_name", "system",
            "--partition_size", str(part_sys_sz),
            "--hash_algorithm", "sha256",
            "--block_size", "4096",
            "--do_not_generate_fec",
            "--salt", "b1853b5bc80859b63e7708ed9f862b06ac7d76a06df0421e0544a370ee61b3d1",
            "--prop", f"com.android.build.system.os_version:{os_version}",
            "--prop", f"com.android.build.system.fingerprint:{fingerprint}",
            "--prop", f"com.android.build.system.security_patch:{security_patch}",
        ],
        check=True,
    )
    vbmeta_sys_out = os.path.join(args.out_dir, "vbmeta_system_b_android.img")
    subprocess.run(
        [
            sys.executable,
            "tooling/scripts/patch_vbmeta.py",
            args.stock_vbmeta_system,
            "system",
            "auto",
            "tooling/tools/avb/testkeys/testkey_rsa2048.pem",
            vbmeta_sys_out,
            "--zero-fec",
            f"--from-image={sys_img}",
        ],
        check=True,
    )

    # 6. Verify both vbmeta signatures with avbtool.py
    print(">> Verifying AVB signatures and embedded keys ...")
    verify_vbmeta_signature(
        vbmeta_out,
        "tooling/tools/avb/testkeys/testkey_rsa4096.pem",
    )
    verify_vbmeta_signature(
        vbmeta_sys_out,
        "tooling/tools/avb/testkeys/testkey_rsa2048.pem",
    )

    # 7. Build surgical super metadata
    subprocess.run(
        [
            sys.executable,
            "tooling/scripts/lp_make.py",
            "--surgical",
            "--system", sys_img,
            "--out-dir", args.out_dir,
        ],
        check=True,
    )
    print("\n>> Phase 1 offline preparation complete! Flash-ready artifacts in:", args.out_dir)


if __name__ == "__main__":
    main()
