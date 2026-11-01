#!/usr/bin/env python3
"""Build a current-safe T440W keypad profile from four exact signed images."""

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tooling", "scripts"))

from inspect_ext4 import Ext4Reader
from prepare_gsi import (
    inject_keypad_system_files,
    overwrite_ext4_file_same_size,
    parse_android_properties,
    patch_generic_kl_for_t440w,
    sha256_file,
    strip_existing_avb_footer,
    verify_vbmeta_signature,
)

AVBTOOL = os.path.join(REPO_ROOT, "tooling", "tools", "avb", "avbtool.py")
PATCH_VBMETA = os.path.join(REPO_ROOT, "tooling", "scripts", "patch_vbmeta.py")
KEY_2048 = os.path.join(
    REPO_ROOT, "tooling", "tools", "avb", "testkeys", "testkey_rsa2048.pem"
)
KEY_4096 = os.path.join(
    REPO_ROOT, "tooling", "tools", "avb", "testkeys", "testkey_rsa4096.pem"
)
KEYLAYOUT_DIR = os.path.join(REPO_ROOT, "device", "t440w", "keylayout", "android")
SYSTEM_EXTENT0_SECTORS = 1_240_920
SECTOR_SIZE = 512


def run(command):
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def descriptor_blobs(path):
    with open(path, "rb") as image:
        data = image.read()
    if data[:4] != b"AVB0":
        raise SystemExit(f"error: {path} is not a standalone vbmeta image")
    auth_size = struct.unpack_from(">Q", data, 12)[0]
    aux_size = struct.unpack_from(">Q", data, 20)[0]
    desc_off = struct.unpack_from(">Q", data, 96)[0]
    desc_size = struct.unpack_from(">Q", data, 104)[0]
    aux = data[256 + auth_size:256 + auth_size + aux_size]
    result = []
    position = desc_off
    end = desc_off + desc_size
    while position < end:
        tag, following = struct.unpack_from(">QQ", aux, position)
        blob = aux[position:position + 16 + following]
        result.append((tag, blob))
        position += 16 + following
    if position != end:
        raise SystemExit(f"error: malformed descriptor table in {path}")
    return result


def changed_descriptor_indexes(before_path, after_path):
    before = descriptor_blobs(before_path)
    after = descriptor_blobs(after_path)
    if len(before) != len(after):
        raise SystemExit("error: descriptor count changed")
    return [
        index
        for index, (old, new) in enumerate(zip(before, after))
        if old != new
    ]


def require_hash(path, expected, label):
    actual = sha256_file(path)
    if actual != expected:
        raise SystemExit(f"error: {label} hash {actual} != expected {expected}")
    return actual


def read_file(path):
    with open(path, "rb") as source:
        return source.read()


def verify_hashtree_image(image_path, partition_name):
    with tempfile.TemporaryDirectory(prefix=f"t440w-verify-{partition_name}-") as work:
        canonical = os.path.join(work, f"{partition_name}.img")
        os.symlink(os.path.abspath(image_path), canonical)
        run([sys.executable, AVBTOOL, "verify_image", "--image", canonical])


