#!/usr/bin/env bash
# Guarded single-partition EDL write, with pre-flash backup and read-back verify.
#
# Before writing, this ALWAYS dumps the current contents of the target partition
# to artifacts/backups/pre-flash/ so you can restore it, asks for explicit confirmation,
# writes, then reads the partition back and compares sha256 to the image so you
# know the write actually committed BEFORE you reboot. See
# docs/runbooks/flash-and-verify.md and docs/PATCHES.md.
#
# Usage: tooling/scripts/flash-partition.sh <partition> <image>
#   e.g. tooling/scripts/flash-partition.sh vbmeta_b artifacts/build/vbmeta_b-patched.img
#
# IMPORTANT (this loader): WRITES must run WITHOUT --skipresponse (the <program>
# handshake must complete for the write to commit); READS use --skipresponse.
# A write with --skipresponse prints success but silently does not persist.
#
# WRITE operation. Can brick the phone. Have a full backup (tooling/scripts/backup.sh).
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$DIR"

if [[ $# -ne 2 ]]; then
  echo "usage: tooling/scripts/flash-partition.sh <partition> <image>" >&2
  exit 2
fi

PART="$1"
IMG="$2"
LOADER="tooling/loader/flip-4-edl.bin"

if [[ ! -f "$IMG" ]]; then
  echo "error: image '$IMG' not found" >&2
  exit 1
fi

mkdir -p artifacts/backups/pre-flash evidence/logs

echo ">> Target partition : $PART"
echo ">> Image to write   : $IMG ($(wc -c < "$IMG") bytes)"
echo

echo ">> Backing up current $PART to artifacts/backups/pre-flash/$PART.img ..."
tooling/scripts/edl r "$PART" "artifacts/backups/pre-flash/$PART.img" \
  --loader="$LOADER" --memory=emmc --skipresponse | tee "evidence/logs/preflash-$PART.log"

echo
read -r -p "Write $IMG to $PART now? Type 'yes' to proceed: " ans
if [[ "$ans" != "yes" ]]; then
  echo "Aborted. No write performed."
  exit 0
fi

# NOTE: no --skipresponse on the write, or it won't commit on this loader.
echo ">> Writing $IMG -> $PART ..."
tooling/scripts/edl w "$PART" "$IMG" \
  --loader="$LOADER" --memory=emmc | tee "evidence/logs/flash-$PART.log"

echo ">> Reading $PART back to verify ..."
tooling/scripts/edl r "$PART" "artifacts/backups/pre-flash/$PART-after.img" \
  --loader="$LOADER" --memory=emmc --skipresponse | tee "evidence/logs/verify-$PART.log"

want="$(shasum -a256 "$IMG" | awk '{print $1}')"
# The partition may be larger than the image; compare only the leading bytes.
got="$(dd if="artifacts/backups/pre-flash/$PART-after.img" bs=1 count="$(wc -c < "$IMG")" 2>/dev/null | shasum -a256 | awk '{print $1}')"

echo
if [[ "$want" == "$got" ]]; then
  echo "VERIFIED: $PART now matches $IMG ($want)."
  echo "Safe to reboot (battery pull, boot normally)."
else
  echo "!! MISMATCH: $PART did NOT commit correctly."
  echo "   want=$want"
  echo "   got =$got"
  echo "   Do NOT reboot. Re-check the tooling/loader/flags (writes need NO --skipresponse)"
  echo "   or restore: tooling/scripts/flash-partition.sh $PART artifacts/backups/pre-flash/$PART.img"
  exit 1
fi
