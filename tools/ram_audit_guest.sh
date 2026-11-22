#!/usr/bin/env bash
# In-guest driver for the live RAM audit.  Installed as
# /usr/local/bin/smth-ramaudit and started by smth-ramaudit.service, which only
# runs when the kernel command line contains smth.ramaudit=1.
#
# It waits for the real desktop, then takes whole-machine snapshots at the
# phases the audit asks for and prints each one to the serial console between
# SMTH_AUDIT: BEGIN <phase> / SMTH_AUDIT: END markers.  Nothing is changed in
# the running session: apps are launched the way the taskbar launches them.
set -u

SNAP=/usr/local/lib/smth/ram_audit_snapshot.py
OUT=/run/smth-audit

say() {
    echo "SMTH_AUDIT: $*"
}

grep -q 'smth.ramaudit=1' /proc/cmdline 2>/dev/null || { say "skip (smth.ramaudit not set)"; exit 0; }
[ -f "$SNAP" ] || { say "FAIL missing $SNAP"; exit 1; }

mkdir -p "$OUT"
touch "$OUT/phase.log"

# The compositor session is started from the tty1 autologin, so the unit races
# with it; wait for the same processes smth-bootcheck waits for.
ready=0
for _ in $(seq 1 120); do
    pgrep -x labwc >/dev/null 2>&1 && pgrep -x waybar >/dev/null 2>&1 \
        && pgrep -x smthd >/dev/null 2>&1 && { ready=1; break; }
    sleep 2
done
if [ "$ready" -ne 1 ]; then
    say "FAIL session timeout labwc=$(pgrep -x labwc >/dev/null && echo yes || echo no) waybar=$(pgrep -x waybar >/dev/null && echo yes || echo no) smthd=$(pgrep -x smthd >/dev/null && echo yes || echo no)"
    exit 1
fi

# Copy the session's own environment instead of guessing it: dbus-run-session
# hands labwc a private bus address.
LPID=$(pgrep -x labwc | head -n1)
for var in XDG_RUNTIME_DIR WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS XDG_SESSION_TYPE; do
    value=$(tr '\0' '\n' < "/proc/$LPID/environ" 2>/dev/null | sed -n "s/^$var=//p" | head -n1)
    [ -n "$value" ] && export "$var=$value"
done
SUSER=$(stat -c %U "/proc/$LPID" 2>/dev/null || echo smth)
say "session user=$SUSER wayland=${WAYLAND_DISPLAY:-?} runtime=${XDG_RUNTIME_DIR:-?}"

snap() {
    phase=$1
    python3 "$SNAP" --phase "$phase" > "$OUT/$phase.json" 2>"$OUT/$phase.err" || {
        say "FAIL snapshot $phase: $(tail -n2 "$OUT/$phase.err" | tr '\n' ' ')"
    }
    say "BEGIN $phase"
    cat "$OUT/$phase.json"
    say "END $phase"
    echo "$(date +%s) $phase" >> "$OUT/phase.log"
}

launch() {
    app=$1
    # Launch exactly what the .desktop entry runs, as the session user, with
    # the session's environment, detached from this unit.
    setpriv --reuid="$SUSER" --regid="$SUSER" --init-groups \
        env HOME=/home/"$SUSER" XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
        WAYLAND_DISPLAY="$WAYLAND_DISPLAY" DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
        XDG_CURRENT_DESKTOP=SMTH XDG_SESSION_TYPE=wayland \
        setsid "$app" >/dev/null 2>&1 &
    say "launched $app"
}

# 1. Immediately after the desktop is reachable.
snap boot

# 2 + 3. Idle: one minute after start-up, then two minutes after start-up.
sleep 60
snap idle_60
sleep 60
snap idle_120

# 4. Settings open.
launch smth-settings
sleep 30
snap settings

# 5. Orbit as well.
launch smth-orbit
sleep 30
snap orbit

# 6. Several ordinary applications at once.
launch alacritty
launch smth-files
launch smth-notes
launch smth-store
sleep 45
snap apps

say "DONE phases=$(wc -l < "$OUT/phase.log")"
sync
exit 0
