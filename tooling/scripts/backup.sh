#!/usr/bin/env bash
# Make a full raw eMMC backup of the TCL Flip 4 and verify it.
#
# This is READ-ONLY on the device. It produces one restorable raw image.
# Requires the phone to be in EDL mode (run tooling/scripts/check-device.sh first).
#
# Usage: tooling/scripts/backup.sh [output-image]
#   default output: artifacts/backups/flip4-full-emmc.img
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$DIR"

OUT="${1:-artifacts/backups/flip4-full-emmc.img}"
LOADER="tooling/loader/flip-4-edl.bin"

if [[ -e "$OUT" || -e "$OUT.receipt.json" ]]; then
  echo "error: refusing to overwrite an existing backup or receipt: $OUT" >&2
  echo "Choose a new output path and preserve the existing files." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")" evidence/logs

echo ">> Dumping full eMMC to $OUT (this takes ~15 min at ~35 MB/s)"
# --skipresponse is REQUIRED for this loader (see docs/PATCHES.md).
tooling/scripts/edl rf "$OUT" --loader="$LOADER" --memory=emmc --skipresponse | tee "evidence/logs/backup.log"

echo
echo ">> Verifying image, GPT CRCs, device identity, and SHA-256 ..."
.venv/bin/python tooling/scripts/record-backup.py \
  "$OUT" evidence/logs/backup.log

echo
echo "Done. Keep this image somewhere safe (it contains personal data)."
echo "Keep $OUT.receipt.json with it; release installs require both files."
echo "To leave EDL mode, hold Power for ~10s until the phone vibrates/reboots."
