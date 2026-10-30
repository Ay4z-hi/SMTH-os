#!/usr/bin/env bash
# Fail fast if any package name in the lists does not exist in Debian trixie.
set -uo pipefail
cd "$(dirname "$0")/.."
. /etc/os-release
if [ "${ID:-}" != "debian" ]; then echo "skip package check (host is ${ID:-?}, not debian)"; exit 0; fi
ARCH="${SMTH_ARCH:-$(dpkg --print-architecture)}"
missing=0
for p in $(cat config/package-lists/*.list.chroot "arch/$ARCH.list" | grep -v '^#' | sort -u); do
  apt-cache show --no-all-versions "$p" >/dev/null 2>&1 || { echo "MISSING: $p"; missing=1; }
done
[ $missing -eq 0 ] && echo "package check ok ($ARCH)"
exit $missing
