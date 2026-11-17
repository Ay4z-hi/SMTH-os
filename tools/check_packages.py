#!/usr/bin/env python3
"""Verify every package name against the published Debian Trixie indexes.

This is the authoritative package check for the image and its extensions. It
reads the real `Packages.xz` indexes for the target architecture from
`deb.debian.org` (main, contrib and non-free-firmware) instead of querying the
host's apt cache. A build container's apt sources are frequently main-only, so
an apt-cache lookup reports valid `non-free-firmware` packages (such as the
firmware extension's blobs) as MISSING even though the image's own
`--archive-areas "main contrib non-free-firmware"` can install them.

The check is deliberately fail-closed: a name that is not present in the
published index is reported and the script exits non-zero.

Usage:
  python3 tools/check_packages.py [amd64|arm64]
"""
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from estimate_iso import lists_for, load_index  # noqa: E402


def detect_arch() -> str:
    try:
        return subprocess.run(["dpkg", "--print-architecture"], capture_output=True,
                              text=True, check=True).stdout.strip() or "amd64"
    except (OSError, subprocess.CalledProcessError):
        return "amd64"


def main() -> int:
    arch = sys.argv[1] if len(sys.argv) > 1 else detect_arch()
    if arch not in ("amd64", "arm64"):
        print(f"unsupported architecture: {arch}", file=sys.stderr)
        return 2
    print(f"verifying package names against Debian Trixie indexes ({arch})")
    index = load_index(arch)
    core, extensions = lists_for(arch)

    missing = []
    for name in sorted(set(core)):
        if name not in index:
            missing.append(f"core: {name}")
    for extension, packages in sorted(extensions.items()):
        for name in sorted(set(packages)):
            if name not in index:
                missing.append(f"extension '{extension}': {name}")

    if missing:
        for item in missing:
            print(f"MISSING: {item}")
        print(f"FAIL: {len(missing)} package name(s) are not in the Debian Trixie "
              f"index for {arch}")
        return 1

    total = len(set(core)) + sum(len(set(p)) for p in extensions.values())
    print(f"package check ok ({arch}): {total} names verified across core and "
          f"{len(extensions)} extension(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
