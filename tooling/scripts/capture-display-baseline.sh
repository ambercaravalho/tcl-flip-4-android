#!/usr/bin/env bash
# Capture a reproducible stock/GSI display-path baseline from a booted T440W.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$DIR"

if [[ $# -gt 1 ]]; then
  echo "usage: tooling/scripts/capture-display-baseline.sh [output-directory]" >&2
  exit 2
fi

OUT="${1:-evidence/captures/display-$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$OUT"

if ! adb get-state >/dev/null 2>&1; then
  echo "error: no authorized, booted ADB device" >&2
  exit 1
fi

adb root >/dev/null 2>&1 || true
adb wait-for-device

capture() {
  local name="$1"
  local command="$2"
  {
    echo "\$ $command"
    adb shell "$command" 2>&1 || true
  } > "$OUT/$name"
}

capture getprop.txt "getprop"
capture uname.txt "uname -a"
capture mounts.txt "cat /proc/mounts"
capture processes.txt "ps -A -o USER,PID,PPID,NAME,ARGS"
capture modules.txt "cat /proc/modules"
capture dev-graphics.txt \
  'ls -la /dev/fb* /dev/graphics /dev/dri 2>&1; for f in /sys/class/graphics/fb*/name /sys/class/graphics/fb*/stride /sys/class/graphics/fb*/virtual_size /sys/class/graphics/fb*/bits_per_pixel; do echo "### $f"; cat "$f" 2>&1; done'
capture drm-state.txt \
  'for f in /sys/kernel/debug/dri/*/state /sys/class/drm/*/status /sys/class/drm/*/modes /sys/class/drm/*/enabled /sys/class/drm/*/dpms; do [ -e "$f" ] || continue; echo "### $f"; cat "$f" 2>&1; done'
capture display-sysfs.txt \
  'for f in /sys/class/graphics/fb*/* /sys/class/drm/*/* /sys/bus/spi/devices/*/{modalias,uevent}; do [ -f "$f" ] || continue; echo "### $f"; timeout 1 cat "$f" 2>/dev/null || true; done'
capture surfaceflinger.txt "dumpsys SurfaceFlinger --display-id"
capture surfaceflinger-full.txt "dumpsys SurfaceFlinger"
capture display-service.txt "dumpsys display"
capture graphics-stats.txt "dumpsys graphicsstats"
capture composer-services.txt \
  'service list | grep -Ei "display|surface|composer|graphics|allocator"; lshal 2>&1 | grep -Ei "display|composer|allocator|mapper"'
capture b2g-process.txt \
  'for p in $(pidof b2g GonkDisplay api-daemon 2>/dev/null); do echo "### PID $p"; cat /proc/$p/cmdline; echo; cat /proc/$p/maps; done'
capture logcat.txt "logcat -b all -d -v threadtime"
capture dmesg.txt "dmesg"

adb exec-out screencap -p > "$OUT/screencap.png" 2> "$OUT/screencap.err" || true

{
  echo "captured_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "adb_serial=$(adb get-serialno)"
  echo "fingerprint=$(adb shell getprop ro.build.fingerprint | tr -d '\r')"
  echo "system_fingerprint=$(adb shell getprop ro.system.build.fingerprint | tr -d '\r')"
  echo "sdk=$(adb shell getprop ro.build.version.sdk | tr -d '\r')"
  echo "slot=$(adb shell getprop ro.boot.slot_suffix | tr -d '\r')"
} > "$OUT/manifest.txt"

echo "Static display baseline captured in $OUT"
echo "For a physical-key trace, run:"
echo "  adb shell 'timeout 10 getevent -lt' > '$OUT/one-key-getevent.txt'"
