#!/usr/bin/env bash
# Build the test-only application-UID Magisk authorization probe.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/tooling/root-probe"
OUT="${1:-$ROOT/artifacts/build/root-probe}"
SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}"
BUILD_TOOLS="$SDK_ROOT/build-tools/${ANDROID_BUILD_TOOLS_VERSION:-36.0.0}"
ANDROID_JAR="$SDK_ROOT/platforms/android-36/android.jar"
CLASSES="$OUT/classes"
DEX="$OUT/dex"
UNSIGNED="$OUT/root-probe-unsigned.apk"
ALIGNED="$OUT/root-probe-aligned.apk"
SIGNED="$OUT/root-probe.apk"
KEY="$OUT/test-key.pk8"

rm -rf "$OUT"
mkdir -p "$CLASSES" "$DEX"
javac \
    -source 8 \
    -target 8 \
    -Xlint:all \
    -bootclasspath "$ANDROID_JAR" \
    -d "$CLASSES" \
    "$APP/src/org/tclflip4/rootprobe/RootProbeActivity.java"
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
    "$CLASSES"/org/tclflip4/rootprobe/*.class
TZ=UTC touch -t 198001010000 "$DEX/classes.dex"
zip -X -q -j "$UNSIGNED" "$DEX/classes.dex"
"$BUILD_TOOLS/zipalign" -f 4 "$UNSIGNED" "$ALIGNED"
openssl pkcs8 \
    -topk8 \
    -nocrypt \
    -in "$ROOT/tooling/tools/avb/testkeys/testkey_rsa2048.pem" \
    -outform DER \
    -out "$KEY"
"$BUILD_TOOLS/apksigner" sign \
    --key "$KEY" \
    --cert "$ROOT/tooling/keypad-cursor/test-cert.pem" \
    --v1-signing-enabled false \
    --v2-signing-enabled false \
    --v3-signing-enabled true \
    --v4-signing-enabled false \
    --out "$SIGNED" \
    "$ALIGNED"
"$BUILD_TOOLS/apksigner" verify --verbose "$SIGNED"
shasum -a 256 "$SIGNED"
