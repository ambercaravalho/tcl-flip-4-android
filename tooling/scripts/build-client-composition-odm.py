#!/usr/bin/env python3
"""Add the T440W forced-client init hook to an exact current ODM image.

The source ODM and top-level vbmeta hashes are mandatory guards. The output
changes only ODM contents and the ODM hashtree descriptor in vbmeta.
"""

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

from prepare_gsi import (
    normalize_ext4_metadata,
    sha256_file,
    strip_existing_avb_footer,
    verify_vbmeta_signature,
)
from inspect_ext4 import Ext4Reader

AVBTOOL = os.path.join(REPO_ROOT, "tooling", "tools", "avb", "avbtool.py")
PATCH_VBMETA = os.path.join(REPO_ROOT, "tooling", "scripts", "patch_vbmeta.py")
VBMETA_KEY = os.path.join(
    REPO_ROOT, "tooling", "tools", "avb", "testkeys", "testkey_rsa4096.pem"
)
INIT_RC = os.path.join(
    REPO_ROOT, "device", "t440w", "init", "init.t440w.platform.rc"
)
HELPER = os.path.join(
    REPO_ROOT, "device", "t440w", "init", "t440w-force-client-composition.sh"
)


def descriptor_blobs(path):
    data = open(path, "rb").read()
    if data[:4] != b"AVB0":
        raise SystemExit(f"error: {path} is not a standalone vbmeta image")
    auth_size = struct.unpack_from(">Q", data, 12)[0]
    aux_size = struct.unpack_from(">Q", data, 20)[0]
    desc_off = struct.unpack_from(">Q", data, 96)[0]
    desc_size = struct.unpack_from(">Q", data, 104)[0]
    aux = data[256 + auth_size:256 + auth_size + aux_size]
    result = []
    pos = desc_off
    end = desc_off + desc_size
    while pos < end:
        tag, following = struct.unpack_from(">QQ", aux, pos)
        blob = aux[pos:pos + 16 + following]
        result.append((tag, blob))
        pos += 16 + following
    if pos != end:
        raise SystemExit(f"error: malformed descriptor table in {path}")
    return result


def changed_descriptor_indexes(before, after):
    if len(before) != len(after):
        raise SystemExit("error: descriptor count changed")
    return [index for index, (old, new) in enumerate(zip(before, after)) if old != new]


def run(command):
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def ext4_has_path(image_path, path):
    with open(image_path, "rb") as image:
        reader = Ext4Reader(image)
        try:
            reader.resolve_path(path)
            return True
        except FileNotFoundError:
            return False


def verify_embedded_files(image_path):
    expected = {
        "/etc/init/init.t440w.platform.rc": INIT_RC,
        "/bin/t440w-force-client-composition.sh": HELPER,
    }
    with open(image_path, "rb") as image:
        reader = Ext4Reader(image)
        for target, source in expected.items():
            actual = reader.read_inode_data(reader.resolve_path(target))
            with open(source, "rb") as expected_file:
                if actual != expected_file.read():
                    raise SystemExit(f"error: embedded file mismatch: {target}")
        try:
            reader.resolve_path("/etc/init/init.t440w.debug.rc")
        except FileNotFoundError:
            pass
        else:
            raise SystemExit("error: debug init policy is present in release ODM")


