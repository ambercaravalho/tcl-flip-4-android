#!/usr/bin/env bash
set -euo pipefail

command -v adb >/dev/null 2>&1 || {
  echo "error: adb is not installed" >&2
  exit 1
}

adb wait-for-device

prop() {
  adb shell getprop "$1" | tr -d '\r'
}

check() {
  local label="$1" actual="$2" expected="$3"
  if [[ "$actual" != "$expected" ]]; then
    echo "FAIL  $label: '$actual' (expected '$expected')" >&2
    return 1
  fi
  echo "OK    $label: $actual"
}

failures=0
check slot "$(prop ro.boot.slot_suffix)" "_b" || failures=$((failures + 1))
check sdk "$(prop ro.build.version.sdk)" "34" || failures=$((failures + 1))
check abi "$(prop ro.product.cpu.abi)" "armeabi-v7a" || failures=$((failures + 1))
check debuggable "$(prop ro.debuggable)" "0" || failures=$((failures + 1))
check force_debuggable "$(prop ro.force_debuggable)" "" ||
  failures=$((failures + 1))
check adb_root_prop "$(prop service.adb.root)" "0" ||
  failures=$((failures + 1))
check selinux "$(adb shell getenforce | tr -d '\r')" "Enforcing" ||
  failures=$((failures + 1))

before="$(adb shell id | tr -d '\r')"
[[ "$before" == uid=2000* ]] || {
  echo "FAIL  adb identity before adb root: $before" >&2
  failures=$((failures + 1))
}

adb root >/dev/null 2>&1 || true
adb wait-for-device
after="$(adb shell id | tr -d '\r')"
[[ "$after" == uid=2000* ]] || {
  echo "FAIL  adb identity after adb root: $after" >&2
  failures=$((failures + 1))
}
[[ "$after" == uid=2000* ]] && echo "OK    adb remains shell (uid 2000)"

su_output="$(adb shell 'su -c id >/dev/null 2>&1; echo $?' | tr -d '\r')"
[[ "$su_output" != "0" ]] || {
  echo "FAIL  shell was granted su" >&2
  failures=$((failures + 1))
}
[[ "$su_output" != "0" ]] && echo "OK    shell su denied"

fingerprint="$(prop ro.build.fingerprint)"
check fingerprint "$fingerprint" \
  "TCL/gflip5gtmo/pitti_32go:14/UKQ1.241125.001/jenkins12220921:user/test-keys" ||
  failures=$((failures + 1))

if ((failures)); then
  echo "error: $failures post-boot check(s) failed" >&2
  exit 1
fi

echo "Post-boot security checks passed. Verify the display and physical keys."
