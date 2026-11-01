#!/usr/bin/env bash
# Patch an exact T440W init_boot image on the connected device with pinned Magisk.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPONENTS="${RELEASE_COMPONENT_DIR:-$ROOT/artifacts/downloads/release-components}"
MAGISK_APK="$COMPONENTS/Magisk-v31.1.apk"
AVBTOOL="$ROOT/tooling/tools/avb/avbtool.py"
PATCH_VBMETA="$ROOT/tooling/scripts/patch_vbmeta.py"
VBMETA_KEY="$ROOT/tooling/tools/avb/testkeys/testkey_rsa4096.pem"
SOURCE=""
EXPECTED=""
VBMETA=""
EXPECTED_VBMETA=""
OUT_DIR="$ROOT/artifacts/build/rooted-release/magisk"
DEVICE_WORK="/data/local/tmp/t440w-magisk-patch"

usage() {
    echo "usage: $0 --source init_boot.img --expect-sha256 HASH --vbmeta vbmeta.img --expect-vbmeta-sha256 HASH [--out-dir DIR]" >&2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)
            SOURCE="$2"
            shift 2
            ;;
        --expect-sha256)
            EXPECTED="$2"
            shift 2
            ;;
        --vbmeta)
            VBMETA="$2"
            shift 2
            ;;
        --expect-vbmeta-sha256)
            EXPECTED_VBMETA="$2"
            shift 2
            ;;
        --out-dir)
            OUT_DIR="$2"
            shift 2
            ;;
        *)
            usage
            exit 2
            ;;
    esac
done

if [[ -z "$SOURCE" || -z "$EXPECTED" || -z "$VBMETA" || -z "$EXPECTED_VBMETA" ]]; then
    usage
    exit 2
fi
for path in "$SOURCE" "$VBMETA" "$MAGISK_APK"; do
    if [[ ! -r "$path" ]]; then
        echo "error: missing input: $path" >&2
        exit 1
    fi
done
ACTUAL="$(shasum -a 256 "$SOURCE" | awk '{print $1}')"
if [[ "$ACTUAL" != "$EXPECTED" ]]; then
    echo "error: init_boot hash $ACTUAL != expected $EXPECTED" >&2
    exit 1
fi
ACTUAL_VBMETA="$(shasum -a 256 "$VBMETA" | awk '{print $1}')"
if [[ "$ACTUAL_VBMETA" != "$EXPECTED_VBMETA" ]]; then
    echo "error: vbmeta hash $ACTUAL_VBMETA != expected $EXPECTED_VBMETA" >&2
    exit 1
fi
if [[ "$(stat -f %z "$VBMETA")" != "65536" ]]; then
    echo "error: vbmeta input is not exactly 64 KiB" >&2
    exit 1
fi
if [[ "$(stat -f %z "$SOURCE")" != "8388608" ]]; then
    echo "error: init_boot input is not exactly 8 MiB" >&2
    exit 1
fi

adb wait-for-device
if [[ "$(adb shell id -u | tr -d '\r')" != "0" ]]; then
    echo "error: root adbd is required for same-device image patching" >&2
    exit 1
fi
if [[ "$(adb shell getprop ro.product.cpu.abi | tr -d '\r')" != "armeabi-v7a" ]]; then
    echo "error: connected device is not the expected 32-bit ARM userspace" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
HOST_WORK="$OUT_DIR/host-payload"
rm -rf "$HOST_WORK"
mkdir -p "$HOST_WORK"
python3 - "$MAGISK_APK" "$HOST_WORK" <<'PY'
import pathlib
import sys
import zipfile

apk, destination = sys.argv[1:]
destination = pathlib.Path(destination)
mapping = {
    "assets/boot_patch.sh": "boot_patch.sh",
    "assets/util_functions.sh": "util_functions.sh",
    "lib/armeabi-v7a/libmagisk.so": "magisk",
    "lib/armeabi-v7a/libmagiskboot.so": "magiskboot",
    "lib/armeabi-v7a/libmagiskinit.so": "magiskinit",
    "lib/armeabi-v7a/libinit-ld.so": "init-ld",
}
with zipfile.ZipFile(apk) as source:
    for archive_path, output_name in mapping.items():
        (destination / output_name).write_bytes(source.read(archive_path))
