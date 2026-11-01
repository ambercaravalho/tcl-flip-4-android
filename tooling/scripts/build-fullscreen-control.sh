#!/usr/bin/env bash
# Build the minimal full-screen Android client used by the T440W trace control.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/tooling/fullscreen-control"
OUT="${1:-$ROOT/artifacts/build/fullscreen-control}"
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
UNSIGNED="$OUT/fullscreen-control-unsigned.apk"
ALIGNED="$OUT/fullscreen-control-aligned.apk"
SIGNED="$OUT/fullscreen-control.apk"
KEY_SOURCE="$OUT/debug-key-source.pem"
KEY="$OUT/debug-key.pk8"
CERT="$OUT/debug-cert.pem"

rm -rf "$CLASSES" "$DEX"
rm -f "$UNSIGNED" "$ALIGNED" "$SIGNED"
mkdir -p "$CLASSES" "$DEX"

# SECURITY-REVIEW: Invokes fixed local Android/JDK build tools on repository-owned sources.
javac \
    -source 8 \
    -target 8 \
    -Xlint:all \
    -bootclasspath "$ANDROID_JAR" \
    -d "$CLASSES" \
    "$APP/src/org/tclflip4/fullscreencontrol/MainActivity.java"

"$BUILD_TOOLS/aapt2" link \
    -I "$ANDROID_JAR" \
    --manifest "$APP/AndroidManifest.xml" \
    --min-sdk-version 34 \
    --target-sdk-version 34 \
    --version-code 1 \
    --version-name 1.0 \
    -o "$UNSIGNED"

"$BUILD_TOOLS/d8" \
    --lib "$ANDROID_JAR" \
    --min-api 34 \
    --output "$DEX" \
    "$CLASSES"/org/tclflip4/fullscreencontrol/*.class

zip -q -j "$UNSIGNED" "$DEX/classes.dex"
"$BUILD_TOOLS/zipalign" -f 4 "$UNSIGNED" "$ALIGNED"

if [[ ! -r "$KEY" || ! -r "$CERT" ]]; then
    # SECURITY-REVIEW: Generates an unencrypted, local-only APK test key under ignored build output.
    rm -f "$KEY_SOURCE" "$KEY" "$CERT" "$OUT/debug-key.pem"
    openssl req \
        -x509 \
        -newkey rsa:2048 \
        -keyout "$KEY_SOURCE" \
        -out "$CERT" \
        -sha256 \
        -days 3650 \
        -nodes \
        -subj "/CN=T440W Fullscreen Control/"
    openssl pkcs8 \
        -topk8 \
        -nocrypt \
        -in "$KEY_SOURCE" \
        -outform DER \
        -out "$KEY"
    rm -f "$KEY_SOURCE"
fi

"$BUILD_TOOLS/apksigner" sign \
    --key "$KEY" \
    --cert "$CERT" \
    --out "$SIGNED" \
    "$ALIGNED"
"$BUILD_TOOLS/apksigner" verify --verbose --print-certs "$SIGNED"

shasum -a 256 "$SIGNED"
