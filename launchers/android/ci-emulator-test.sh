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
note "boot completed: $(adb shell getprop sys.boot_completed 2>&1 | tr -d '\r')"

adb logcat -c || true

if ! step "install" adb install -r "$APK"; then
  fail "adb install failed" "$LAST_OUT"
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
note "SMTH launcher install check passed"
