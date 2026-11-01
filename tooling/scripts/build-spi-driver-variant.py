#!/usr/bin/env python3
"""Build signed vendor_dlkm/vbmeta images for one SPI driver test profile."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tooling", "scripts"))
from inspect_ext4 import Ext4Reader
from prepare_gsi import (
    overwrite_ext4_file_same_size,
    strip_existing_avb_footer,
    verify_vbmeta_signature,
)

PARTITION_SIZE = 53_796_864
MODULE_PATH = "/lib/modules/msm_drm.ko"
SALT = "5ff3ad795b534f56467f3d40354fee9798d15819f7f9a0f71cbbbe1b4b5459d5"
FINGERPRINT = (
    "TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/"
    "jenkins12220921:user/test-keys"
)


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while chunk := source.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile", choices=("immutable", "coalesce", "full-height-client")
    )
    parser.add_argument("--out-dir", default="artifacts/build/spi-driver-tests")
    parser.add_argument(
        "--stock-vendor-dlkm", default="artifacts/build/vendor_dlkm_b.img"
    )
    parser.add_argument("--stock-vbmeta", default="artifacts/build/vbmeta_b.img")
    parser.add_argument("--odm", default="artifacts/build/odm_b-dbg-patched.img")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    module_out = os.path.join(args.out_dir, f"msm_drm-{args.profile}.ko")
    vendor_out = os.path.join(
        args.out_dir, f"vendor_dlkm_b-{args.profile}.img"
    )
    vbmeta_out = os.path.join(args.out_dir, f"vbmeta_b-{args.profile}.img")

    with open(args.stock_vendor_dlkm, "rb") as source:
        reader = Ext4Reader(source)
        stock_module = reader.read_inode_data(reader.resolve_path(MODULE_PATH))

    with tempfile.TemporaryDirectory(prefix="t440w-spi-variant-") as work:
        stock_module_path = os.path.join(work, "msm_drm.ko")
        patched_module_path = os.path.join(work, "msm_drm-patched.ko")
        with open(stock_module_path, "wb") as module:
            module.write(stock_module)

        subprocess.run(
            [
                sys.executable,
                "tooling/scripts/patch-msm-drm-spi.py",
                stock_module_path,
                args.profile,
                patched_module_path,
            ],
            check=True,
        )
        shutil.copyfile(patched_module_path, module_out)

        shutil.copyfile(args.stock_vendor_dlkm, vendor_out)
        strip_existing_avb_footer(vendor_out)
        with open(patched_module_path, "rb") as module:
            overwrite_ext4_file_same_size(
                vendor_out, MODULE_PATH, module.read()
            )

        subprocess.run(
            [
                sys.executable,
                "tooling/tools/avb/avbtool.py",
                "add_hashtree_footer",
                "--image", vendor_out,
                "--partition_name", "vendor_dlkm",
                "--partition_size", str(PARTITION_SIZE),
                "--hash_algorithm", "sha256",
                "--block_size", "4096",
                "--do_not_generate_fec",
                "--salt", SALT,
                "--prop", "com.android.build.vendor_dlkm.os_version:14",
                "--prop",
                f"com.android.build.vendor_dlkm.fingerprint:{FINGERPRINT}",
            ],
            check=True,
        )

        odm_vbmeta = os.path.join(work, "vbmeta-odm.img")
        subprocess.run(
            [
                sys.executable,
                "tooling/scripts/patch_vbmeta.py",
                args.stock_vbmeta,
                "odm",
                "auto",
                "tooling/tools/avb/testkeys/testkey_rsa4096.pem",
                odm_vbmeta,
                "--zero-fec",
                f"--from-image={args.odm}",
            ],
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "tooling/scripts/patch_vbmeta.py",
                odm_vbmeta,
                "vendor_dlkm",
                "auto",
                "tooling/tools/avb/testkeys/testkey_rsa4096.pem",
                vbmeta_out,
                "--zero-fec",
                f"--from-image={vendor_out}",
            ],
            check=True,
        )
        with open(vendor_out, "rb") as vendor_image:
            reader = Ext4Reader(vendor_image)
            embedded_module = reader.read_inode_data(
                reader.resolve_path(MODULE_PATH)
            )
        if embedded_module != open(patched_module_path, "rb").read():
            raise RuntimeError(
                f"{vendor_out}: embedded {MODULE_PATH} failed read-back"
            )
        verify_vbmeta_signature(
            vbmeta_out,
            "tooling/tools/avb/testkeys/testkey_rsa4096.pem",
        )

    manifest = {
        "profile": args.profile,
        "module": {"path": module_out, "sha256": sha256(module_out)},
        "vendor_dlkm": {"path": vendor_out, "sha256": sha256(vendor_out)},
        "vbmeta": {"path": vbmeta_out, "sha256": sha256(vbmeta_out)},
    }
    manifest_path = os.path.join(
        args.out_dir, f"manifest-{args.profile}.json"
    )
    with open(manifest_path, "w") as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")
    print(f"wrote {manifest_path}")


if __name__ == "__main__":
    main()