def update_odm_files(odm_path):
    with open(odm_path, "rb") as image:
        reader = Ext4Reader(image)
        build_prop = reader.read_inode_data(
            reader.resolve_path("/etc/build.prop")
        ).decode("utf-8")
    lines = [
        line for line in build_prop.splitlines()
        if not line.startswith("qemu.hw.mainkeys=")
        and not line.startswith("persist.sys.phh.mainkeys=")
    ]
    build_prop = (
        "\n".join(lines).rstrip("\n")
        + "\npersist.sys.phh.mainkeys=1\nqemu.hw.mainkeys=1\n"
    )

    with tempfile.TemporaryDirectory(prefix="t440w-keypad-odm-") as work:
        work_odm = os.path.join(work, "odm.img")
        shutil.copyfile(odm_path, work_odm)
        with open(os.path.join(work, "build.prop"), "w") as output:
            output.write(build_prop)
        shutil.copyfile(
            os.path.join(KEYLAYOUT_DIR, "soc_matrix_keypad0.kl"),
            os.path.join(work, "soc_matrix_keypad0.kl"),
        )
        shutil.copyfile(
            os.path.join(KEYLAYOUT_DIR, "pm8941_pwrkey.kl"),
            os.path.join(work, "pm8941_pwrkey.kl"),
        )
        shutil.copyfile(
            os.path.join(REPO_ROOT, "device", "t440w", "init", "init.t440w.debug.rc"),
            os.path.join(work, "init.t440w.debug.rc"),
        )
        with open(os.path.join(work, "ctx.bp.bin"), "wb") as output:
            output.write(b"u:object_r:vendor_configs_file:s0\x00")
        with open(os.path.join(work, "ctx.kl.bin"), "wb") as output:
            output.write(b"u:object_r:vendor_keylayout_file:s0\x00")
        commands = [
            "rm /etc/build.prop",
            "write /work/build.prop /etc/build.prop",
            "sif /etc/build.prop mode 0100600",
            "sif /etc/build.prop uid 0",
            "sif /etc/build.prop gid 0",
            "ea_set -f /work/ctx.bp.bin /etc/build.prop security.selinux",
            "rm /etc/init/init.t440w.debug.rc",
            "write /work/init.t440w.debug.rc /etc/init/init.t440w.debug.rc",
            "sif /etc/init/init.t440w.debug.rc mode 0100644",
            "sif /etc/init/init.t440w.debug.rc uid 0",
            "sif /etc/init/init.t440w.debug.rc gid 0",
            "ea_set -f /work/ctx.bp.bin /etc/init/init.t440w.debug.rc security.selinux",
        ]
        for name in ("soc_matrix_keypad0.kl", "pm8941_pwrkey.kl"):
            path = f"/usr/keylayout/{name}"
            commands.extend(
                [
                    f"rm {path}",
                    f"write /work/{name} {path}",
                    f"sif {path} mode 0100644",
                    f"sif {path} uid 0",
                    f"sif {path} gid 0",
                    f"ea_set -f /work/ctx.kl.bin {path} security.selinux",
                ]
            )
        with open(os.path.join(work, "debugfs.cmd"), "w") as output:
            output.write("\n".join(commands) + "\n")
        run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{work}:/work",
                "t440w-tools:local",
                "sh",
                "-c",
                "e2fsck -fy /work/odm.img >/dev/null"
                " && debugfs -w -f /work/debugfs.cmd /work/odm.img >/dev/null"
                " && e2fsck -fy /work/odm.img >/dev/null",
            ]
        )
        shutil.copyfile(work_odm, odm_path)

    expected = {
        "/etc/build.prop": build_prop.encode("utf-8"),
        "/usr/keylayout/soc_matrix_keypad0.kl": read_file(
            os.path.join(KEYLAYOUT_DIR, "soc_matrix_keypad0.kl")
        ),
        "/usr/keylayout/pm8941_pwrkey.kl": read_file(
            os.path.join(KEYLAYOUT_DIR, "pm8941_pwrkey.kl")
        ),
        "/etc/init/init.t440w.debug.rc": read_file(
            os.path.join(REPO_ROOT, "device", "t440w", "init", "init.t440w.debug.rc")
        ),
    }
    with open(odm_path, "rb") as image:
        reader = Ext4Reader(image)
        for path, expected_bytes in expected.items():
            actual = reader.read_inode_data(reader.resolve_path(path))
            if actual != expected_bytes:
                raise SystemExit(f"error: ODM embedded file mismatch: {path}")


def add_odm_footer(odm_path):
    run(
        [
            sys.executable,
            AVBTOOL,
            "add_hashtree_footer",
            "--image",
            odm_path,
            "--partition_name",
            "odm",
            "--partition_size",
            "1470464",
            "--hash_algorithm",
            "sha256",
            "--block_size",
            "4096",
            "--do_not_generate_fec",
            "--salt",
            "5ff3ad795b534f56467f3d40354fee9798d15819f7f9a0f71cbbbe1b4b5459d5",
            "--prop",
            "com.android.build.odm.os_version:14",
            "--prop",
            "com.android.build.odm.fingerprint:"
            "TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/"
            "jenkins12220921:user/test-keys",
        ]
    )
    verify_hashtree_image(odm_path, "odm")


