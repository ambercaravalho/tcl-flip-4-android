#!/usr/bin/env bash
# Reversibly install and enable the T440W keypad cursor prototype.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/artifacts/build/keypad-cursor}"
APK="$OUT/keypad-cursor.apk"
STATE="$OUT/install-state"
PACKAGE="org.tclflip4.keypadcursor"
COMPONENT="$PACKAGE/$PACKAGE.KeypadCursorService"

if [[ ! -r "$APK" ]]; then
    echo "error: missing APK: $APK" >&2
    exit 1
fi
if [[ -e "$STATE" ]]; then
    echo "error: rollback state already exists: $STATE" >&2
    exit 1
fi

adb wait-for-device
if [[ "$(adb shell id -u | tr -d '\r')" != "0" ]]; then
    echo "error: root adbd is required for secure-settings changes" >&2
    exit 1
fi
if adb shell pm path "$PACKAGE" 2>/dev/null | grep -q '^package:'; then
    echo "error: $PACKAGE is already installed; refusing to overwrite it" >&2
    exit 1
fi

mkdir -p "$STATE"
adb shell settings get secure accessibility_enabled |
    tr -d '\r' >"$STATE/accessibility_enabled.txt"
adb shell settings get secure enabled_accessibility_services |
    tr -d '\r' >"$STATE/enabled_accessibility_services.txt"
adb shell settings get global policy_control |
    tr -d '\r' >"$STATE/policy_control.txt"
adb shell getprop qemu.hw.mainkeys |
    tr -d '\r' >"$STATE/qemu_hw_mainkeys.txt"
adb shell getprop persist.sys.phh.mainkeys |
    tr -d '\r' >"$STATE/persist_sys_phh_mainkeys.txt"

adb install "$APK"

enabled="$(cat "$STATE/enabled_accessibility_services.txt")"
if [[ -z "$enabled" || "$enabled" == "null" ]]; then
    merged="$COMPONENT"
elif [[ ":$enabled:" == *":$COMPONENT:"* ]]; then
    merged="$enabled"
else
    merged="$enabled:$COMPONENT"
fi

adb shell settings put secure enabled_accessibility_services "$merged"
adb shell settings put secure accessibility_enabled 1
adb shell setprop persist.sys.phh.mainkeys 1
adb shell setprop qemu.hw.mainkeys 1

adb shell settings get secure accessibility_enabled
adb shell settings get secure enabled_accessibility_services
adb shell getprop persist.sys.phh.mainkeys
adb shell getprop qemu.hw.mainkeys
adb shell setprop ctl.restart zygote

echo "Framework restart requested; verify the service and navigation bar after Android returns."
