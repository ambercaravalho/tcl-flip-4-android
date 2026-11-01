#!/usr/bin/env bash
# Build the hash-pinned C9 source with the minimal T440W default-key patch.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANIFEST="$ROOT/tooling/release-components.json"
PATCH="$ROOT/tooling/patches/c9-v3.0.4-t440w.patch"
OUT="${1:-$ROOT/artifacts/build/c9-t440w}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
SOURCE="$OUT/source"
GRADLE_CACHE="$OUT/gradle-cache"
APK_OUT="$OUT/c9-t440w.apk"
SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
BUILD_TOOLS_VERSION="${ANDROID_BUILD_TOOLS_VERSION:-36.0.0}"
BUILD_TOOLS="$SDK_ROOT/build-tools/$BUILD_TOOLS_VERSION"
KEY_PEM="$ROOT/tooling/tools/avb/testkeys/testkey_rsa2048.pem"
CERT="$ROOT/tooling/keypad-cursor/test-cert.pem"
KEY="$OUT/test-key.pk8"

SOURCE_URL="$(
    python3 - "$MANIFEST" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    manifest = json.load(source)
component = next(item for item in manifest["components"] if item["id"] == "c9")
print(component["source"])
PY
)"
SOURCE_COMMIT="$(
    python3 - "$MANIFEST" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    manifest = json.load(source)
component = next(item for item in manifest["components"] if item["id"] == "c9")
print(component["source_commit"])
PY
)"
EXPECTED_APK_SHA256="$(
    python3 - "$MANIFEST" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    manifest = json.load(source)
component = next(item for item in manifest["components"] if item["id"] == "c9")
print(component["t440w_build_sha256"])
PY
)"

for tool in git docker openssl python3; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "error: missing required host tool: $tool" >&2
        exit 1
    fi
done
for tool in zipalign apksigner; do
    if [[ ! -x "$BUILD_TOOLS/$tool" ]]; then
        echo "error: missing $BUILD_TOOLS/$tool" >&2
        exit 1
    fi
done
for path in "$PATCH" "$KEY_PEM" "$CERT"; do
    if [[ ! -r "$path" ]]; then
        echo "error: missing build input: $path" >&2
        exit 1
    fi
done
if [[ ! -d "$SDK_ROOT/platforms/android-36" ]]; then
    echo "error: Android SDK platform 36 is required" >&2
    exit 1
fi

rm -rf "$SOURCE"
mkdir -p "$OUT" "$GRADLE_CACHE"
git clone --filter=blob:none --no-checkout "$SOURCE_URL" "$SOURCE"
git -C "$SOURCE" checkout --detach "$SOURCE_COMMIT"
git -C "$SOURCE" apply --check "$PATCH"
git -C "$SOURCE" apply "$PATCH"

docker run --rm --platform linux/amd64 \
    -e ANDROID_HOME=/opt/android-sdk \
    -e ANDROID_SDK_ROOT=/opt/android-sdk \
    -e GRADLE_USER_HOME=/gradle-cache \
    -v "$SOURCE:/src" \
    -v "$GRADLE_CACHE:/gradle-cache" \
    -v "$SDK_ROOT:/opt/android-sdk:ro" \
    -w /src \
    eclipse-temurin:17-jdk \
    sh ./gradlew --no-daemon --console=plain assembleRelease

UNSIGNED="$SOURCE/app/build/outputs/apk/release/app-release-unsigned.apk"
NORMALIZED="$OUT/c9-t440w-normalized.apk"
ALIGNED="$OUT/c9-t440w-aligned.apk"
if [[ ! -r "$UNSIGNED" ]]; then
    echo "error: C9 build did not produce $UNSIGNED" >&2
    exit 1
fi

python3 - "$UNSIGNED" "$NORMALIZED" <<'PY'
import sys
import zipfile

source_path, output_path = sys.argv[1:]
excluded = {
    # AGP emits these optional optimization hints in nondeterministic order
    # even when classes.dex is byte-identical.
    "assets/dexopt/baseline.prof",
    "assets/dexopt/baseline.profm",
}
with zipfile.ZipFile(source_path, "r") as source:
    entries = [
        (item, source.read(item.filename))
        for item in source.infolist()
        if item.filename not in excluded
    ]
with zipfile.ZipFile(output_path, "w", allowZip64=True) as output:
    for old, data in sorted(entries, key=lambda entry: entry[0].filename):
        new = zipfile.ZipInfo(old.filename, date_time=(1980, 1, 1, 0, 0, 0))
        new.compress_type = old.compress_type
        new.external_attr = old.external_attr
        new.create_system = old.create_system
        new.flag_bits = old.flag_bits & 0x800
        output.writestr(new, data)
PY

"$BUILD_TOOLS/zipalign" -f 4 "$NORMALIZED" "$ALIGNED"
openssl pkcs8 \
    -topk8 \
    -nocrypt \
    -in "$KEY_PEM" \
    -outform DER \
    -out "$KEY"
"$BUILD_TOOLS/apksigner" sign \
    --key "$KEY" \
    --cert "$CERT" \
    --v1-signing-enabled false \
    --v2-signing-enabled false \
    --v3-signing-enabled true \
    --v4-signing-enabled false \
    --out "$APK_OUT" \
    "$ALIGNED"
"$BUILD_TOOLS/apksigner" verify --verbose --print-certs "$APK_OUT"

git -C "$SOURCE" diff --check
cp "$SOURCE/LICENSE" "$OUT/LICENSE-C9-Apache-2.0.txt"
ACTUAL_APK_SHA256="$(shasum -a 256 "$APK_OUT" | awk '{print $1}')"
if [[ "$ACTUAL_APK_SHA256" != "$EXPECTED_APK_SHA256" ]]; then
    echo "error: T440W C9 APK hash $ACTUAL_APK_SHA256 != expected $EXPECTED_APK_SHA256" >&2
    exit 1
fi
shasum -a 256 "$APK_OUT"
