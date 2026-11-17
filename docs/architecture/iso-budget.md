# ISO size budget: measurement and the optional-extension split

Status: **both architectures build an ISO and pass the size gate.** The final
measured images are **861.0 MiB (amd64)** and **627.7 MiB (arm64)**, down from
1117 MiB and 1209 MiB. The budget policy is: **450 MiB preferred target, 900 MiB
maximum acceptable size**. The gate warns above 450 MiB and fails only above
900 MiB, so an image no longer fails automatically merely for exceeding 450 MiB.
450 MiB was not raised silently; the preferred target is kept and the maximum
acceptable size is documented.

The first post-policy builds failed the gate because live-build's
`--firmware-chroot` default (true) installs the whole non-free-firmware archive
(~1.2 GiB installed) regardless of `--apt-recommends false`. `auto/config` now
passes `--firmware-chroot false`, and the base lists explicitly install only
common Wi-Fi/Bluetooth/storage firmware; the rest is in `extensions/firmware`.
The baseline table near the end records the pre-split sizes.

## Final measured (run 44141628362, commit f2124e1)

| | amd64 | arm64 |
|---|---:|---:|
| Installed chroot | **2019 MiB** | ~1900 MiB |
| ISO written | **861.0 MiB** (902,823,936 B) | **627.7 MiB** (658,206,720 B) |
| `lb build` | exit 0 | exit 0 |
| Size gate | PASS | PASS |
| effective compression | ~2.34x (zstd 22, 1 MiB blocks) | ~3.0x |

Run 44131721760 first reached these sizes; run 44141628362 reproduced them and
also passed the firmware-extension job.

Intermediate runs show where the savings came from: 908.0 MiB (zstd 15),
903.0 MiB (zstd 19), unchanged at zstd 22, then 861.0 MiB with 1 MiB blocks.
The larger block saved 42 MiB on amd64 and 39.6 MiB on arm64 while keeping
zstd's fast decompression.

The firmware split did its job: the amd64 chroot fell from 2410 to 2019 MiB and
the full-archive firmware packages disappeared from the top list. amd64 was
only 3 MiB over after zstd 19 because the remaining common firmware is large
(`firmware-iwlwifi` 111 MiB, `firmware-atheros` 95 MiB, `firmware-amd-graphics`
90 MiB, `firmware-nvidia-graphics` 63 MiB). Rather than drop a driver, the build
now uses zstd level 22 with 1 MiB squashfs blocks.

### Firmware extension verification

CI job `Firmware extension (test-signed)` builds the real `extensions/firmware`
payload from Trixie with an ephemeral RSA key, then loads `smthctl` and checks the
signature, manifest id/arch, payload SHA-256, and the exact `.smx` member list.
It also lists the squashfs payload and requires `/lib/firmware` entries. The job
passes on run 44141628362 (commit f2124e1).

Two firmware packages are deliberately not shipped: `firmware-ipw2x00` and
`firmware-ivtv`. Their `preinst` scripts require interactive acceptance of the
Intel PRO/Wireless and Hauppauge licences, so debootstrap cannot install them
unattended. Both are legacy hardware; the omission is recorded in
`extensions/firmware/packages.txt`. `tools/check_packages.py` now verifies 123
names for amd64 and 119 for arm64.

Still unverified: installing and mounting the built `.smx` into a running SMTH
system. The build and signature verification are covered; the live mount path is
not.

## Baseline measured on real builds (GitHub Actions run 43951424994)

| | amd64 | arm64 |
|---|---:|---:|
| Installed chroot | **2410 MiB** | **2927 MiB** |
| ISO written | **1116.7 MiB** | **1209.1 MiB** |
| `lb build` | exit 0 | exit 0 |
| Size gate | FAIL (>450 MiB) | FAIL (>450 MiB) |
| effective compression | ~2.16x (zstd) | ~2.42x |

