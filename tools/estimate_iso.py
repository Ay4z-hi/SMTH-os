#!/usr/bin/env python3
"""Estimate the ISO payload from the real Debian Trixie package index.

Why this exists: the 450 MiB ISO budget could not be judged from the package
lists alone. `wine` is a metapackage, so the list looks small while its closure
(libwine alone) is 725 MiB installed. This tool resolves the full dependency
closure of the core lists from the published Debian index, reports the largest
packages, and compares an estimated squashfs-compressed image size against the
budget.

The compressed estimate uses `--ratio` (default 2.8x, measured range for
zstd-compressed Debian desktops is roughly 2.5x-3.0x). It is an estimate, not a
replacement for `tools/check_budgets.py`, which measures the real ISO.

Usage:
  python3 tools/estimate_iso.py [--arch amd64|arm64] [--ratio 2.8] [--check-names] [--enforce]
"""
import argparse
import lzma
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUDGET_MIB = 450
COMPONENTS = ("main", "contrib", "non-free-firmware")
# Installed boot files that are not part of any package closure.
BOOT_OVERHEAD_MIB = 6
CACHE = pathlib.Path("/tmp/smth-debian-index")


def fetch(component: str, arch: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{component}-{arch}.xz"
    if not path.exists():
        url = f"http://deb.debian.org/debian/dists/trixie/{component}/binary-{arch}/Packages.xz"
        print(f"  downloading {url}", file=sys.stderr)
        with urllib.request.urlopen(url, timeout=120) as response:
            path.write_bytes(response.read())
    return path


def load_index(arch: str):
    index = {}
    for component in COMPONENTS:
        path = fetch(component, arch)
        text = lzma.open(path, "rt", errors="replace").read()
        for stanza in text.split("\n\n"):
            name = re.search(r"^Package: (\S+)", stanza, re.M)
            if not name:
                continue
            size = re.search(r"^Installed-Size: (\d+)", stanza, re.M)
            deps = [re.search(r"^Depends: (.+)$", stanza, re.M),
                    re.search(r"^Pre-Depends: (.+)$", stanza, re.M)]
            joined = ",".join(m.group(1) for m in deps if m)
            index[name.group(1)] = {
                "size": int(size.group(1)) if size else 0,
                "deps": joined,
                "component": component,
            }
    return index


def lists_for(arch: str):
    core = []
    for path in sorted((ROOT / "config/package-lists").glob("*.list.chroot")):
        core += [line.strip() for line in path.read_text().splitlines()
                 if line.strip() and not line.startswith("#")]
    core += [line.strip() for line in (ROOT / f"arch/{arch}.list").read_text().splitlines()
             if line.strip() and not line.startswith("#")]
    extensions = {}
    for path in sorted((ROOT / "extensions").glob("*/packages.txt")):
        packages = []
        for line in path.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            name, _, only_arch = line.partition("@")
            if only_arch.strip() and only_arch.strip() != arch:
                continue
            packages.append(name.strip())
        extensions[path.parent.name] = packages
    return core, extensions


def closure(packages, index):
    seen, missing, stack = set(), set(), list(packages)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        entry = index.get(name)
        if entry is None:
            missing.add(name)
            continue
        seen.add(name)
        for group in entry["deps"].split(","):
            group = group.strip()
            if not group:
                continue
            alternatives = [re.split(r"[ (:]", alt.strip())[0] for alt in group.split("|")]
            real = next((alt for alt in alternatives if alt in index), None)
            if real:
                stack.append(real)
            else:
                missing.add(alternatives[0])
    total_kib = sum(index[name]["size"] for name in seen)
    return seen, missing, total_kib


def report(label, packages, index):
    seen, missing, kib = closure(packages, index)
    mib = kib / 1024
    print(f"\n{label}: {len(seen)} packages, {mib:.1f} MiB installed")
    for name, entry in sorted(((n, index[n]) for n in seen), key=lambda item: -item[1]["size"])[:10]:
        print(f"  {entry['size'] / 1024:7.1f} MiB  {name}")
    if missing:
        print(f"  unresolved virtual/unknown names: {', '.join(sorted(missing))}")
    return mib, missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", default="amd64", choices=("amd64", "arm64"))
    parser.add_argument("--ratio", type=float, default=2.8,
                        help="assumed squashfs compression ratio (installed/compressed)")
    parser.add_argument("--check-names", action="store_true",
                        help="fail when a listed package does not exist in Debian Trixie")
    parser.add_argument("--enforce", action="store_true",
                        help="fail when the estimated core ISO exceeds the budget")
    args = parser.parse_args()

    print(f"Debian Trixie index for {args.arch}")
    index = load_index(args.arch)
    core, extensions = lists_for(args.arch)

    unknown = sorted({p for p in core if p not in index})
    if unknown:
        print(f"\nUNKNOWN core package names: {', '.join(unknown)}")
        if args.check_names:
            return 1

    core_mib, missing = report(f"core lists ({args.arch})", core, index)
    estimated = core_mib / args.ratio + BOOT_OVERHEAD_MIB
    print(f"  estimated ISO: {core_mib:.0f} MiB / {args.ratio:.1f} + {BOOT_OVERHEAD_MIB} MiB boot"
          f" = ~{estimated:.0f} MiB (budget {BUDGET_MIB} MiB)")

    for name, packages in extensions.items():
        ext_mib, _ = report(f"extension '{name}' (not in the core ISO)", packages, index)
        if missing and name == "hypervisor":
            pass
        del ext_mib

    if args.enforce and estimated > BUDGET_MIB:
        print(f"\nFAIL: estimated core ISO ~{estimated:.0f} MiB exceeds the {BUDGET_MIB} MiB budget.")
        print("Move the largest offenders into signed extensions instead of raising the budget.")
        return 1
    if estimated > BUDGET_MIB:
        print(f"\nWARNING: estimated core ISO ~{estimated:.0f} MiB is over budget.")
        return 0
    print("\nOK: estimated core ISO is within budget.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
