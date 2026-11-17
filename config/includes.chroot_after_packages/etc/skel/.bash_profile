# SMTH OS live session.  live-config logs the live user in on tty1; start the
# compositor there once.  A terminal opened later is not a login shell, so this
# cannot recurse or start a second session.
if [ -z "${WAYLAND_DISPLAY:-}" ] && [ -z "${DISPLAY:-}" ] && [ "$(tty 2>/dev/null)" = "/dev/tty1" ]; then
    exec /usr/local/bin/smth-session
fi
