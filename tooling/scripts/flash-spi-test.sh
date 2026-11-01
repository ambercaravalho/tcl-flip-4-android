#!/usr/bin/env bash
# Flash one complete, reversible T440W SPI test state and verify every byte.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$DIR"

if [[ $# -ne 1 ]]; then
  echo "usage: tooling/scripts/flash-spi-test.sh <baseline|immutable|coalesce|full-height-client|clock25|clock12>" >&2
  exit 2
fi

PROFILE="$1"
case "$PROFILE" in
  immutable|coalesce|full-height-client)
    echo "error: '$PROFILE' requires vbmeta derived from a same-session target read-back" >&2
    echo "error: prebuilt module-profile vbmeta may contain stale untargeted descriptors" >&2
    echo "follow the current finding's raw-LBA backup/write/read-back procedure" >&2
    exit 1
    ;;
esac

LOADER="tooling/loader/flip-4-edl.bin"
STOCK_DLKM="artifacts/build/vendor_dlkm_b.img"
STOCK_DTBO="artifacts/build/dtbo_b.img"
BASE_VBMETA="artifacts/build/spi-driver-tests/vbmeta_b-baseline.img"
VENDOR_LBA=6137856
VENDOR_SECTORS=105072
DTBO_LBA=3293184
DTBO_SECTORS=49152
VBMETA_LBA=3377152
VBMETA_SECTORS=128

mkdir -p artifacts/build/spi-driver-tests evidence/logs
python3 tooling/scripts/patch_vbmeta.py \
  artifacts/build/vbmeta_b.img odm auto tooling/tools/avb/testkeys/testkey_rsa4096.pem \
  "$BASE_VBMETA" --zero-fec --from-image=artifacts/build/odm_b-dbg-patched.img

case "$PROFILE" in
  baseline)
    VENDOR_IMG="$STOCK_DLKM"
    DTBO_IMG="$STOCK_DTBO"
    VBMETA_IMG="$BASE_VBMETA"
    ;;
  clock25)
    VENDOR_IMG="$STOCK_DLKM"
    DTBO_IMG="artifacts/build/dtbo_b-spi25mhz.img"
    VBMETA_IMG="artifacts/build/vbmeta_b-debug-spi25mhz.img"
    ;;
  clock12)
    VENDOR_IMG="$STOCK_DLKM"
    DTBO_IMG="artifacts/build/dtbo_b-spi12.5mhz.img"
    VBMETA_IMG="artifacts/build/vbmeta_b-debug-spi12.5mhz.img"
    ;;
  *)
    echo "error: unknown profile '$PROFILE'" >&2
    exit 2
    ;;
esac

for image in "$VENDOR_IMG" "$DTBO_IMG" "$VBMETA_IMG"; do
  if [[ ! -f "$image" ]]; then
    echo "error: missing $image" >&2
    exit 1
  fi
done

tooling/scripts/check-device.sh
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="artifacts/backups/pre-spi-test/$STAMP"
mkdir -p "$BACKUP"

echo "Backing up current vendor_dlkm_b, dtbo_b, and vbmeta_b to $BACKUP"
tooling/scripts/edl rs "$VENDOR_LBA" "$VENDOR_SECTORS" "$BACKUP/vendor_dlkm_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse > "evidence/logs/spi-$STAMP-backup-vendor-dlkm.log"
tooling/scripts/edl rs "$DTBO_LBA" "$DTBO_SECTORS" "$BACKUP/dtbo_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse > "evidence/logs/spi-$STAMP-backup-dtbo.log"
tooling/scripts/edl rs "$VBMETA_LBA" "$VBMETA_SECTORS" "$BACKUP/vbmeta_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse > "evidence/logs/spi-$STAMP-backup-vbmeta.log"
shasum -a256 "$BACKUP"/*.img

echo
echo "Profile: $PROFILE"
echo "  vendor_dlkm: $VENDOR_IMG"
echo "  dtbo       : $DTBO_IMG"
echo "  vbmeta     : $VBMETA_IMG"
read -r -p "Type '$PROFILE' to write all three images: " answer
if [[ "$answer" != "$PROFILE" ]]; then
  echo "Aborted. No write performed."
  exit 0
fi

# Data first, top-level verification metadata last. Writes never use
# --skipresponse with this loader.
tooling/scripts/edl ws "$VENDOR_LBA" "$VENDOR_IMG" \
  --loader="$LOADER" --memory=emmc > "evidence/logs/spi-$STAMP-write-vendor-dlkm.log"
tooling/scripts/edl ws "$DTBO_LBA" "$DTBO_IMG" \
  --loader="$LOADER" --memory=emmc > "evidence/logs/spi-$STAMP-write-dtbo.log"
tooling/scripts/edl ws "$VBMETA_LBA" "$VBMETA_IMG" \
  --loader="$LOADER" --memory=emmc > "evidence/logs/spi-$STAMP-write-vbmeta.log"

VERIFY="artifacts/build/spi-driver-tests/verify-$PROFILE"
tooling/scripts/edl rs "$VENDOR_LBA" "$VENDOR_SECTORS" "$VERIFY-vendor_dlkm_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse > "evidence/logs/spi-$STAMP-verify-vendor-dlkm.log"
tooling/scripts/edl rs "$DTBO_LBA" "$DTBO_SECTORS" "$VERIFY-dtbo_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse > "evidence/logs/spi-$STAMP-verify-dtbo.log"
tooling/scripts/edl rs "$VBMETA_LBA" "$VBMETA_SECTORS" "$VERIFY-vbmeta_b.img" \
  --loader="$LOADER" --memory=emmc --skipresponse > "evidence/logs/spi-$STAMP-verify-vbmeta.log"

cmp -s "$VENDOR_IMG" "$VERIFY-vendor_dlkm_b.img"
cmp -s "$DTBO_IMG" "$VERIFY-dtbo_b.img"
cmp -s "$VBMETA_IMG" "$VERIFY-vbmeta_b.img"
shasum -a256 "$VERIFY-"*.img
echo "VERIFIED: SPI profile '$PROFILE' is safe to boot."
