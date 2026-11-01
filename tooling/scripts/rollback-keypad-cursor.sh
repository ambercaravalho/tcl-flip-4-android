#!/usr/bin/env bash
# Restore the settings saved by install-keypad-cursor.sh and remove the prototype.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/artifacts/build/keypad-cursor}"
STATE="$OUT/install-state"
PACKAGE="org.tclflip4.keypadcursor"

for name in \
    accessibility_enabled \
    enabled_accessibility_services \
    policy_control \
    qemu_hw_mainkeys \
    persist_sys_phh_mainkeys
do
    if [[ ! -r "$STATE/$name.txt" ]]; then
        echo "error: missing rollback value: $STATE/$name.txt" >&2
        exit 1
    fi
done

adb wait-for-device
if [[ "$(adb shell id -u | tr -d '\r')" != "0" ]]; then
    echo "error: root adbd is required for secure-settings rollback" >&2
    exit 1
fi

restore_setting() {
    local namespace="$1"
    local key="$2"
    local value="$3"
    if [[ -z "$value" || "$value" == "null" ]]; then
        adb shell settings delete "$namespace" "$key" >/dev/null
    else
        adb shell settings put "$namespace" "$key" "$value"
    fi
}

restore_setting secure enabled_accessibility_services \
    "$(cat "$STATE/enabled_accessibility_services.txt")"
restore_setting secure accessibility_enabled \
    "$(cat "$STATE/accessibility_enabled.txt")"
restore_setting global policy_control \
    "$(cat "$STATE/policy_control.txt")"

adb uninstall "$PACKAGE"
phh_mainkeys="$(cat "$STATE/persist_sys_phh_mainkeys.txt")"
if [[ -z "$phh_mainkeys" ]]; then
    adb shell "setprop persist.sys.phh.mainkeys ''"
else
    adb shell setprop persist.sys.phh.mainkeys "$phh_mainkeys"
fi
mainkeys="$(cat "$STATE/qemu_hw_mainkeys.txt")"
if [[ -z "$mainkeys" ]]; then
    adb shell "setprop qemu.hw.mainkeys ''"
else
    adb shell setprop qemu.hw.mainkeys "$mainkeys"
fi
rm -rf "$STATE"

adb shell settings get secure accessibility_enabled
adb shell settings get secure enabled_accessibility_services
adb shell settings get global policy_control
adb shell getprop persist.sys.phh.mainkeys
adb shell getprop qemu.hw.mainkeys
adb shell setprop ctl.restart zygote
