#!/usr/bin/env bash
# Fail fast if any package name in the lists does not exist in Debian trixie.
# Volume lists also honour the "@arch" suffix used by extensions/*/packages.txt.
set -uo pipefail
cd "$(dirname "$0")/.."
. /etc/os-release
ARCH="${SMTH_ARCH:-$(dpkg --print-architecture)}"
if [ "${ID:-}" != "debian" ]; then
  echo "skip apt package check (host is ${ID:-?}, not debian)"
else
  missing=0
  while read -r p; do
    apt-cache show --no-all-versions "$p" >/dev/null 2>&1 || { echo "MISSING: $p"; missing=1; }
  done < <(
    cat config/package-lists/*.list.chroot "arch/$ARCH.list" |
      grep -v '^#' | sed 's/#.*//' | awk 'NF{print $1}' | sort -u
    awk -v arch="$ARCH" '
      { line=$0; sub(/#.*/, "", line); gsub(/^[ \t]+|[ \t]+$/, "", line) }
      line == "" { next }
      index(line, "@") {
        split(line, parts, "@")
        if (parts[2] != arch) next
        print parts[1]
        next
      }
      { print line }
    ' extensions/*/packages.txt | sort -u
  )
  [ $missing -eq 0 ] && echo "package check ok ($ARCH)"
  exit $missing
fi
exit 0