Largest installed packages (amd64): firmware-netronome 140.6 MiB, libllvm19
123.7 MiB, firmware-iwlwifi 111.4 MiB, linux-image-6.12.117+deb13-amd64
106.3 MiB, firmware-atheros 95.0 MiB, firmware-amd-graphics 89.8 MiB,
firmware-nvidia-graphics 63.1 MiB, firmware-nvidia-tesla-535-gsp 59.4 MiB,
firmware-marvell-prestera 59.0 MiB, firmware-mediatek 45.2 MiB, mesa-libgallium
40.6 MiB, firmware-sof-signed 34.2 MiB. `chroot/usr/lib` alone is 1599 MiB.

arm64 is heavier still: firmware-qcom-soc is 298 MiB and the kernel 170 MiB.

**At least ~780 MiB of the payload is non-free firmware** installed by
live-build's `--firmware-chroot true` default, i.e. more than the entire ISO
budget on its own before any desktop is added. The rest is a full GTK/GNOME-class
stack under `/usr/lib`.

### Why the earlier estimate was wrong

The estimator resolved `Depends` only and assumed 2.8x compression. The real
image installs 2410 MiB where the model counted 1013 MiB, and compresses at
~2.16x, so it predicted ~368 MiB for an image that came out at 1117 MiB. The
tool now models the install more honestly, but it remains an estimate: only
`tools/check_budgets.py` on a real ISO decides.

### What closing the gap requires (needs a decision)

1. **Firmware split** (implemented): `--firmware-chroot false` stops the automatic
   full-archive install. The base lists keep `firmware-linux-free`, Intel/Atheros/
   MediaTek/Realtek/Broadcom Wi-Fi and Bluetooth, and (amd64 only) AMD/NVIDIA/Intel
   graphics plus Intel/SOF audio. Every other firmware package is in the signed
   `extensions/firmware`, so common laptops keep working out of the box and rare
   hardware is one extension install away.
2. **LLVM/llvmpipe reduction** (~60 MiB): drop `libllvm19` by not shipping the
   software rasteriser path.
3. **The remaining ~400 MiB is the application stack.** Reaching 450 MiB means
   replacing the GTK/GNOME-class apps with lighter equivalents, or moving most of
   them into extensions — a product decision, not a build tweak.

Options that are explicitly *not* being taken unilaterally: raising the budget,
or silently deleting capabilities.

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

`python3 tools/estimate_iso.py --arch amd64` — 607 packages, **1523 MiB
installed**; at the measured 2.2x zstd ratio plus 6 MiB boot files: **~698 MiB**.
arm64 (kernel is larger, x86-only GPU/audio firmware excluded): **~633 MiB**.
The model still misses roughly 500 MiB of packages that live-build itself adds,
so the real amd64 chroot is 2019 MiB and the ISO 861 MiB. Measure the ISO; the
estimate only validates the direction of a change.

Caveats, stated explicitly:

* 2.2x is measured on the current image, but the package closure still omits
  live-build's own additions. A real ISO must be measured: the estimate
  validates the *decision*, it does not replace `check_budgets.py`.
* The closure models `Depends` only, matching `--apt-recommends false`, but it
  does not model live-build's own package injection. Firmware injection is now
  disabled with `--firmware-chroot false` and replaced by explicit base lists.
* initramfs contents depend on the hook; `BOOT_OVERHEAD_MIB = 6` in the tool is a
  placeholder for kernel + initrd + grub/isolinux assets.

## How to keep it honest

1. `tools/check_packages.py` verifies every core and extension package name
   against the published Debian Trixie `Packages.xz` indexes (main, contrib,
   non-free-firmware) for the target architecture. It replaced the host
   `apt-cache` check, which reported valid non-free-firmware packages as
   missing when a build container's apt sources were main-only.
2. `tools/estimate_iso.py --check-names` independently fails if a listed
   package does not exist; CI runs the check on every change (see
   `.github/workflows/ci.yml`).
3. `tools/check_budgets.py` now warns above the 450 MiB preferred target and fails
   the real ISO build only above the 900 MiB maximum acceptable size.
4. If a feature genuinely cannot fit even in the acceptable range, it belongs in
   a signed extension — never as a silently removed capability.