def verify_selinux_label(image_path, target, expected):
    image_dir = os.path.dirname(os.path.abspath(image_path))
    image_name = os.path.basename(image_path)
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{image_dir}:/image:ro",
            "t440w-tools:local",
            "debugfs",
            "-R",
            f"ea_get {target} security.selinux",
            f"/image/{image_name}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if f'"{expected}\\000"' not in result.stdout:
        raise SystemExit(
            f"error: {target} SELinux label is not {expected}: "
            f"{result.stdout.strip()}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--odm", required=True, help="Exact current signed ODM image")
    parser.add_argument("--vbmeta", required=True, help="Exact current top-level vbmeta")
    parser.add_argument("--expect-odm-sha256", required=True)
    parser.add_argument("--expect-vbmeta-sha256", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    source_odm_hash = sha256_file(args.odm)
    source_vbmeta_hash = sha256_file(args.vbmeta)
    if source_odm_hash != args.expect_odm_sha256:
        raise SystemExit(
            f"error: ODM hash {source_odm_hash} != expected {args.expect_odm_sha256}"
        )
    if source_vbmeta_hash != args.expect_vbmeta_sha256:
        raise SystemExit(
            "error: vbmeta hash "
            f"{source_vbmeta_hash} != expected {args.expect_vbmeta_sha256}"
        )

    os.makedirs(args.out_dir, exist_ok=True)
    odm_out = os.path.join(args.out_dir, "odm_b-client-composition.img")
    vbmeta_out = os.path.join(args.out_dir, "vbmeta_b-client-composition.img")
    shutil.copyfile(args.odm, odm_out)
    strip_existing_avb_footer(odm_out)
    if os.path.getsize(odm_out) != 1_384_448:
        raise SystemExit("error: unexpected raw ODM filesystem size")
    has_bin = ext4_has_path(odm_out, "/bin")
    has_helper = ext4_has_path(
        odm_out, "/bin/t440w-force-client-composition.sh"
    )

    with tempfile.TemporaryDirectory(prefix="t440w-client-composition-") as work:
        work_odm = os.path.join(work, "odm.img")
        shutil.copyfile(odm_out, work_odm)
        shutil.copyfile(INIT_RC, os.path.join(work, "init.t440w.platform.rc"))
        shutil.copyfile(HELPER, os.path.join(work, "t440w-force-client-composition.sh"))
        open(os.path.join(work, "ctx.rc.bin"), "wb").write(
            b"u:object_r:vendor_configs_file:s0\x00"
        )
        open(os.path.join(work, "ctx.vendor.bin"), "wb").write(
            b"u:object_r:vendor_file:s0\x00"
        )
        open(os.path.join(work, "ctx.exec.bin"), "wb").write(
            b"u:object_r:vendor_shell_exec:s0\x00"
        )
        commands = [
            "rm /etc/init/init.t440w.platform.rc",
            "write /work/init.t440w.platform.rc /etc/init/init.t440w.platform.rc",
            "sif /etc/init/init.t440w.platform.rc mode 0100644",
            "sif /etc/init/init.t440w.platform.rc uid 0",
            "sif /etc/init/init.t440w.platform.rc gid 0",
            "ea_set -f /work/ctx.rc.bin /etc/init/init.t440w.platform.rc security.selinux",
        ]
        if not has_bin:
            commands.extend(
                [
                    "mkdir /bin",
                    "sif /bin mode 040755",
                    "sif /bin uid 0",
                    "sif /bin gid 0",
                    "ea_set -f /work/ctx.vendor.bin /bin security.selinux",
                ]
            )
        if has_helper:
            commands.append("rm /bin/t440w-force-client-composition.sh")
        commands.extend(
            [
                "write /work/t440w-force-client-composition.sh /bin/t440w-force-client-composition.sh",
                "sif /bin/t440w-force-client-composition.sh mode 0100755",
                "sif /bin/t440w-force-client-composition.sh uid 0",
                "sif /bin/t440w-force-client-composition.sh gid 0",
                "ea_set -f /work/ctx.exec.bin /bin/t440w-force-client-composition.sh security.selinux",
            ]
        )
        open(os.path.join(work, "debugfs.cmd"), "w").write("\n".join(commands) + "\n")
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
        shutil.copyfile(work_odm, odm_out)
        normalize_ext4_metadata(
            odm_out,
            [
                "/etc/init/init.t440w.platform.rc",
                "/bin/t440w-force-client-composition.sh",
            ],
        )

    run(
        [
            sys.executable,
            AVBTOOL,
            "add_hashtree_footer",
            "--image",
            odm_out,
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
    with tempfile.TemporaryDirectory(prefix="t440w-verify-odm-") as verify_dir:
        canonical_odm = os.path.join(verify_dir, "odm.img")
        shutil.copyfile(odm_out, canonical_odm)
        run([sys.executable, AVBTOOL, "verify_image", "--image", canonical_odm])
    verify_embedded_files(odm_out)
    verify_selinux_label(
        odm_out,
        "/bin/t440w-force-client-composition.sh",
        "u:object_r:vendor_shell_exec:s0",
    )
    verify_selinux_label(
        odm_out,
        "/etc/init/init.t440w.platform.rc",
        "u:object_r:vendor_configs_file:s0",
    )
    run(
        [
            sys.executable,
            PATCH_VBMETA,
            args.vbmeta,
            "odm",
            "auto",
            VBMETA_KEY,
            vbmeta_out,
            "--zero-fec",
            f"--from-image={odm_out}",
        ]
    )
    verify_vbmeta_signature(vbmeta_out, VBMETA_KEY)

    changed = changed_descriptor_indexes(
        descriptor_blobs(args.vbmeta), descriptor_blobs(vbmeta_out)
    )
    if len(changed) != 1:
        raise SystemExit(f"error: expected one changed descriptor, got indexes {changed}")

    manifest = {
        "source": {
            "odm": {"path": os.path.abspath(args.odm), "sha256": source_odm_hash},
            "vbmeta": {
                "path": os.path.abspath(args.vbmeta),
                "sha256": source_vbmeta_hash,
            },
        },
        "output": {
            "odm": {
                "path": os.path.abspath(odm_out),
                "sha256": sha256_file(odm_out),
            },
            "vbmeta": {
                "path": os.path.abspath(vbmeta_out),
                "sha256": sha256_file(vbmeta_out),
            },
        },
        "changed_descriptor_indexes": changed,
    }
    manifest_path = os.path.join(args.out_dir, "build-manifest.json")
    with open(manifest_path, "w") as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