def add_system_footer(system_path, partition_size):
    with open(system_path, "rb") as image:
        reader = Ext4Reader(image)
        props = parse_android_properties(
            reader.read_inode_data(reader.resolve_path("/system/build.prop"))
        )
    fingerprint = (
        props.get("ro.system.build.fingerprint")
        or props.get("ro.build.fingerprint")
    )
    os_version = (
        props.get("ro.system.build.version.release")
        or props.get("ro.build.version.release")
    )
    security_patch = (
        props.get("ro.system.build.version.security_patch")
        or props.get("ro.build.version.security_patch")
    )
    if not fingerprint or not os_version or not security_patch:
        raise SystemExit("error: incomplete system AVB properties")
    run(
        [
            sys.executable,
            AVBTOOL,
            "add_hashtree_footer",
            "--image",
            system_path,
            "--partition_name",
            "system",
            "--partition_size",
            str(partition_size),
            "--hash_algorithm",
            "sha256",
            "--block_size",
            "4096",
            "--do_not_generate_fec",
            "--salt",
            "b1853b5bc80859b63e7708ed9f862b06ac7d76a06df0421e0544a370ee61b3d1",
            "--prop",
            f"com.android.build.system.os_version:{os_version}",
            "--prop",
            f"com.android.build.system.fingerprint:{fingerprint}",
            "--prop",
            f"com.android.build.system.security_patch:{security_patch}",
        ]
    )
    verify_hashtree_image(system_path, "system")


