#!/usr/bin/env python3
"""Assemble the allowlisted T440W Android v0.1.0 GitHub release assets."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "tooling/releases/v0.1.0.json"
NOTES_PATH = REPO_ROOT / "tooling/releases/v0.1.0-notes.md"
MAX_GITHUB_ASSET_SIZE = 2 * 1024 * 1024 * 1024
METADATA_NAMES = {
    "release-manifest.json",
    "RELEASE_NOTES.md",
    "SOURCE_PROVENANCE.md",
    "t440w-android-v0.1.0-sources.tar.gz",
    "SHA256SUMS",
}
SOURCE_PATHS = (
    "LICENSE",
    "NOTICE",
    "README.md",
    "docs/README.md",
    "device/t440w",
    "docs/findings/2026-10-31-05-spi-driver-reconstruction.md",
    "docs/findings/2026-11-01-07-spi-full-height-client.md",
    "docs/findings/2026-11-01-10-rooted-release-stack.md",
    "docs/guides",
    "docs/reference/release-components.md",
    "docs/reference/spi-display-path.md",
    "docs/runbooks/backup-and-restore.md",
    "docs/runbooks/build-and-release.md",
    "docs/runbooks/flash-and-verify.md",
    "tooling/keypad-cursor",
    "tooling/patches/c9-v3.0.4-t440w.patch",
    "tooling/release-components.json",
    "tooling/releases/v0.1.0.json",
    "tooling/releases/v0.1.0-notes.md",
    "tooling/scripts/backup.sh",
    "tooling/scripts/build-c9-t440w.sh",
    "tooling/scripts/build-keypad-cursor.sh",
    "tooling/scripts/build-rooted-release.py",
    "tooling/scripts/build-spi-driver-variant.py",
    "tooling/scripts/fetch-release-components.py",
    "tooling/scripts/install-release.py",
    "tooling/scripts/install-release.sh",
    "tooling/scripts/inspect_ext4.py",
    "tooling/scripts/lp_make.py",
    "tooling/scripts/package-release.py",
    "tooling/scripts/patch-magisk-init-boot.sh",
    "tooling/scripts/patch-msm-drm-spi.py",
    "tooling/scripts/patch_vbmeta.py",
    "tooling/scripts/prepare_gsi.py",
    "tooling/scripts/record-backup.py",
    "tooling/scripts/setup.sh",
    "tooling/scripts/t440w_install_lib.py",
    "tooling/scripts/verify-post-boot.sh",
    "tooling/tests",
    "tooling/tools/avb",
    "tooling/tools/mkbootimg",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    # SECURITY-REVIEW: tracked manifests are still parsed as untrusted data and
    # validated before any source/output path is opened.
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"error: expected JSON object in {path}")
    return value


def validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema") != 1 or manifest.get("release") != "v0.1.0":
        raise SystemExit("error: unsupported release manifest")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or len(assets) != 8:
        raise SystemExit("error: v0.1.0 requires exactly eight image assets")
    names: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise SystemExit("error: invalid asset entry")
        name = asset.get("name")
        source = asset.get("source")
        size = asset.get("size")
        digest = asset.get("sha256")
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not name.endswith(".img")
            or name in names
        ):
            raise SystemExit(f"error: unsafe or duplicate asset name {name!r}")
        if (
            not isinstance(source, str)
            or Path(source).is_absolute()
            or ".." in Path(source).parts
        ):
            raise SystemExit(f"error: unsafe source path for {name}")
        if not isinstance(size, int) or size <= 0 or size >= MAX_GITHUB_ASSET_SIZE:
            raise SystemExit(f"error: unsupported GitHub asset size for {name}")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise SystemExit(f"error: invalid SHA-256 for {name}")
        if size != asset.get("sectors", 0) * 512:
            raise SystemExit(f"error: size/range mismatch for {name}")
        names.add(name)
    return assets


def resolve_source(relative: str) -> Path:
    path = (REPO_ROOT / relative).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"error: source escapes repository: {relative}") from exc
    return path


def prepare_output(
    output: Path, allowed_names: set[str], force: bool
) -> None:
    # SECURITY-REVIEW: output is user-controlled. The tool resolves it, refuses
    # filesystem root/repository root, and removes only known generated names.
    output = output.resolve()
    if output in (Path("/"), REPO_ROOT.resolve()):
        raise SystemExit(f"error: unsafe output directory: {output}")
    if output.exists() and not output.is_dir():
        raise SystemExit(f"error: output is not a directory: {output}")
    if output.exists():
        entries = {item.name for item in output.iterdir()}
        unknown = entries - allowed_names
        if unknown:
            raise SystemExit(
                "error: output contains unknown files: " + ", ".join(sorted(unknown))
            )
        if entries and not force:
            raise SystemExit("error: output is not empty; rerun with --force")
        if force:
            for item in output.iterdir():
                if item.is_dir():
                    raise SystemExit(f"error: refusing to remove directory {item}")
                item.unlink()
    output.mkdir(parents=True, exist_ok=True)


def copy_verified(source: Path, destination: Path, asset: dict[str, Any]) -> None:
    if not source.is_file():
        raise SystemExit(f"error: missing canonical asset: {source}")
    actual_size = source.stat().st_size
    actual_digest = sha256_file(source)
    if actual_size != asset["size"] or actual_digest != asset["sha256"]:
        raise SystemExit(
            f"error: canonical asset mismatch for {asset['name']}: "
            f"size={actual_size}, sha256={actual_digest}"
        )
    shutil.copyfile(source, destination)
    if (
        destination.stat().st_size != asset["size"]
        or sha256_file(destination) != asset["sha256"]
    ):
        raise SystemExit(f"error: staged copy mismatch for {asset['name']}")


def git_output(args: list[str]) -> str:
    # SECURITY-REVIEW: fixed local git commands, no shell or external input.
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def verify_git_state(allow_dirty: bool) -> str:
    commit = git_output(["rev-parse", "HEAD"])
    dirty = git_output(["status", "--porcelain"])
    if dirty and not allow_dirty:
        raise SystemExit(
            "error: source archive requires a clean working tree; commit the "
            "release sources first (or use --allow-dirty for local testing)"
        )
    return commit


def sanitized_manifest(
    manifest: dict[str, Any], source_commit: str
) -> dict[str, Any]:
    assets = []
    for source in manifest["assets"]:
        assets.append(
            {
                key: source[key]
                for key in (
                    "name",
                    "sha256",
                    "size",
                    "raw_lba",
                    "sectors",
                    "target",
                    "kind",
                )
            }
        )
    return {
        "schema": manifest["schema"],
        "release": manifest["release"],
        "device": manifest["device"],
        "loader_sha256": manifest["loader"]["sha256"],
        "source_commit": source_commit,
        "assets": assets,
    }


def make_provenance(source_commit: str) -> str:
    components = read_json(REPO_ROOT / "tooling/release-components.json")
    rows = []
    for component in components.get("components", []):
        if not isinstance(component, dict):
            raise SystemExit("error: invalid component manifest")
        rows.append(
            f"- **{component['id']} {component['version']}** — "
            f"`{component['license']}`; source {component['source']} at "
            f"`{component['source_commit']}`; distributed binary SHA-256 "
            f"`{component['sha256']}`."
        )
    integration = components.get("integration_configs", {}).get("microg", {})
    rows.append(
        "- **microG integration configuration** — "
        f"`{integration['license']}`; source {integration['source']} at "
        f"`{integration['source_commit']}`."
    )
    return """# T440W Android v0.1.0 source provenance

