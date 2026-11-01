#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 || ! "$1" =~ ^(client|device)$ ]]; then
  echo "usage: tooling/scripts/set-composition-mode.sh <client|device>" >&2
  exit 2
fi

ADB="${ADB:-adb}"
MODE=0
if [[ "$1" == "client" ]]; then
  MODE=1
fi

"$ADB" wait-for-device
"$ADB" root >/dev/null
"$ADB" wait-for-device

# SDK 34 SurfaceFlinger debug transaction used during the original live
# investigation. This is deliberately a runtime diagnostic, not a persistent
# production property.
RESULT=$("$ADB" shell service call SurfaceFlinger 1008 i32 "$MODE")
if [[ "$RESULT" != *"00000000"* ]]; then
  echo "error: SurfaceFlinger rejected composition-mode transaction: $RESULT" >&2
  exit 1
fi

echo "SurfaceFlinger composition mode: $1"
"$ADB" shell dumpsys SurfaceFlinger |
  grep -aE 'uses(Device|Client)Composition|h/w composer|renderRate' || true