def patch_vbmeta(source, partition, image, key, output):
    run(
        [
            sys.executable,
            PATCH_VBMETA,
            source,
            partition,
            "auto",
            key,
            output,
            "--zero-fec",
            f"--from-image={image}",
        ]
    )
    verify_vbmeta_signature(output, key)
    changed = changed_descriptor_indexes(source, output)
    if len(changed) != 1:
        raise SystemExit(
            f"error: expected one changed {partition} descriptor, got {changed}"
        )
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odm", required=True)
    parser.add_argument("--system", required=True)
    parser.add_argument("--vbmeta", required=True)
    parser.add_argument("--vbmeta-system", required=True)
    parser.add_argument("--expect-odm-sha256", required=True)
    parser.add_argument("--expect-system-sha256", required=True)
    parser.add_argument("--expect-vbmeta-sha256", required=True)
    parser.add_argument("--expect-vbmeta-system-sha256", required=True)
    parser.add_argument(
        "--keypad-apk",
        default="artifacts/build/keypad-cursor/keypad-cursor.apk",
    )
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    source_hashes = {
        "odm": require_hash(args.odm, args.expect_odm_sha256, "ODM"),
        "system": require_hash(args.system, args.expect_system_sha256, "system"),
        "vbmeta": require_hash(args.vbmeta, args.expect_vbmeta_sha256, "vbmeta"),
        "vbmeta_system": require_hash(
            args.vbmeta_system,
            args.expect_vbmeta_system_sha256,
            "vbmeta_system",
        ),
        "keypad_apk": sha256_file(args.keypad_apk),
    }
    source_sizes = {
        "odm": os.path.getsize(args.odm),
        "system": os.path.getsize(args.system),
        "vbmeta": os.path.getsize(args.vbmeta),
        "vbmeta_system": os.path.getsize(args.vbmeta_system),
    }

    os.makedirs(args.out_dir, exist_ok=True)
    odm_out = os.path.join(args.out_dir, "odm_b-keypad.img")
    system_out = os.path.join(args.out_dir, "system_b-keypad.img")
    vbmeta_out = os.path.join(args.out_dir, "vbmeta_b-keypad.img")
    vbmeta_system_out = os.path.join(args.out_dir, "vbmeta_system_b-keypad.img")

    shutil.copyfile(args.odm, odm_out)
    strip_existing_avb_footer(odm_out)
    if os.path.getsize(odm_out) != 1_384_448:
        raise SystemExit("error: unexpected raw ODM filesystem size")
    update_odm_files(odm_out)
    add_odm_footer(odm_out)

    shutil.copyfile(args.system, system_out)
    strip_existing_avb_footer(system_out)
    with open(system_out, "rb") as image:
        reader = Ext4Reader(image)
        generic_path = "/system/usr/keylayout/Generic.kl"
        generic = reader.read_inode_data(reader.resolve_path(generic_path))
    patched_generic, counts = patch_generic_kl_for_t440w(generic)
    if counts[1] != 1:
        raise SystemExit(f"error: expected one key-48 Generic.kl patch, got {counts}")
    overwrite_ext4_file_same_size(system_out, generic_path, patched_generic)
    inject_keypad_system_files(system_out, args.keypad_apk)
    add_system_footer(system_out, source_sizes["system"])

    changed_odm = patch_vbmeta(
        args.vbmeta, "odm", odm_out, KEY_4096, vbmeta_out
    )
    changed_system = patch_vbmeta(
        args.vbmeta_system,
        "system",
        system_out,
        KEY_2048,
        vbmeta_system_out,
    )

    outputs = {
        "odm": odm_out,
        "system": system_out,
        "vbmeta": vbmeta_out,
        "vbmeta_system": vbmeta_system_out,
    }
    for name, output in outputs.items():
        if os.path.getsize(output) != source_sizes[name]:
            raise SystemExit(
                f"error: {name} size changed from {source_sizes[name]} "
                f"to {os.path.getsize(output)}"
            )

    extent0_out = os.path.join(args.out_dir, "system_b-keypad-extent0.img")
    extent1_out = os.path.join(args.out_dir, "system_b-keypad-extent1.img")
    extent0_size = SYSTEM_EXTENT0_SECTORS * SECTOR_SIZE
    with open(system_out, "rb") as source:
        with open(extent0_out, "wb") as extent0:
            remaining = extent0_size
            while remaining:
                block = source.read(min(8 * 1024 * 1024, remaining))
                if not block:
                    raise SystemExit("error: system image ended in extent 0")
                extent0.write(block)
                remaining -= len(block)
        with open(extent1_out, "wb") as extent1:
            shutil.copyfileobj(source, extent1, 8 * 1024 * 1024)
    if os.path.getsize(extent0_out) != extent0_size:
        raise SystemExit("error: system extent 0 size mismatch")
    if os.path.getsize(extent1_out) != source_sizes["system"] - extent0_size:
        raise SystemExit("error: system extent 1 size mismatch")
    outputs["system_extent0"] = extent0_out
    outputs["system_extent1"] = extent1_out

    manifest = {
        "source": {
            "odm": {
                "path": os.path.abspath(args.odm),
                "sha256": source_hashes["odm"],
                "size": source_sizes["odm"],
            },
            "system": {
                "path": os.path.abspath(args.system),
                "sha256": source_hashes["system"],
                "size": source_sizes["system"],
            },
            "vbmeta": {
                "path": os.path.abspath(args.vbmeta),
                "sha256": source_hashes["vbmeta"],
                "size": source_sizes["vbmeta"],
            },
            "vbmeta_system": {
                "path": os.path.abspath(args.vbmeta_system),
                "sha256": source_hashes["vbmeta_system"],
                "size": source_sizes["vbmeta_system"],
            },
            "keypad_apk": {
                "path": os.path.abspath(args.keypad_apk),
                "sha256": source_hashes["keypad_apk"],
            },
        },
        "output": {
            name: {
                "path": os.path.abspath(path),
                "sha256": sha256_file(path),
                "size": os.path.getsize(path),
            }
            for name, path in outputs.items()
        },
        "changed_descriptor_indexes": {
            "vbmeta": changed_odm,
            "vbmeta_system": changed_system,
        },
        "system_extents": [
            {
                "name": "system_extent0",
                "raw_lba": 3_698_688,
                "sectors": SYSTEM_EXTENT0_SECTORS,
            },
            {
                "name": "system_extent1",
                "raw_lba": 6_254_592,
                "sectors": os.path.getsize(extent1_out) // SECTOR_SIZE,
            },
        ],
    }
    manifest_path = os.path.join(args.out_dir, "build-manifest.json")
    with open(manifest_path, "w") as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
