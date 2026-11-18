#!/usr/bin/env bash
# Install and launch the launcher APK on a running Android emulator.
#
# Run by .github/workflows/launchers.yml inside android-emulator-runner, after
# the AVD has booted. Kept as a real script (not an inline YAML blob) so it can
# be syntax-checked locally, reviewed, and run by hand against any device:
#
#   adb devices && ./ci-emulator-test.sh [path/to/app-debug.apk]
set -uo pipefail

APK="${1:-$(dirname "$0")/app/build/outputs/apk/debug/app-debug.apk}"
PKG=os.smth.launcher
ACTIVITY=$PKG/.MainActivity

# GitHub only shows raw job logs to signed-in accounts, so every check reports
# through annotations and the step summary instead.
note() {
  echo "[smth-ci] $*"
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    echo "$*" >> "$GITHUB_STEP_SUMMARY"
  fi
}

fail() {
  local title="$1" detail="${2:-}"
  note "FAILED: $title"
  printf '::error title=%s::%s\n' "$title" "${detail:0:1500}"
  echo "--- adb devices ---"
  adb devices || true
  exit 1
}

step() {
  local label="$1"
  shift
  local out status
  out=$("$@" 2>&1)
  status=$?
  note "$label -> exit $status"
  printf '%s\n' "$out"
  LAST_OUT=$out
  return $status
}

command -v adb >/dev/null || fail "adb is not on PATH"
[ -s "$APK" ] || fail "APK missing" "no APK at $APK"

step "wait for device" adb wait-for-device || fail "emulator never became available"
step "android version" adb shell getprop ro.build.version.sdk || true

# `wait-for-device` only means adbd is up.  Package installation can race the
# rest of the boot and die with a truncated "Performing Streamed Install".
booted=0
for _ in $(seq 1 90); do
  if [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; then
    booted=1
    break
  fi
  sleep 2
done
note "boot completed: $booted"
[ "$booted" -eq 1 ] || fail "emulator did not finish booting" "sys.boot_completed stayed 0 for 180s"

adb logcat -c || true

if ! step "install" timeout 180 adb install -r "$APK"; then
  # The emulator runner occasionally drops the package service for a few
  # seconds after boot.  Remove any partial registration and try once more.
  adb shell pm uninstall "$PKG" >/dev/null 2>&1 || true
  sleep 5
  if ! step "install retry" timeout 180 adb install -r "$APK"; then
    fail "adb install failed" "$LAST_OUT"
  fi
fi

if ! step "installed package path" adb shell pm path "$PKG"; then
  fail "package $PKG is not installed" "$LAST_OUT"
fi

if ! step "launch" adb shell am start -W -n "$ACTIVITY"; then
  fail "am start failed" "$LAST_OUT"
fi

sleep 8

pids=$(adb shell pidof "$PKG" 2>&1 | tr -d '\r')
if [ -z "$pids" ]; then
  fail "launcher process exited" "$(adb logcat -d -t 200 2>&1 | tail -c 1400)"
fi
note "process alive: pid $pids"

adb shell dumpsys activity activities 2>&1 | grep -E 'ResumedActivity|mResumedActivity' | head -3 | while read -r line; do
  note "resumed: $line"
done

note "home activity: $(adb shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME 2>&1 | tr -d '\r' | tail -1)"

# Keep a real screenshot of the running launcher with the build so the layout
# can be reviewed without a local emulator.
shot="$(dirname "$0")/smth-launcher-emulator.png"
if adb exec-out screencap -p > "$shot" 2>/dev/null && [ -s "$shot" ]; then
  note "screenshot: $shot ($(stat -c%s "$shot") bytes)"
else
  note "screenshot: not captured"
fi
note "SMTH launcher install check passed"
