#!/usr/bin/env bash
# Build the T440W system-wide physical-keypad cursor service.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/tooling/keypad-cursor"
OUT="${1:-$ROOT/artifacts/build/keypad-cursor}"
SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
BUILD_TOOLS_VERSION="${ANDROID_BUILD_TOOLS_VERSION:-36.0.0}"
BUILD_TOOLS="$SDK_ROOT/build-tools/$BUILD_TOOLS_VERSION"
ANDROID_JAR="$SDK_ROOT/platforms/android-36/android.jar"

for tool in aapt2 d8 zipalign apksigner; do
    if [[ ! -x "$BUILD_TOOLS/$tool" ]]; then
        echo "error: missing $BUILD_TOOLS/$tool" >&2
        exit 1
    fi
done
for tool in javac openssl zip; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "error: missing required host tool: $tool" >&2
        exit 1
    fi
done
if [[ ! -r "$ANDROID_JAR" ]]; then
    echo "error: missing Android platform jar: $ANDROID_JAR" >&2
    exit 1
fi

CLASSES="$OUT/classes"
DEX="$OUT/dex"
COMPILED_RESOURCES="$OUT/resources.zip"
UNSIGNED="$OUT/keypad-cursor-unsigned.apk"
ALIGNED="$OUT/keypad-cursor-aligned.apk"
SIGNED="$OUT/keypad-cursor.apk"
KEY="$OUT/test-key.pk8"
KEY_PEM="$ROOT/tooling/tools/avb/testkeys/testkey_rsa2048.pem"
CERT="$APP/test-cert.pem"

rm -rf "$CLASSES" "$DEX"
rm -f "$COMPILED_RESOURCES" "$UNSIGNED" "$ALIGNED" "$SIGNED"
mkdir -p "$CLASSES" "$DEX"

javac \
    -source 8 \
    -target 8 \
    -Xlint:all \
    -bootclasspath "$ANDROID_JAR" \
    -d "$CLASSES" \
    "$APP/src/org/tclflip4/keypadcursor/KeypadCursorService.java"

"$BUILD_TOOLS/aapt2" compile \
    --dir "$APP/res" \
    -o "$COMPILED_RESOURCES"

"$BUILD_TOOLS/aapt2" link \
    -I "$ANDROID_JAR" \
    --manifest "$APP/AndroidManifest.xml" \
    --min-sdk-version 34 \
    --target-sdk-version 34 \
    --version-code 1 \
    --version-name 1.0 \
    "$COMPILED_RESOURCES" \
    -o "$UNSIGNED"

"$BUILD_TOOLS/d8" \
    --lib "$ANDROID_JAR" \
    --min-api 34 \
    --output "$DEX" \
    "$CLASSES"/org/tclflip4/keypadcursor/*.class

TZ=UTC touch -t 198001010000 "$DEX/classes.dex"
zip -X -q -j "$UNSIGNED" "$DEX/classes.dex"
"$BUILD_TOOLS/zipalign" -f 4 "$UNSIGNED" "$ALIGNED"

if [[ ! -r "$KEY_PEM" || ! -r "$CERT" ]]; then
    echo "error: missing keypad APK signing material" >&2
    exit 1
fi
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
    --out "$SIGNED" \
    "$ALIGNED"
"$BUILD_TOOLS/apksigner" verify --verbose --print-certs "$SIGNED"

shasum -a 256 "$SIGNED"
