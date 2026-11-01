#!/usr/bin/env python3
"""Shared validation helpers for the T440W release installer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
from typing import Any
import zlib


REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE = "v0.1.0"
DEFAULT_MANIFEST = REPO_ROOT / "tooling/releases/v0.1.0.json"
EXPECTED_MANIFEST_SHA256 = (
    "bcfb36e7892e649de3b7e171976f5cf47ee64616751c20b838301c5b3f87c7b3"
)
SECTOR_SIZE = 512
GPT_SIGNATURE = b"EFI PART"


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
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"error: expected a JSON object in {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def require_hex_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SystemExit(f"error: {label} must be a lowercase SHA-256")
    return value


def require_positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise SystemExit(f"error: {label} must be a positive integer")
    return value


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema") != 1 or manifest.get("release") != RELEASE:
        raise SystemExit("error: unsupported release manifest")
    device = manifest.get("device")
    loader = manifest.get("loader")
    assets = manifest.get("assets")
    if not isinstance(device, dict) or not isinstance(loader, dict):
        raise SystemExit("error: manifest device/loader object missing")
    if not isinstance(assets, list) or len(assets) != 8:
        raise SystemExit(f"error: {RELEASE} manifest must contain exactly 8 assets")
    if device.get("model") != "T440W":
        raise SystemExit("error: manifest does not target T440W")
    if device.get("hwid") != "0x002980e100420071":
        raise SystemExit("error: unexpected manifest HWID")
    if device.get("target_slot") != "b":
        raise SystemExit(f"error: {RELEASE} must target slot B")
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
        if (
            not isinstance(source, str)
            or Path(source).is_absolute()
            or ".." in Path(source).parts
        ):
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


def read_gpt(
    path: Path, *, header_lba: int = 1
) -> list[tuple[str, int, int]]:
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
    geometry = [[name, first, last - first + 1] for name, first, last in parts]
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
            raise SystemExit(f"error: GPT {target} is {actual}, expected {expected}")
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


def load_release() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if sha256_file(DEFAULT_MANIFEST) != EXPECTED_MANIFEST_SHA256:
        raise SystemExit(
            f"error: tracked {RELEASE} manifest was modified; restore the tagged file"
        )
    manifest = load_json(DEFAULT_MANIFEST)
    return manifest, validate_manifest(manifest)
