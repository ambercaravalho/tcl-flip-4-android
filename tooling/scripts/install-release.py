#!/usr/bin/env python3
"""Verify, back up, and flash a frozen T440W Android release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone
from typing import Any

import t440w_install_lib as install


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "tooling/releases/v0.1.0.json"
EXPECTED_MANIFEST_SHA256 = (
    "bcfb36e7892e649de3b7e171976f5cf47ee64616751c20b838301c5b3f87c7b3"
)
EDL = REPO_ROOT / "tooling/scripts/edl"
SECTOR_SIZE = 512
GPT_SIGNATURE = b"EFI PART"
READ_GPT_SECTORS = 34
RELEASE_REPOSITORY = "ambercaravalho/tcl-flip-4-android"


def sha256_file(path: Path, *, progress_label: str | None = None) -> str:
    digest = hashlib.sha256()
    processed = 0
    next_report = 1024 * 1024 * 1024
    total = path.stat().st_size
    if progress_label is not None:
        print(
            f">> Hashing {progress_label}: {total / (1024 ** 3):.2f} GiB",
            flush=True,
        )
    with path.open("rb") as source:
        while chunk := source.read(8 * 1024 * 1024):
            digest.update(chunk)
            processed += len(chunk)
            if progress_label is not None and processed >= next_report:
                print(
                    f"   {processed / (1024 ** 3):.1f} / "
                    f"{total / (1024 ** 3):.1f} GiB",
                    flush=True,
                )
                next_report += 1024 * 1024 * 1024
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    # SECURITY-REVIEW: release/receipt JSON is untrusted input; callers validate
    # its schema, allowlisted names, sizes, hashes, and numeric ranges before use.
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"error: expected a JSON object in {path}")
    return value


def require_hex_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SystemExit(f"error: {label} must be a lowercase SHA-256")
    return value


def require_positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise SystemExit(f"error: {label} must be a positive integer")
    return value


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema") != 1 or manifest.get("release") != "v0.1.0":
        raise SystemExit("error: unsupported release manifest")
    device = manifest.get("device")
    loader = manifest.get("loader")
    assets = manifest.get("assets")
    if not isinstance(device, dict) or not isinstance(loader, dict):
        raise SystemExit("error: manifest device/loader object missing")
    if not isinstance(assets, list) or len(assets) != 8:
        raise SystemExit("error: v0.1.0 manifest must contain exactly 8 assets")
    if device.get("model") != "T440W":
        raise SystemExit("error: manifest does not target T440W")
    if device.get("hwid") != "0x002980e100420071":
        raise SystemExit("error: unexpected manifest HWID")
    if device.get("target_slot") != "b":
        raise SystemExit("error: v0.1.0 must target slot B")
    if device.get("sector_size") != SECTOR_SIZE:
        raise SystemExit("error: unsupported sector size")
    require_positive_int(device.get("total_sectors"), "device.total_sectors")
    require_positive_int(device.get("super_sectors"), "device.super_sectors")
    require_hex_digest(
        device.get("gpt_geometry_sha256"), "device.gpt_geometry_sha256"
    )
    require_hex_digest(loader.get("sha256"), "loader.sha256")
    if loader.get("path") != "tooling/loader/flip-4-edl.bin":
        raise SystemExit("error: unexpected loader path")

    names: set[str] = set()
    targets: set[str] = set()
    ranges: list[tuple[int, int, str]] = []
    kinds = ("payload", "metadata", "verification")
    seen_kind = 0
    for index, raw in enumerate(assets):
        if not isinstance(raw, dict):
            raise SystemExit(f"error: assets[{index}] is not an object")
        name = raw.get("name")
        source = raw.get("source")
        target = raw.get("target")
        kind = raw.get("kind")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or name in names
            or not name.endswith(".img")
        ):
            raise SystemExit(f"error: unsafe or duplicate asset name {name!r}")
        if not isinstance(source, str) or Path(source).is_absolute() or ".." in Path(source).parts:
            raise SystemExit(f"error: unsafe source path for {name}")
        if (
            not isinstance(target, str)
            or not re.fullmatch(r"[a-z0-9_]+", target)
            or target in targets
        ):
            raise SystemExit(f"error: unsafe target name for {name}")
        if kind not in kinds:
            raise SystemExit(f"error: unsupported kind for {name}")
        kind_number = kinds.index(kind)
        if kind_number < seen_kind:
            raise SystemExit("error: manifest write order regresses from metadata")
        seen_kind = kind_number
        size = require_positive_int(raw.get("size"), f"{name}.size")
        lba = require_positive_int(raw.get("raw_lba"), f"{name}.raw_lba")
        sectors = require_positive_int(raw.get("sectors"), f"{name}.sectors")
        if size != sectors * SECTOR_SIZE:
            raise SystemExit(f"error: {name} size does not equal its raw range")
        require_hex_digest(raw.get("sha256"), f"{name}.sha256")
        end = lba + sectors
        for other_start, other_end, other_name in ranges:
            if max(lba, other_start) < min(end, other_end):
                raise SystemExit(
                    f"error: {name} overlaps {other_name} in the manifest"
                )
        ranges.append((lba, end, name))
        names.add(name)
        targets.add(target)
    if assets[-1].get("target") != "vbmeta_b":
        raise SystemExit("error: top-level vbmeta must be written last")
    return assets


def resolve_repo_path(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"error: path escapes repository: {relative}") from exc
    return path


def verify_loader(manifest: dict[str, Any]) -> Path:
    loader_info = manifest["loader"]
    loader = resolve_repo_path(loader_info["path"])
    if not loader.is_file():
        raise SystemExit(f"error: missing EDL loader: {loader}")
    actual = sha256_file(loader)
    if actual != loader_info["sha256"]:
        raise SystemExit(
            f"error: EDL loader SHA-256 mismatch: {actual} "
            f"(expected {loader_info['sha256']})"
        )
    return loader


def verify_assets(
    release_dir: Path,
    assets: list[dict[str, Any]],
    *,
    show: bool = True,
) -> dict[str, Path]:
    # SECURITY-REVIEW: release_dir is user-controlled. Asset names are validated
    # basename-only allowlist entries before paths are resolved and opened.
    if not release_dir.is_dir():
        raise SystemExit(f"error: release directory not found: {release_dir}")
    root = release_dir.resolve()
    result: dict[str, Path] = {}
    for asset in assets:
        path = (root / asset["name"]).resolve()
        if path.parent != root:
            raise SystemExit(f"error: asset path escapes release directory: {path}")
        if not path.is_file():
            raise SystemExit(f"error: missing release asset: {asset['name']}")
        size = path.stat().st_size
        if size != asset["size"]:
            raise SystemExit(
                f"error: {asset['name']} size is {size}, expected {asset['size']}"
            )
        digest = sha256_file(path)
        if digest != asset["sha256"]:
            raise SystemExit(
                f"error: {asset['name']} SHA-256 is {digest}, "
                f"expected {asset['sha256']}"
            )
        result[asset["name"]] = path
        if show:
            print(f"OK  {asset['name']}  {digest}")
    return result


def download_asset(url: str, destination: Path, expected_size: int) -> None:
    partial = destination.with_name(f"{destination.name}.part")
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > expected_size:
        partial.write_bytes(b"")
        offset = 0
    request = urllib.request.Request(
        url,
        headers={"Range": f"bytes={offset}-"} if offset else {},
    )
    try:
        response = urllib.request.urlopen(request)
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and offset == expected_size:
            partial.replace(destination)
            return
        raise SystemExit(f"error: download failed for {url}: {exc}") from exc
    append = offset > 0 and getattr(response, "status", 200) == 206
    if not append:
        offset = 0
    mode = "ab" if append else "wb"
    print(f">> Downloading {destination.name}", flush=True)
    with response, partial.open(mode) as output:
        written = offset
        next_report = ((written // (256 * 1024 * 1024)) + 1) * (
            256 * 1024 * 1024
        )
        while chunk := response.read(8 * 1024 * 1024):
            output.write(chunk)
            written += len(chunk)
            if written >= next_report:
                print(
                    f"   {written / (1024 ** 2):.0f} / "
                    f"{expected_size / (1024 ** 2):.0f} MiB",
                    flush=True,
                )
                next_report += 256 * 1024 * 1024
    if partial.stat().st_size != expected_size:
        raise SystemExit(
            f"error: incomplete download for {destination.name}: "
            f"{partial.stat().st_size} of {expected_size} bytes"
        )
    partial.replace(destination)


def ensure_release_assets(
    manifest: dict[str, Any],
    assets: list[dict[str, Any]],
) -> tuple[Path, dict[str, Path]]:
    release = manifest["release"]
    release_dir = REPO_ROOT / "artifacts/releases" / release
    release_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}
    for asset in assets:
        path = release_dir / asset["name"]
        valid = (
            path.is_file()
            and path.stat().st_size == asset["size"]
            and sha256_file(path) == asset["sha256"]
        )
        if not valid:
            quoted = urllib.parse.quote(asset["name"])
            url = (
                f"https://github.com/{RELEASE_REPOSITORY}/releases/download/"
                f"{release}/{quoted}"
            )
            download_asset(url, path, asset["size"])
            digest = sha256_file(path)
            if digest != asset["sha256"]:
                raise SystemExit(
                    f"error: downloaded {asset['name']} SHA-256 is {digest}, "
                    f"expected {asset['sha256']}"
                )
        print(f"OK  {asset['name']}")
        result[asset["name"]] = path
    return release_dir, result


def read_gpt(
    path: Path, *, header_lba: int = 1
) -> list[tuple[str, int, int]]:
    # SECURITY-REVIEW: path may be user-controlled. Reads are bounded by GPT
    # header values, CRC-checked, with conservative table limits.
    with path.open("rb") as image:
        image.seek(header_lba * SECTOR_SIZE)
        header = image.read(SECTOR_SIZE)
        if header[:8] != GPT_SIGNATURE:
            raise SystemExit(
                f"error: no GPT signature at LBA {header_lba} in {path}"
            )
        current_lba = struct.unpack_from("<Q", header, 24)[0]
        if current_lba != header_lba:
            raise SystemExit(
                f"error: GPT header at LBA {header_lba} claims LBA "
                f"{current_lba} in {path}"
            )
        header_size = struct.unpack_from("<I", header, 12)[0]
        header_crc = struct.unpack_from("<I", header, 16)[0]
        if not (92 <= header_size <= SECTOR_SIZE):
            raise SystemExit(f"error: invalid GPT header size in {path}")
        crc_header = bytearray(header[:header_size])
        crc_header[16:20] = b"\0" * 4
        if zlib.crc32(crc_header) & 0xFFFFFFFF != header_crc:
            raise SystemExit(
                f"error: GPT header CRC mismatch at LBA {header_lba} in {path}"
            )
        entry_lba = struct.unpack_from("<Q", header, 72)[0]
        entry_count = struct.unpack_from("<I", header, 80)[0]
        entry_size = struct.unpack_from("<I", header, 84)[0]
        table_crc = struct.unpack_from("<I", header, 88)[0]
        if not (1 <= entry_count <= 4096 and 128 <= entry_size <= 1024):
            raise SystemExit(f"error: unreasonable GPT table geometry in {path}")
        table_size = entry_count * entry_size
        image.seek(entry_lba * SECTOR_SIZE)
        table = image.read(table_size)
        if len(table) != table_size:
            raise SystemExit(f"error: truncated GPT table in {path}")
        if zlib.crc32(table) & 0xFFFFFFFF != table_crc:
            raise SystemExit(
                f"error: GPT table CRC mismatch at LBA {header_lba} in {path}"
            )

    partitions = []
    for index in range(entry_count):
        entry = table[index * entry_size:(index + 1) * entry_size]
        if entry[:16] == b"\0" * 16:
            continue
        first, last = struct.unpack_from("<QQ", entry, 32)
        if first > last:
            raise SystemExit(f"error: invalid GPT range at entry {index}")
        try:
            name = entry[56:128].decode("utf-16-le").rstrip("\0")
        except UnicodeDecodeError as exc:
            raise SystemExit(f"error: invalid GPT name at entry {index}") from exc
        partitions.append((name, first, last))
    return partitions


def gpt_geometry_sha256(parts: list[tuple[str, int, int]]) -> str:
    geometry = [
        [name, first, last - first + 1] for name, first, last in parts
    ]
    encoded = json.dumps(
        geometry, ensure_ascii=True, separators=(",", ":")
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def partition_map(parts: list[tuple[str, int, int]]) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for name, first, last in parts:
        if name in result:
            raise SystemExit(f"error: duplicate GPT partition {name}")
        result[name] = (first, last - first + 1)
    return result


def verify_reference_gpt(
    parts: list[tuple[str, int, int]],
    manifest: dict[str, Any],
    assets: list[dict[str, Any]],
) -> None:
    expected_geometry = manifest["device"]["gpt_geometry_sha256"]
    actual_geometry = gpt_geometry_sha256(parts)
    if actual_geometry != expected_geometry:
        raise SystemExit(
            f"error: GPT geometry digest is {actual_geometry}, "
            f"expected {expected_geometry}"
        )
    mapped = partition_map(parts)
    for target in ("vbmeta_system_b", "init_boot_b", "vbmeta_b"):
        asset = next(item for item in assets if item["target"] == target)
        actual = mapped.get(target)
        expected = (asset["raw_lba"], asset["sectors"])
        if actual != expected:
            raise SystemExit(
                f"error: GPT {target} is {actual}, expected {expected}"
            )
    super_range = mapped.get("super")
    expected_super = (3686400, manifest["device"]["super_sectors"])
    if super_range != expected_super:
        raise SystemExit(
            f"error: GPT super range is {super_range}, expected {expected_super}"
        )
    super_start, super_sectors = super_range
    super_end = super_start + super_sectors
    for asset in assets:
        if asset["target"] in ("vbmeta_system_b", "init_boot_b", "vbmeta_b"):
            continue
        start = asset["raw_lba"]
        end = start + asset["sectors"]
        if start < super_start or end > super_end:
            raise SystemExit(
                f"error: {asset['name']} range is outside GPT super partition"
            )


def parse_edl_identity(
    output: str, manifest: dict[str, Any]
) -> dict[str, Any]:
    expected_hwid = manifest["device"]["hwid"].lower()
    hwid_match = re.search(
        r"(?i)\bhwid\b[^0-9a-f]*(0x[0-9a-f]{16})", output
    )
    chip_match = re.search(
        r"(?i)Chip serial num:\s*\d+\s*\((0x[0-9a-f]+)\)", output
    )
    emmc_match = re.search(r"(?im)^\s*firehose - serial_num:(\d+)\s*$", output)
    blocks_match = re.search(
        r"(?im)^\s*firehose - total_blocks:(\d+)\s*$", output
    )
    block_size_match = re.search(
        r"(?im)^\s*firehose - block_size:(\d+)\s*$", output
    )
    if not all(
        (hwid_match, chip_match, emmc_match, blocks_match, block_size_match)
    ):
        raise SystemExit("error: incomplete HWID/storage identity in EDL output")
    assert hwid_match is not None
    assert chip_match is not None
    assert emmc_match is not None
    assert blocks_match is not None
    assert block_size_match is not None
    hwid = hwid_match.group(1).lower()
    total_blocks = int(blocks_match.group(1))
    block_size = int(block_size_match.group(1))
    if hwid != expected_hwid:
        raise SystemExit(f"error: live HWID is {hwid}, expected {expected_hwid}")
    if total_blocks != manifest["device"]["total_sectors"]:
        raise SystemExit(
            f"error: live storage has {total_blocks} sectors, expected "
            f"{manifest['device']['total_sectors']}"
        )
    if block_size != manifest["device"]["sector_size"]:
        raise SystemExit(
            f"error: live block size is {block_size}, expected {SECTOR_SIZE}"
        )
    return {
        "hwid": hwid,
        "chip_serial": chip_match.group(1).lower(),
        "emmc_serial": int(emmc_match.group(1)),
        "total_blocks": total_blocks,
        "block_size": block_size,
    }


def backup_receipt_path(backup: Path) -> Path:
    return backup.with_name(f"{backup.name}.receipt.json")


def verify_full_backup(
    backup: Path,
    manifest: dict[str, Any],
    assets: list[dict[str, Any]],
) -> dict[str, Any]:
    # SECURITY-REVIEW: backup is a user-controlled path opened read-only after
    # type/size/GPT checks. The tool never writes to the full backup.
    if not backup.is_file():
        raise SystemExit(f"error: full backup not found: {backup}")
    expected_size = (
        manifest["device"]["total_sectors"] * manifest["device"]["sector_size"]
    )
    if backup.stat().st_size != expected_size:
        raise SystemExit(
            f"error: full backup size is {backup.stat().st_size}, "
            f"expected {expected_size}"
        )
    primary_parts = read_gpt(backup)
    secondary_parts = read_gpt(
        backup, header_lba=manifest["device"]["total_sectors"] - 1
    )
    if primary_parts != secondary_parts:
        raise SystemExit("error: primary and backup GPT geometry differ")
    verify_reference_gpt(primary_parts, manifest, assets)
    geometry_digest = gpt_geometry_sha256(primary_parts)
    receipt_path = backup_receipt_path(backup)
    receipt = load_json(receipt_path)
    if receipt.get("schema") != 1:
        raise SystemExit(f"error: unsupported full-backup receipt: {receipt_path}")
    identity = receipt.get("device_identity")
    if not isinstance(identity, dict):
        raise SystemExit("error: full-backup receipt lacks device identity")
    if identity.get("hwid") != manifest["device"]["hwid"].lower():
        raise SystemExit("error: full-backup receipt has the wrong HWID")
    if identity.get("total_blocks") != manifest["device"]["total_sectors"]:
        raise SystemExit("error: full-backup receipt has the wrong storage size")
    if identity.get("block_size") != manifest["device"]["sector_size"]:
        raise SystemExit("error: full-backup receipt has the wrong block size")
    if not isinstance(identity.get("chip_serial"), str) or not isinstance(
        identity.get("emmc_serial"), int
    ):
        raise SystemExit("error: full-backup receipt has invalid serial identity")
    if receipt.get("gpt_geometry_sha256") != geometry_digest:
        raise SystemExit("error: full-backup receipt GPT identity mismatch")
    if receipt.get("size") != expected_size:
        raise SystemExit("error: full-backup receipt size mismatch")
    digest = sha256_file(backup, progress_label="full eMMC backup")
    if receipt.get("sha256") != digest:
        raise SystemExit("error: full-backup receipt SHA-256 mismatch")
    print(f"OK  full backup  {digest}")
    return {
        "sha256": digest,
        "device_identity": identity,
        "gpt_geometry_sha256": geometry_digest,
    }


def run_edl(
    args: list[str],
    loader: Path,
    log_path: Path,
    *,
    capture: bool = False,
) -> str:
    command = [
        str(EDL),
        *args,
        f"--loader={loader}",
        "--memory=emmc",
    ]
    # SECURITY-REVIEW: subprocess arguments are fixed commands plus manifest-
    # validated integers and repository-contained paths; shell execution is off.
    log_path.parent.mkdir(parents=True, exist_ok=True)
    output_lines: list[str] = []
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log.write(line)
            if capture:
                output_lines.append(line)
        status = process.wait()
    if status != 0:
        raise SystemExit(
            f"error: EDL command failed with status {status}; see {log_path}"
        )
    return "".join(output_lines)


def probe_live(
    manifest: dict[str, Any],
    assets: list[dict[str, Any]],
    loader: Path,
    log_dir: Path,
) -> dict[str, Any]:
    log_dir.mkdir(parents=True, exist_ok=True)
    output = run_edl(
        ["printgpt", "--skipresponse"],
        loader,
        log_dir / "printgpt.log",
        capture=True,
    )
    identity = parse_edl_identity(output, manifest)

    with tempfile.TemporaryDirectory(prefix="t440w-live-gpt-") as temp:
        gpt_path = Path(temp) / "primary-gpt.img"
        run_edl(
            ["rs", "0", str(READ_GPT_SECTORS), str(gpt_path), "--skipresponse"],
            loader,
            log_dir / "read-primary-gpt.log",
        )
        if gpt_path.stat().st_size != READ_GPT_SECTORS * SECTOR_SIZE:
            raise SystemExit("error: live primary GPT read has unexpected size")
        parts = read_gpt(gpt_path)
        verify_reference_gpt(parts, manifest, assets)
        identity["primary_gpt_sha256"] = sha256_file(gpt_path)
        identity["gpt_geometry_sha256"] = gpt_geometry_sha256(parts)
    print(
        "OK  live T440W identity and exact GPT geometry  "
        f"{identity['gpt_geometry_sha256']}"
    )
    return identity


def print_plan(manifest: dict[str, Any], assets: list[dict[str, Any]]) -> None:
    print()
    print(f"Release: {manifest['release']}")
    print("Target : T440W slot B")
    print("Mode   : VERIFY/PLAN ONLY (no device access)")
    print()
    print("Write and immediate full read-back order:")
    for number, asset in enumerate(assets, start=1):
        print(
            f" {number}. {asset['target']:<20} "
            f"LBA {asset['raw_lba']:<8} sectors {asset['sectors']:<8} "
            f"{asset['name']}"
        )
    print()
    print("Run with --probe-edl for a read-only live identity/GPT check.")


def target_backup_name(asset: dict[str, Any]) -> str:
    return f"{asset['target']}-before.img"


def require_same_device(
    backup_state: dict[str, Any], live_identity: dict[str, Any]
) -> None:
    backup_identity = backup_state["device_identity"]
    for field in (
        "hwid",
        "chip_serial",
        "emmc_serial",
        "total_blocks",
        "block_size",
    ):
        if backup_identity.get(field) != live_identity.get(field):
            raise SystemExit(
                f"error: connected phone {field} does not match the full "
                "backup receipt"
            )
    if (
        backup_state["gpt_geometry_sha256"]
        != live_identity["gpt_geometry_sha256"]
    ):
        raise SystemExit(
            "error: connected phone GPT does not match the full backup receipt"
        )
    print("OK  full backup receipt belongs to the connected phone")


def backup_targets(
    manifest: dict[str, Any],
    assets: list[dict[str, Any]],
    loader: Path,
    full_backup: Path,
    output: Path | None,
) -> Path:
    full_state = verify_full_backup(full_backup, manifest, assets)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    release = manifest["release"]
    backup_dir = (
        output
        if output is not None
        else REPO_ROOT / "artifacts/backups" / f"pre-{release}" / stamp
    )
    # SECURITY-REVIEW: output is user-controlled. Existing/non-empty
    # directories are rejected to prevent overwriting rollback material.
    if backup_dir.exists() and (
        not backup_dir.is_dir() or any(backup_dir.iterdir())
    ):
        raise SystemExit(f"error: target backup path is not empty: {backup_dir}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    live_identity = probe_live(
        manifest, assets, loader, backup_dir / "logs"
    )
    require_same_device(full_state, live_identity)
    slot = get_active_slot(loader, backup_dir / "logs" / "get-active-slot.log")
    if slot != "b":
        raise SystemExit(
            f"error: {release} requires slot B to be active before any release "
            "write; this installer does not modify GPT slot metadata"
        )
    print("OK  active slot is B")

    files = []
    for asset in assets:
        destination = backup_dir / target_backup_name(asset)
        print(f">> Backing up {asset['target']} to {destination}")
        run_edl(
            [
                "rs",
                str(asset["raw_lba"]),
                str(asset["sectors"]),
                str(destination),
                "--skipresponse",
            ],
            loader,
            backup_dir / "logs" / f"backup-{asset['target']}.log",
        )
        if destination.stat().st_size != asset["size"]:
            raise SystemExit(
                f"error: backup of {asset['target']} has unexpected size"
            )
        files.append(
            {
                "target": asset["target"],
                "name": destination.name,
                "raw_lba": asset["raw_lba"],
                "sectors": asset["sectors"],
                "size": destination.stat().st_size,
                "sha256": sha256_file(destination),
            }
        )

    receipt = {
        "schema": 1,
        "release": manifest["release"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "full_backup_sha256": full_state["sha256"],
        "device_identity": full_state["device_identity"],
        "gpt_geometry_sha256": full_state["gpt_geometry_sha256"],
        "live_primary_gpt_sha256": live_identity["primary_gpt_sha256"],
        "active_slot": slot,
        "files": files,
    }
    (backup_dir / "backup-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"OK  target backups and receipt: {backup_dir}")
    return backup_dir


def verify_target_backup(
    backup_dir: Path,
    manifest: dict[str, Any],
    assets: list[dict[str, Any]],
    full_backup_state: dict[str, Any],
) -> dict[str, Any]:
    receipt = load_json(backup_dir / "backup-receipt.json")
    if receipt.get("schema") != 1 or receipt.get("release") != manifest["release"]:
        raise SystemExit("error: target backup receipt is for another release")
    if receipt.get("full_backup_sha256") != full_backup_state["sha256"]:
        raise SystemExit("error: target backups reference a different full backup")
    if receipt.get("device_identity") != full_backup_state["device_identity"]:
        raise SystemExit("error: target backups reference a different phone")
    if (
        receipt.get("gpt_geometry_sha256")
        != full_backup_state["gpt_geometry_sha256"]
    ):
        raise SystemExit("error: target backups reference a different GPT")
    if receipt.get("active_slot") != "b":
        raise SystemExit("error: target backups were not captured on active slot B")
    live_gpt_digest = require_hex_digest(
        receipt.get("live_primary_gpt_sha256"),
        "target backup live_primary_gpt_sha256",
    )
    entries = receipt.get("files")
    if not isinstance(entries, list) or len(entries) != len(assets):
        raise SystemExit("error: incomplete target backup receipt")
    by_target = {
        item.get("target"): item for item in entries if isinstance(item, dict)
    }
    result: dict[str, Path] = {}
    digests: dict[str, str] = {}
    for asset in assets:
        entry = by_target.get(asset["target"])
        expected_name = target_backup_name(asset)
        if (
            not isinstance(entry, dict)
            or entry.get("name") != expected_name
            or entry.get("raw_lba") != asset["raw_lba"]
            or entry.get("sectors") != asset["sectors"]
            or entry.get("size") != asset["size"]
        ):
            raise SystemExit(
                f"error: invalid target backup receipt for {asset['target']}"
            )
        digest = require_hex_digest(
            entry.get("sha256"), f"backup {asset['target']}.sha256"
        )
        path = (backup_dir / expected_name).resolve()
        if path.parent != backup_dir.resolve() or not path.is_file():
            raise SystemExit(f"error: missing target backup {expected_name}")
        if path.stat().st_size != asset["size"] or sha256_file(path) != digest:
            raise SystemExit(f"error: target backup mismatch for {asset['target']}")
        result[asset["target"]] = path
        digests[asset["target"]] = digest
    print(f"OK  verified rollback set: {backup_dir}")
    return {
        "paths": result,
        "digests": digests,
        "live_primary_gpt_sha256": live_gpt_digest,
    }


def confirm_exact(prompt: str, phrase: str) -> None:
    print()
    print(prompt)
    answer = input(f"Type exactly '{phrase}' to continue: ")
    if answer != phrase:
        raise SystemExit("aborted: confirmation did not match")


def write_flash_receipt(
    path: Path,
    release: str,
    completed: list[dict[str, Any]],
    total: int,
    *,
    in_progress: str | None = None,
) -> None:
    receipt: dict[str, Any] = {
        "schema": 1,
        "release": release,
        "complete": len(completed) == total and in_progress is None,
        "verified": completed,
    }
    if in_progress is not None:
        receipt["in_progress"] = in_progress
    install.write_json(path, receipt)


def get_active_slot(loader: Path, log_path: Path) -> str:
    output = run_edl(
        ["getactiveslot", "--skipresponse"],
        loader,
        log_path,
        capture=True,
    )
    matches = re.findall(r"(?i)(?:active\s*slot|slot)[^ab]*\b([ab])\b", output)
    if not matches:
        raise SystemExit(
            f"error: could not parse active slot; inspect {log_path} and "
            "do not change slots manually without confirming the result"
        )
    unique = {item.lower() for item in matches}
    if len(unique) != 1:
        raise SystemExit(f"error: contradictory active-slot output in {log_path}")
    return unique.pop()


def flash(
    manifest: dict[str, Any],
    assets: list[dict[str, Any]],
    asset_paths: dict[str, Path],
    loader: Path,
    full_backup: Path,
    target_backup: Path,
) -> None:
    release = manifest["release"]
    full_state = verify_full_backup(full_backup, manifest, assets)
    target_state = verify_target_backup(
        target_backup.resolve(), manifest, assets, full_state
    )
    flash_dir = target_backup / f"flash-{release}"
    if flash_dir.exists() and not flash_dir.is_dir():
        raise SystemExit(f"error: flash path is not a directory: {flash_dir}")
    preflight_logs = target_backup / f"preflight-{release}"
    live_identity = probe_live(manifest, assets, loader, preflight_logs)
    require_same_device(full_state, live_identity)
    if (
        live_identity["primary_gpt_sha256"]
        != target_state["live_primary_gpt_sha256"]
    ):
        raise SystemExit(
            "error: live primary GPT bytes changed since target backups"
        )
    slot = get_active_slot(loader, preflight_logs / "get-active-slot.log")
    if slot != "b":
        raise SystemExit(
            f"error: {release} requires slot B to be active before writing; "
            "no range was modified"
        )
    print("OK  active slot is B")
    flash_dir.mkdir(exist_ok=True)
    receipt_path = flash_dir / "flash-receipt.json"
    completed: list[dict[str, Any]] = []
    in_progress: str | None = None
    if receipt_path.exists():
        receipt = load_json(receipt_path)
        entries = receipt.get("verified")
        if (
            receipt.get("schema") != 1
            or receipt.get("release") != release
            or not isinstance(entries, list)
            or len(entries) > len(assets)
        ):
            raise SystemExit("error: invalid partial flash receipt")
        raw_in_progress = receipt.get("in_progress")
        if raw_in_progress is not None:
            if (
                not isinstance(raw_in_progress, str)
                or len(entries) >= len(assets)
                or raw_in_progress != assets[len(entries)]["target"]
            ):
                raise SystemExit("error: invalid in-progress flash receipt")
            in_progress = raw_in_progress
        for index, entry in enumerate(entries):
            asset = assets[index]
            if (
                not isinstance(entry, dict)
                or entry.get("target") != asset["target"]
                or entry.get("raw_lba") != asset["raw_lba"]
                or entry.get("sectors") != asset["sectors"]
                or entry.get("sha256") != asset["sha256"]
            ):
                raise SystemExit("error: partial flash receipt is not a valid prefix")
            readback = flash_dir / f"{asset['target']}-resume-check.img"
            if readback.exists():
                if not readback.is_file():
                    raise SystemExit(f"error: unsafe read-back path: {readback}")
                readback.unlink()
            print(f">> Rechecking previously verified {asset['target']}")
            run_edl(
                [
                    "rs",
                    str(asset["raw_lba"]),
                    str(asset["sectors"]),
                    str(readback),
                    "--skipresponse",
                ],
                loader,
                flash_dir / "logs" / f"resume-{asset['target']}.log",
            )
            if (
                not readback.is_file()
                or readback.stat().st_size != asset["size"]
                or sha256_file(readback) != asset["sha256"]
            ):
                raise SystemExit(
                    f"error: {asset['target']} changed after its prior read-back; "
                    "DO NOT REBOOT. Restore it from the target backup."
                )
            completed.append(entry)
        print(f"OK  resumed after {len(completed)} verified range(s)")

    for asset in assets[len(completed):]:
        target = asset["target"]
        current = flash_dir / f"{target}-before-write-check.img"
        if current.exists():
            if not current.is_file():
                raise SystemExit(f"error: unsafe pre-write check path: {current}")
            current.unlink()
        print(f">> Confirming live {target} still matches its rollback backup")
        run_edl(
            [
                "rs",
                str(asset["raw_lba"]),
                str(asset["sectors"]),
                str(current),
                "--skipresponse",
            ],
            loader,
            flash_dir / "logs" / f"pre-write-{target}.log",
        )
        if not current.is_file() or current.stat().st_size != asset["size"]:
            raise SystemExit(
                f"error: live pre-write read failed for {target}; no range was written"
            )
        backup_path = target_state["paths"][target]
        backup_digest = target_state["digests"][target]
        if sha256_file(backup_path) != backup_digest:
            raise SystemExit(f"error: rollback image changed: {backup_path}")
        current_digest = sha256_file(current)
        if target == in_progress and current_digest == asset["sha256"]:
            completed.append(
                {
                    "target": target,
                    "raw_lba": asset["raw_lba"],
                    "sectors": asset["sectors"],
                    "sha256": current_digest,
                    "verified_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
            write_flash_receipt(
                receipt_path, release, completed, len(assets)
            )
            in_progress = None
            print(f"VERIFIED  {target}  {current_digest} (recovered receipt)")
            continue
        if (
            target == in_progress
            and current_digest not in (backup_digest, asset["sha256"])
        ):
            confirm_exact(
                f"The interrupted write to {target} is partial. Restore its "
                "verified rollback image before continuing.",
                f"RESTORE {target}",
            )
            if sha256_file(backup_path) != backup_digest:
                raise SystemExit(f"error: rollback image changed: {backup_path}")
            run_edl(
                ["ws", str(asset["raw_lba"]), str(backup_path)],
                loader,
                flash_dir / "logs" / f"restore-{target}.log",
            )
            restored = flash_dir / f"{target}-restore-check.img"
            if restored.exists():
                if not restored.is_file():
                    raise SystemExit(f"error: unsafe restore check path: {restored}")
                restored.unlink()
            run_edl(
                [
                    "rs",
                    str(asset["raw_lba"]),
                    str(asset["sectors"]),
                    str(restored),
                    "--skipresponse",
                ],
                loader,
                flash_dir / "logs" / f"verify-restore-{target}.log",
            )
            if (
                not restored.is_file()
                or restored.stat().st_size != asset["size"]
                or sha256_file(restored) != backup_digest
            ):
                raise SystemExit(
                    f"error: rollback read-back mismatch for {target}; DO NOT REBOOT"
                )
            current_digest = backup_digest
            write_flash_receipt(
                receipt_path, release, completed, len(assets)
            )
            in_progress = None
            print(f"RESTORED  {target}  {backup_digest}")
        if (
            current_digest != backup_digest
        ):
            raise SystemExit(
                f"error: live {target} no longer matches its rollback backup; "
                "no further range was written"
            )

    remaining = assets[len(completed):]
    if remaining:
        confirm_exact(
            f"This will overwrite {len(remaining)} raw slot-B range(s) on "
            "the connected phone.",
            f"FLASH T440W {release}",
        )

    for asset in remaining:
        source = asset_paths[asset["name"]]
        target = asset["target"]
        if (
            source.stat().st_size != asset["size"]
            or sha256_file(source) != asset["sha256"]
        ):
            raise SystemExit(
                f"error: release asset changed before write: {source.name}"
            )
        write_flash_receipt(
            receipt_path,
            release,
            completed,
            len(assets),
            in_progress=target,
        )
        print(f">> Writing {source.name} to raw LBA {asset['raw_lba']}")
        run_edl(
            ["ws", str(asset["raw_lba"]), str(source)],
            loader,
            flash_dir / "logs" / f"write-{target}.log",
        )
        readback = flash_dir / f"{target}-after.img"
        if readback.exists():
            if not readback.is_file():
                raise SystemExit(f"error: unsafe read-back path: {readback}")
            readback.unlink()
        print(f">> Reading the complete {target} range back")
        run_edl(
            [
                "rs",
                str(asset["raw_lba"]),
                str(asset["sectors"]),
                str(readback),
                "--skipresponse",
            ],
            loader,
            flash_dir / "logs" / f"verify-{target}.log",
        )
        actual_size = readback.stat().st_size if readback.is_file() else -1
        actual_digest = sha256_file(readback) if readback.is_file() else ""
        if (
            not readback.is_file()
            or actual_size != asset["size"]
            or actual_digest != asset["sha256"]
        ):
            raise SystemExit(
                f"error: {target} read-back mismatch; DO NOT REBOOT. "
                f"Restore {target_backup / target_backup_name(asset)} to "
                f"LBA {asset['raw_lba']} and verify it."
            )
        completed.append(
            {
                "target": target,
                "raw_lba": asset["raw_lba"],
                "sectors": asset["sectors"],
                "sha256": actual_digest,
                "verified_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        write_flash_receipt(
            receipt_path,
            release,
            completed,
            len(assets),
        )
        print(f"VERIFIED  {target}  {actual_digest}")

    print("OK  every release range was written and read back exactly")
    final_slot = get_active_slot(
        loader, flash_dir / "logs" / "verify-active-slot.log"
    )
    if final_slot != "b":
        raise SystemExit("error: active slot changed unexpectedly; do not reboot")
    print("OK  slot B remained active")
    print("Hold Power for roughly 10 seconds until the phone vibrates/reboots.")
    print("Then run tooling/scripts/verify-post-boot.sh.")


def guided_session_path(release: str) -> Path:
    return REPO_ROOT / "artifacts/install" / release / "session.json"


def load_guided_session(release: str) -> dict[str, Any]:
    path = guided_session_path(release)
    if not path.exists():
        return {"schema": 1, "release": release}
    session = load_json(path)
    if session.get("schema") != 1 or session.get("release") != release:
        raise SystemExit(f"error: invalid guided install session: {path}")
    return session


def save_guided_session(session: dict[str, Any]) -> None:
    install.write_json(guided_session_path(session["release"]), session)


def backup_is_protected(session: dict[str, Any], digest: str) -> bool:
    return (
        session.get("backup_protected") is True
        and session.get("protected_backup_sha256") == digest
    )


def repo_artifact_path(value: Any, label: str) -> Path:
    if not isinstance(value, str):
        raise SystemExit(f"error: invalid {label} in guided session")
    raw = Path(value)
    path = (raw if raw.is_absolute() else REPO_ROOT / raw).resolve()
    artifacts = (REPO_ROOT / "artifacts").resolve()
    try:
        path.relative_to(artifacts)
    except ValueError as exc:
        raise SystemExit(f"error: {label} escapes artifacts/: {path}") from exc
    return path


def wait_for_edl() -> None:
    checker = REPO_ROOT / "tooling/scripts/check-device.sh"
    while True:
        print()
        print("Put the T440W in EDL mode, then press Enter.")
        input()
        status = subprocess.run([str(checker)], cwd=REPO_ROOT, check=False)
        if status.returncode == 0:
            return
        answer = input("EDL was not detected. Retry? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes"):
            continue
        raise SystemExit("aborted: no EDL device detected")


def guided_install(
    manifest: dict[str, Any],
    assets: list[dict[str, Any]],
    loader: Path,
) -> None:
    release = manifest["release"]
    session = load_guided_session(release)
    print(f"T440W Android installer ({release}, latest supported release)")
    print("This supports only the exact T440W hardware and slot-B layout.")

    _, asset_paths = ensure_release_assets(manifest, assets)
    session["assets_verified"] = True
    save_guided_session(session)

    wait_for_edl()
    probe_dir = REPO_ROOT / "evidence/logs" / f"install-{release}-probe"
    probe_live(manifest, assets, loader, probe_dir)
    slot = get_active_slot(loader, probe_dir / "get-active-slot.log")
    if slot != "b":
        raise SystemExit(
            f"error: {release} requires active slot B; no write was performed"
        )
    print("OK  active slot is B")

    if "full_backup" in session:
        full_backup = repo_artifact_path(session["full_backup"], "full backup")
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        full_backup = (
            REPO_ROOT / "artifacts/backups" / f"t440w-full-emmc-{stamp}.img"
        )
        session["full_backup"] = str(full_backup.relative_to(REPO_ROOT))
        save_guided_session(session)

    receipt = backup_receipt_path(full_backup)
    if not full_backup.exists() and not receipt.exists():
        subprocess.run(
            [str(REPO_ROOT / "tooling/scripts/backup.sh"), str(full_backup)],
            cwd=REPO_ROOT,
            check=True,
        )
    elif not full_backup.is_file() or not receipt.is_file():
        raise SystemExit(
            "error: the prior full backup is incomplete. Preserve it for "
            f"diagnosis, remove the session at {guided_session_path(release)}, "
            "and restart with a fresh output path."
        )

    backup_receipt = load_json(receipt)
    backup_digest = require_hex_digest(
        backup_receipt.get("sha256"), "full backup receipt sha256"
    )
    if not backup_is_protected(session, backup_digest):
        confirm_exact(
            "Copy the full backup and its receipt to protected storage outside "
            "this repository before continuing.",
            "BACKUP SAFE",
        )
        session["backup_protected"] = True
        session["protected_backup_sha256"] = backup_digest
        save_guided_session(session)

    if "target_backup" in session:
        target_backup = repo_artifact_path(
            session["target_backup"], "target backup"
        )
        if not (target_backup / "backup-receipt.json").is_file():
            raise SystemExit(
                f"error: incomplete target backup in session: {target_backup}"
            )
    else:
        target_backup = backup_targets(
            manifest, assets, loader, full_backup, None
        )
        session["target_backup"] = str(target_backup.relative_to(REPO_ROOT))
        save_guided_session(session)

    flash(
        manifest,
        assets,
        asset_paths,
        loader,
        full_backup,
        target_backup,
    )
    session["flash_complete"] = True
    save_guided_session(session)

    answer = input(
        "After Android has booted and ADB is connected, run post-boot checks? "
        "[y/N] "
    ).strip().lower()
    if answer in ("y", "yes"):
        subprocess.run(
            [str(REPO_ROOT / "tooling/scripts/verify-post-boot.sh")],
            cwd=REPO_ROOT,
            check=True,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_dir", type=Path, nargs="?")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--guided",
        action="store_true",
        help="download and safely install the latest supported release",
    )
    actions.add_argument(
        "--probe-edl",
        action="store_true",
        help="read and verify live EDL identity/GPT; perform no writes",
    )
    actions.add_argument(
        "--backup-targets",
        action="store_true",
        help="read all target ranges into a fresh rollback directory",
    )
    actions.add_argument(
        "--flash",
        action="store_true",
        help="write and read back the release after interactive confirmation",
    )
    parser.add_argument("--full-backup", type=Path)
    parser.add_argument(
        "--target-backup",
        type=Path,
        help="existing backup receipt for --flash, or output for --backup-targets",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest, assets = install.load_release()
    loader = verify_loader(manifest)
    if args.guided:
        if args.release_dir is not None:
            raise SystemExit("error: --guided does not accept release_dir")
        guided_install(manifest, assets, loader)
        return 0
    if args.release_dir is None:
        raise SystemExit("error: release_dir is required unless using --guided")
    asset_paths = verify_assets(args.release_dir.resolve(), assets)

    if args.probe_edl:
        release = manifest["release"]
        probe_logs = REPO_ROOT / "evidence/logs" / f"install-{release}-probe"
        probe_live(
            manifest,
            assets,
            loader,
            probe_logs,
        )
        slot = get_active_slot(loader, probe_logs / "get-active-slot.log")
        if slot != "b":
            raise SystemExit(
                f"error: {release} requires active slot B; no write was performed"
            )
        print("OK  active slot is B")
    elif args.backup_targets:
        if args.full_backup is None:
            raise SystemExit("error: --backup-targets requires --full-backup")
        backup_targets(
            manifest,
            assets,
            loader,
            args.full_backup.resolve(),
            args.target_backup.resolve() if args.target_backup else None,
        )
    elif args.flash:
        if args.full_backup is None or args.target_backup is None:
            raise SystemExit(
                "error: --flash requires --full-backup and --target-backup"
            )
        flash(
            manifest,
            assets,
            asset_paths,
            loader,
            args.full_backup.resolve(),
            args.target_backup.resolve(),
        )
    else:
        print_plan(manifest, assets)
    return 0


if __name__ == "__main__":
    sys.exit(main())
