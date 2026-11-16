# ISO size budget: measurement and the optional-extension split

Status: **estimated from the real Debian Trixie package index; the ISO itself was
not built in this environment** (live-build needs root + debootstrap, see
`docs/audit/2026-11-audit.md`). `tools/check_budgets.py` remains the authoritative
gate on a real ISO.

Budget: **450 MiB**, unchanged.

## Why the budget was at risk

`config/package-lists/*` looked small, but the dependency closure was enormous.
Measured with `tools/estimate_iso.py` (Debian Trixie, amd64):

| Configuration | Installed closure | Largest contributors |
|---|---:|---|
| Before (`wine` + WebKitGTK + Vulkan + KDE Connect in core) | **2233.5 MiB** | libwine 725 MiB, libllvm19 124 MiB, kernel 106 MiB, libwebkitgtk 93 MiB, mesa-vulkan-drivers 79 MiB |
| After the split below | **1050 MiB** | libllvm19 124 MiB, kernel 106 MiB, mesa-libgallium 41 MiB |

Two traps made the lists misleading:

1. `wine` is a **metapackage**. Its own `Installed-Size` is a few KiB while
   `libwine` alone is 725 MiB — roughly 250 MiB compressed, more than half the
   whole ISO.
2. The Qt/KDE stack behind `kdeconnect`, and GTK3 behind `wayvnc`, were pulled in
   for device pairing and screen mirroring.

## What moved out of the core ISO

Nothing was deleted; every moved component now ships in a signed extension:

| Component | Where it went | Reason |
|---|---|---|
| Wine / Windows binaries | `extensions/hypervisor` (`wine @amd64`) | 725 MiB installed closure |
| box64 (x86-64 on arm64) | `extensions/developer` (`box64 @arm64`) | 23 MiB, only needed for compat work |
| WebKitGTK (SMTH Browser) | `extensions/browser` (`gir1.2-webkit-6.0`) | 124 MiB installed |
| KDE Connect + WayVNC (CoreLink) | `extensions/hypervisor` | Qt + GTK3 closure |
| Vulkan drivers | `extensions/hypervisor` (`mesa-vulkan-drivers`) | 79 MiB; GL rendering does not need it |
| file-roller | removed from lists | Files extracts zip/tar itself |
| Inter + JetBrains Mono packages | removed from lists | Doto/Space Mono/DotGothic16 are bundled offline (2.8 MiB total) |

The core apps degrade honestly when an extension is absent: `smth-open` names the
extension it needs, `smth-browser` shows an install prompt instead of a blank
window, and `smth-corelink` reports the missing tool.

## Current estimate

`python3 tools/estimate_iso.py --arch amd64` — 595 packages, **1050 MiB installed**;
at the tool's default 2.8x squashfs ratio plus 6 MiB boot files: **~381 MiB**.
arm64 (kernel is larger): **~404 MiB**.

Caveats, stated explicitly:

* 2.8x is an assumption. A real ISO must be measured: the estimate validates the
  *decision*, it does not replace `check_budgets.py`.
* The closure ignores firmware pulled by `linux-image-*` recommends (recommends
  are disabled in `auto/config` with `--apt-recommends false`).
* initramfs contents depend on the hook; `BOOT_OVERHEAD_MIB = 6` in the tool is a
  placeholder for kernel + initrd + grub/isolinux assets.

## How to keep it honest

1. `tools/estimate_iso.py --check-names` fails if a listed package does not exist.
2. CI runs it on every change (see `.github/workflows/ci.yml`).
3. `tools/check_budgets.py` still fails the real ISO build above 450 MiB.
4. If a feature genuinely cannot fit, it belongs in a signed extension — never in
   a raised budget and never as a silently removed capability.
