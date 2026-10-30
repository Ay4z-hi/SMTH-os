#!/usr/bin/env bash
# Re-evaluate layout on start and on every display hotplug (udev DRM events).
smth-mode auto
udevadm monitor --udev --subsystem-match=drm 2>/dev/null | while read -r _; do
  sleep 1; smth-mode auto
done