PY
cp "$SOURCE" "$HOST_WORK/init_boot.img"
chmod 755 "$HOST_WORK"/*

adb shell rm -rf "$DEVICE_WORK"
adb shell mkdir -p "$DEVICE_WORK"
adb push "$HOST_WORK/." "$DEVICE_WORK/" >/dev/null
adb shell "cd '$DEVICE_WORK' \
    && chmod 755 * \
    && KEEPVERITY=true KEEPFORCEENCRYPT=true PATCHVBMETAFLAG=false \
       RECOVERYMODE=false LEGACYSAR=false \
       sh ./boot_patch.sh ./init_boot.img"
adb pull "$DEVICE_WORK/new-boot.img" "$OUT_DIR/init_boot_b-magisk.img" >/dev/null
adb shell rm -rf "$DEVICE_WORK"

OUTPUT="$OUT_DIR/init_boot_b-magisk.img"
# Magisk preserves the stock embedded AVB descriptor while changing the raw
# image length. Recreate that unsigned footer so its image size and digest
# describe the patched payload before updating the signed top-level vbmeta.
python3 "$AVBTOOL" erase_footer --image "$OUTPUT"
python3 "$AVBTOOL" add_hash_footer \
    --image "$OUTPUT" \
    --partition_name init_boot \
    --partition_size 8388608 \
    --hash_algorithm sha256 \
    --salt c4869a83799cbc08e59d64d737969b5a9f6096936378e46d4a1c31c29581a440 \
    --prop com.android.build.init_boot.os_version:14 \
    --prop 'com.android.build.init_boot.fingerprint:TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys' \
    --prop com.android.build.init_boot.security_patch:2024-11-05
ln -sf "$(basename "$OUTPUT")" "$OUT_DIR/init_boot.img"
python3 "$AVBTOOL" verify_image --image "$OUT_DIR/init_boot.img"
rm "$OUT_DIR/init_boot.img"

if [[ "$(stat -f %z "$OUTPUT")" != "8388608" ]]; then
    echo "error: patched init_boot is not exactly 8 MiB" >&2
    exit 1
fi
if cmp -s "$SOURCE" "$OUTPUT"; then
    echo "error: Magisk output is byte-identical to the source" >&2
    exit 1
fi

VBMETA_OUTPUT="$OUT_DIR/vbmeta_b-magisk.img"
python3 "$PATCH_VBMETA" \
    "$VBMETA" init_boot auto "$VBMETA_KEY" "$VBMETA_OUTPUT" \
    "--from-image=$OUTPUT"
python3 - "$ROOT" "$VBMETA" "$VBMETA_OUTPUT" "$VBMETA_KEY" <<'PY'
import pathlib
import struct
import sys

root, before_path, after_path, key = sys.argv[1:]
sys.path.insert(0, str(pathlib.Path(root) / "tooling" / "scripts"))
from prepare_gsi import verify_vbmeta_signature

def descriptors(path):
    data = pathlib.Path(path).read_bytes()
    auth_size = struct.unpack_from(">Q", data, 12)[0]
    aux_size = struct.unpack_from(">Q", data, 20)[0]
    desc_off = struct.unpack_from(">Q", data, 96)[0]
    desc_size = struct.unpack_from(">Q", data, 104)[0]
    aux = data[256 + auth_size:256 + auth_size + aux_size]
    result = []
    pos = desc_off
    while pos < desc_off + desc_size:
        _, following = struct.unpack_from(">QQ", aux, pos)
        result.append(aux[pos:pos + 16 + following])
        pos += 16 + following
    return result

before = descriptors(before_path)
after = descriptors(after_path)
changed = [index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]
if len(before) != len(after) or len(changed) != 1:
    raise SystemExit(f"error: expected exactly one changed descriptor, got {changed}")
verify_vbmeta_signature(after_path, key)
print(f"changed top-level vbmeta descriptor index: {changed[0]}")
PY

cat >"$OUT_DIR/build-manifest.json" <<EOF
{
  "magisk_apk_sha256": "$(shasum -a 256 "$MAGISK_APK" | awk '{print $1}')",
  "output": {
    "init_boot_b_sha256": "$(shasum -a 256 "$OUTPUT" | awk '{print $1}')",
    "vbmeta_b_sha256": "$(shasum -a 256 "$VBMETA_OUTPUT" | awk '{print $1}')"
  },
  "source": {
    "init_boot_b_sha256": "$ACTUAL",
    "vbmeta_b_sha256": "$ACTUAL_VBMETA"
  }
}
EOF
shasum -a 256 "$OUTPUT" "$VBMETA_OUTPUT"
