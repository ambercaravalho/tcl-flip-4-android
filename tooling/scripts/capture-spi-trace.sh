#!/usr/bin/env bash
# Trace the private T440W SPI present path with kernel kprobe events.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$DIR"

if [[ $# -gt 2 ]]; then
  echo "usage: tooling/scripts/capture-spi-trace.sh [seconds] [output-file]" >&2
  exit 2
fi

SECONDS_TO_TRACE="${1:-10}"
OUT="${2:-evidence/captures/spi-trace-$(date -u +%Y%m%dT%H%M%SZ).txt}"
mkdir -p "$(dirname "$OUT")"

if ! [[ "$SECONDS_TO_TRACE" =~ ^[1-9][0-9]*$ ]]; then
  echo "error: seconds must be a positive integer" >&2
  exit 2
fi

adb root >/dev/null 2>&1 || true
adb wait-for-device

TRACEFS="$(adb shell 'if [ -d /sys/kernel/tracing ]; then echo /sys/kernel/tracing; elif [ -d /sys/kernel/debug/tracing ]; then echo /sys/kernel/debug/tracing; fi' | tr -d '\r')"
if [[ -z "$TRACEFS" ]]; then
  echo "error: tracefs is unavailable on the device" >&2
  exit 1
fi

cleanup() {
  adb shell "echo 0 > '$TRACEFS/events/t440w/enable' 2>/dev/null || true; : > '$TRACEFS/kprobe_events' 2>/dev/null || true" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

adb shell "
  set -e
  echo 0 > '$TRACEFS/tracing_on'
  echo 0 > '$TRACEFS/events/enable'
  : > '$TRACEFS/kprobe_events'
  echo 'p:t440w/update_fb spi_display_update_fb src=%x0:x64 width=%x1:u32 height=%x2:u32 fb_width=%x3:u32 fb_height=%x4:u32 pitch=%x5:u32 fourcc=%x6:u32' >> '$TRACEFS/kprobe_events'
  echo 'p:t440w/plane_update _sde_plane_atomic_update plane=%x0:x64 state=%x1:x64' >> '$TRACEFS/kprobe_events'
  echo 'p:t440w/fence_wait sde_plane_wait_input_fence plane=%x0:x64 timeout=%x1:s64' >> '$TRACEFS/kprobe_events'
  echo 'r:t440w/fence_wait_done sde_plane_wait_input_fence ret=\$retval:s32' >> '$TRACEFS/kprobe_events'
  echo 'p:t440w/window_reset spi_panel_reset_window panel=%x0:x64 xres=+0xf0(%x0):u32 yres=+0x100(%x0):u32' >> '$TRACEFS/kprobe_events'
  echo 'p:t440w/te spi_display_te_handler' >> '$TRACEFS/kprobe_events'
  echo 'p:t440w/kickoff spi_kickoff_thread worker=%x0:x64' >> '$TRACEFS/kprobe_events'
  echo 'p:t440w/spi_start spi_sync spi=%x0:x64 message=%x1:x64' >> '$TRACEFS/kprobe_events'
  echo 'r:t440w/spi_done spi_sync ret=\$retval:s32' >> '$TRACEFS/kprobe_events'
  echo 'p:t440w/input input_event dev=%x0:x64 type=%x1:u32 code=%x2:u32 value=%x3:s32' >> '$TRACEFS/kprobe_events'
  echo mono_raw > '$TRACEFS/trace_clock'
  echo 4096 > '$TRACEFS/buffer_size_kb'
  : > '$TRACEFS/trace'
  echo 1 > '$TRACEFS/events/t440w/enable'
  echo 1 > '$TRACEFS/tracing_on'
"

echo "Tracing for ${SECONDS_TO_TRACE}s. Press one D-pad direction once now."
adb shell "timeout '$SECONDS_TO_TRACE' cat '$TRACEFS/trace_pipe'" > "$OUT" || true
adb shell "echo 0 > '$TRACEFS/tracing_on'"
{
  echo
  echo "# kprobe hit/miss profile"
  adb shell "cat '$TRACEFS/kprobe_profile'"
} >> "$OUT"

echo "SPI trace captured in $OUT"
