#!/usr/bin/env python3
"""Validate a full T440W eMMC dump and bind it to its EDL identity log."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import t440w_install_lib as install


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("identity_log", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    # SECURITY-REVIEW: image/log are user-controlled paths opened read-only;
    # the receipt path is fixed adjacent to the image and never follows a
    # user-provided output name.
    image = args.image.resolve()
    identity_log = args.identity_log.resolve()
    if not image.is_file():
        raise SystemExit(f"error: backup image not found: {image}")
    if not identity_log.is_file():
        raise SystemExit(f"error: EDL identity log not found: {identity_log}")

    manifest, assets = install.load_release()
    expected_size = (
        manifest["device"]["total_sectors"]
        * manifest["device"]["sector_size"]
    )
    if image.stat().st_size != expected_size:
        raise SystemExit(
            f"error: backup size is {image.stat().st_size}, "
            f"expected {expected_size}"
        )

    primary = install.read_gpt(image)
    secondary = install.read_gpt(
        image, header_lba=manifest["device"]["total_sectors"] - 1
    )
    if primary != secondary:
        raise SystemExit("error: primary and backup GPT geometry differ")
    install.verify_reference_gpt(primary, manifest, assets)
    geometry_digest = install.gpt_geometry_sha256(primary)
    identity = install.parse_edl_identity(
        identity_log.read_text(encoding="utf-8", errors="replace"), manifest
    )

    receipt_path = install.backup_receipt_path(image)
    if receipt_path.exists() and not args.force:
        raise SystemExit(
            f"error: receipt already exists: {receipt_path}; use --force "
            "only after confirming this is the same backup session"
        )
    digest = install.sha256_file(image, progress_label="full eMMC backup")
    receipt = {
        "schema": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "image_name": image.name,
        "size": image.stat().st_size,
        "sha256": digest,
        "device_identity": identity,
        "gpt_geometry_sha256": geometry_digest,
        "primary_and_backup_gpt_crc_valid": True,
    }
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OK  backup receipt: {receipt_path}")
    print(f"OK  backup SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