The tagged repository at commit `{source_commit}` is the source for the T440W integration, release
builders, keypad service, C9 patch, EDL wrapper changes, and binary display
patch description. The release source archive contains the relevant tracked
files with normalized metadata.

## Embedded components

{rows}

## Display module source gap

`vendor_dlkm_b-full-height-client.img` contains a binary-patched
`/lib/modules/msm_drm.ko`. The stock module is SHA-256
`39f972853c5acb061a3964a48cf6bf0ff375b55dc216e537c69e76c290755065`;
the patched module is
`89febd510f7aa939ce8a20943038f0beab67d1d59a49ce48110dc229b624cf50`.
The exact matching TCL Linux 6.1 source is unavailable. TCL's available
`gflip65dish` and T440G disclosures contain unrelated 4.19/5.15 trees.

`tooling/scripts/patch-msm-drm-spi.py` records every instruction replacement,
and the reconstruction finding records the recovered behavior. Those materials
do not constitute the missing corresponding source. Redistribution of the
prebuilt GPL module therefore retains an unresolved compliance risk.

## Other notices

See `LICENSE`, `NOTICE`, and `docs/reference/release-components.md` in the
tagged repository and source archive. The proprietary signed firehose loader
is redistributed for device interoperability and is not included in the ROM
image assets.
""".format(rows="\n".join(rows), source_commit=source_commit)


def archive_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def iter_source_files() -> list[tuple[Path, str]]:
    result: list[tuple[Path, str]] = []
    for relative in SOURCE_PATHS:
        source = resolve_source(relative)
        if not source.exists():
            raise SystemExit(f"error: source-bundle path missing: {relative}")
        if source.is_file():
            result.append((source, relative))
            continue
        for child in sorted(source.rglob("*")):
            if not child.is_file():
                continue
            if "__pycache__" in child.parts or child.name == ".DS_Store":
                continue
            result.append((child, child.relative_to(REPO_ROOT).as_posix()))
    return sorted(set(result), key=lambda item: item[1])


def write_source_archive(destination: Path) -> None:
    with destination.open("wb") as raw:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw, mtime=0
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for source, relative in iter_source_files():
                    archive.add(
                        source,
                        arcname=f"t440w-android-v0.1.0/{relative}",
                        recursive=False,
                        filter=archive_filter,
                    )


def write_checksums(output: Path, names: list[str]) -> None:
    lines = [f"{sha256_file(output / name)}  {name}" for name in sorted(names)]
    (output / "SHA256SUMS").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "artifacts/releases/v0.1.0",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace only known generated files in an existing staging directory",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow a non-HEAD source archive for local testing only",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = read_json(MANIFEST_PATH)
    assets = validate_manifest(manifest)
    source_commit = verify_git_state(args.allow_dirty)
    output = args.output.resolve()
    allowed_names = {asset["name"] for asset in assets} | METADATA_NAMES
    prepare_output(output, allowed_names, args.force)

    for asset in assets:
        source = resolve_source(asset["source"])
        destination = output / asset["name"]
        print(f">> Staging {asset['name']}")
        copy_verified(source, destination, asset)

    (output / "release-manifest.json").write_text(
        json.dumps(
            sanitized_manifest(manifest, source_commit),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(NOTES_PATH, output / "RELEASE_NOTES.md")
    (output / "SOURCE_PROVENANCE.md").write_text(
        make_provenance(source_commit), encoding="utf-8"
    )
    write_source_archive(output / "t440w-android-v0.1.0-sources.tar.gz")

    checksum_names = sorted(allowed_names - {"SHA256SUMS"})
    write_checksums(output, checksum_names)
    for name in sorted(allowed_names):
        path = output / name
        if not path.is_file():
            raise SystemExit(f"error: missing staged output {name}")
        if path.stat().st_size >= MAX_GITHUB_ASSET_SIZE:
            raise SystemExit(f"error: staged asset exceeds GitHub limit: {name}")
        print(f"OK  {name}  {path.stat().st_size} bytes  {sha256_file(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
