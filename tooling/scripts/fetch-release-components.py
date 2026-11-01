#!/usr/bin/env python3
"""Fetch hash-pinned third-party release APKs into the ignored artifact cache."""

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.request


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO_ROOT / "tooling" / "release-components.json"
DEFAULT_OUT = REPO_ROOT / "artifacts" / "downloads" / "release-components"
REQUIRED_FIELDS = {
    "id",
    "version",
    "filename",
    "url",
    "size",
    "sha256",
    "certificate_sha256",
    "source",
    "source_commit",
    "license",
}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_component(component):
    missing = REQUIRED_FIELDS - component.keys()
    if missing:
        raise SystemExit(
            f"error: component {component.get('id', '<unknown>')} "
            f"is missing fields: {sorted(missing)}"
        )
    filename = component["filename"]
    if pathlib.PurePath(filename).name != filename:
        raise SystemExit(f"error: unsafe component filename: {filename}")
    if not component["url"].startswith("https://"):
        raise SystemExit(f"error: non-HTTPS component URL: {component['url']}")
    if len(component["sha256"]) != 64:
        raise SystemExit(f"error: invalid SHA-256 for {component['id']}")
    if not re.fullmatch(r"[0-9a-f]{64}", component["certificate_sha256"]):
        raise SystemExit(
            f"error: invalid signer certificate SHA-256 for {component['id']}"
        )
    if component["size"] <= 0:
        raise SystemExit(f"error: invalid size for {component['id']}")


def verify(path, component):
    if path.stat().st_size != component["size"]:
        return False
    return sha256_file(path) == component["sha256"]


def find_apksigner():
    found = shutil.which("apksigner")
    if found:
        return found
    sdk_root = pathlib.Path(
        os.environ.get("ANDROID_SDK_ROOT", pathlib.Path.home() / "Library/Android/sdk")
    )
    version = os.environ.get("ANDROID_BUILD_TOOLS_VERSION", "36.0.0")
    candidate = sdk_root / "build-tools" / version / "apksigner"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    raise SystemExit("error: apksigner is required to verify release components")


def signer_digest(apksigner, path):
    result = subprocess.run(
        [apksigner, "verify", "--print-certs", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(
        r"Signer #1 certificate SHA-256 digest: ([0-9a-fA-F]{64})",
        result.stdout,
    )
    if not match:
        raise SystemExit(f"error: no signer certificate digest for {path}")
    return match.group(1).lower()


def download(component, destination):
    request = urllib.request.Request(
        component["url"],
        headers={"User-Agent": "t440w-release-builder/1"},
    )
    context = ssl.create_default_context()
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.",
        suffix=".partial",
        dir=destination.parent,
        delete=False,
    ) as temporary:
        temporary_path = pathlib.Path(temporary.name)
        try:
            with urllib.request.urlopen(
                request, context=context, timeout=120
            ) as response:
                shutil.copyfileobj(response, temporary, 1024 * 1024)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
    if not verify(temporary_path, component):
        actual_size = temporary_path.stat().st_size
        actual_hash = sha256_file(temporary_path)
        temporary_path.unlink()
        raise SystemExit(
            f"error: {component['id']} verification failed: "
            f"size={actual_size}, sha256={actual_hash}"
        )
    os.replace(temporary_path, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=pathlib.Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out-dir", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--component",
        action="append",
        dest="components",
        help="Fetch only this component id; may be repeated",
    )
    args = parser.parse_args()

    with open(args.manifest, encoding="utf-8") as source:
        manifest = json.load(source)
    if manifest.get("schema") != 1:
        raise SystemExit("error: unsupported release-component manifest schema")

    components = manifest.get("components", [])
    ids = [component.get("id") for component in components]
    if len(ids) != len(set(ids)):
        raise SystemExit("error: duplicate component id")
    requested = set(args.components or ids)
    unknown = requested - set(ids)
    if unknown:
        raise SystemExit(f"error: unknown component ids: {sorted(unknown)}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    apksigner = find_apksigner()
    receipt = {"schema": 1, "components": []}
    for component in components:
        validate_component(component)
        if component["id"] not in requested:
            continue
        destination = args.out_dir / component["filename"]
        if destination.exists() and not verify(destination, component):
            raise SystemExit(
                f"error: refusing to replace mismatching cached file: {destination}"
            )
        if not destination.exists():
            print(f">> Fetching {component['id']} {component['version']}")
            download(component, destination)
        else:
            print(f">> Verified cached {component['id']} {component['version']}")
        actual_signer = signer_digest(apksigner, destination)
        if actual_signer != component["certificate_sha256"]:
            raise SystemExit(
                f"error: {component['id']} signer {actual_signer} != "
                f"expected {component['certificate_sha256']}"
            )
        receipt["components"].append(
            {
                "id": component["id"],
                "version": component["version"],
                "path": str(destination.resolve()),
                "size": destination.stat().st_size,
                "sha256": sha256_file(destination),
                "certificate_sha256": actual_signer,
                "source_commit": component["source_commit"],
                "license": component["license"],
            }
        )

    receipt_path = args.out_dir / "verified-components.json"
    with open(receipt_path, "w", encoding="utf-8") as output:
        json.dump(receipt, output, indent=2, sort_keys=True)
        output.write("\n")
    print(f">> Wrote {receipt_path}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as error:
        print(f"error: component download failed: {error}", file=sys.stderr)
        raise SystemExit(1)
