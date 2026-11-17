#!/usr/bin/env bash
# Verify every package name in the image and extension lists exists in Debian
# Trixie for the target architecture.
#
# Validation is done against the published Debian indexes (main, contrib,
# non-free-firmware) rather than the host's apt cache. Build containers often
# configure only main, which made valid non-free-firmware packages look missing.
# See tools/check_packages.py for the authoritative check.
set -euo pipefail
cd "$(dirname "$0")/.."
ARCH="${SMTH_ARCH:-$(dpkg --print-architecture)}"
exec python3 tools/check_packages.py "$ARCH"
