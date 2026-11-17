# SMTH OS

A modular Debian Trixie live desktop for amd64 and arm64, with a Rust system core,
a Wayland shell (labwc + Waybar), GTK4/libadwaita apps, two companion launchers
(Android and Windows) and a signed extension system.

**Status: active engineering build.** Source availability is not proof of runtime
behaviour; every claim below is labelled.

## Verified / not verified

Verified by commands in this repository (see `docs/audit/2026-11-audit.md`):

* Rust core: 50 tests (`cargo test --workspace`), clippy clean, rustfmt clean.
* Palette, artwork and bundled-font contract: `python3 tools/test_palette.py`.
* Desktop wiring (every `Exec=`, autostart line, keybind, taskbar command and
  packaged script resolves): `python3 tools/check_wiring.py`.
* ISO size model against the real Debian index: `python3 tools/estimate_iso.py`.
* Android APK: `gradle assembleDebug` succeeds (JDK 17, SDK 35), and the APK
  passes `unzip -t`, DEX presence, bundled fonts, `aapt` package +
  launchable-activity identity and `apksigner verify`.
* Startup construction model: `python3 tools/test_startup.py` (timeline, logo,
  cursor independence, selection boxes, items, resolutions, Reduced Motion).
* Boot harness wiring: `tools/verify_bootloader.sh` and
  `tools/qemu_boot_test.sh` are syntax-checked and invoked by the `boot` CI
  matrix; no QEMU run was possible in this audit environment.

**Not verified here** (blocked in the audit environment, runs in CI): ISO build and
boot, Android APK install/launch (no emulator), Windows EXE build/smoke test, and
any on-screen interaction. The startup renderer has not been run on a compositor
in this environment.

## Design contract

- Palette source: `tools/palette.json` only.
  `A #D71921` (red accent), `B #8C8C8C` (grey neutral), `AHIAN_A #7C4DFF`,
  `AHIAN_B #00C2A8`.
- Black, white and grey foundation; no gradients, blur, glows, acrylic or
  translucent "liquid glass" surfaces.
- Typography bundled offline: **Doto**, **DotGothic16**, **Space Mono** (OFL) in
  `usr/share/fonts/truetype/smth/`. No network font packages.
- Dot-matrix visual language; 4 px spacing grid, 4 px control radius.
- AHIAN mode uses the purple/teal pair and its own wallpaper.
- Offline-first: no account, no telemetry.

## Repository layout

```
core/                    Rust workspace (smth-core, smthd, smth-ahian)
config/                  live-build hooks, package lists, chroot payload
  includes.chroot_after_packages/usr/local/bin      shell entry points
  includes.chroot_after_packages/usr/local/lib/smth GTK/dot libraries
extensions/*/             signed .smx definitions (packages + manifest)
launchers/android|windows companion launchers
tools/                   asset generation, palette, wiring and budget checks
docs/audit, docs/architecture                   audit, migration, budget
scripts/build.sh         ISO build (native arch)
```

## Build

Native Debian 13 (Trixie) host or the CI container, as root for live-build:

```sh
SMTH_ARCH=amd64 sudo -E ./scripts/build.sh
SMTH_ARCH=arm64 sudo -E ./scripts/build.sh
```

The build runs, in order: package-name validation, shell/Python syntax, wiring and
palette checks, `cargo fmt`/`clippy`/`test`, asset generation, release build of
`smthd`/`smth-ahian`/`smthctl-core`, live-build, the ISO size gate (preferred
450 MiB, maximum acceptable 900 MiB), and SHA-256 checksums.

## Quick checks (no root, no ISO)

```sh
cd core && cargo test --workspace
python3 tools/check_wiring.py
python3 tools/test_palette.py
python3 tools/test_startup.py
python3 tools/estimate_iso.py --arch amd64 --check-names
```

## Signed extensions

Wine, WebKitGTK, Vulkan, KDE Connect/WayVNC, box64, LibreOffice-class office apps
and developer tools ship as signed `.smx` images so the core ISO aims for the 450 MiB preferred target and must stay below the 900 MiB
maximum acceptable size (measurements and the full table:
`docs/architecture/iso-budget.md`).

Provide an RSA key pair to build artifacts:

```sh
SMTH_SIGNING_KEY=/secure/smth-release.key \
SMTH_SIGNING_PUBKEY=/secure/smth-release.pub \
SMTH_ARCH=amd64 sudo -E ./scripts/build.sh
```

Without a trusted public key at `/etc/smth/extensions.pub`, verification and
installation fail closed.

```sh
smthctl extension verify Browser-amd64.smx
sudo smthctl extension install Browser-amd64.smx
smthctl extension list
sudo smthctl extension remove browser
```

Extension package lists accept an `@arch` suffix (`wine @amd64`, `box64 @arm64`)
so one definition serves both targets.

## Startup animation

The graphical session starts the real desktop first, then `smth-startup` draws a
9.6 s layer-shell construction over it: logo, independent cursors, electric-blue
selection boxes, taskbar/widgets/windows and a fade to the live session. It is
setting-controlled, honours Reduce Motion, and is replaceable without a rebuild
(`/usr/share/smth/startup-logo.png`). See
`docs/architecture/startup-animation.md` for the timeline and test limits.

## AHIAN

Run `ahian` in a terminal: progressive errors, a dialog storm that fills the
screen over ~10 s, a blue screen reading *wants to make your life beautiful*, a
9 second countdown, then the purple/teal AHIAN desktop. `unahian` shows the angry
red screen (*looks like you dont like ahian*) and restores normal mode. The
timeline is generated by `smth_core::ahian` and covered by tests.

## Known gaps

- Guided installer, LUKS/encrypted install, A/B updates and rollback: not
  implemented yet. The boot menu's persistence entry only configures live-boot;
  do not install this image over data you care about.
- PIN/pattern lock: not implemented; `smth-lock` is `swaylock` (PAM password).
- `freezerd` is a scaffold and is not enabled in the image.
- Runtime performance budgets (RAM, boot time, launch latency) are unmeasured
  until a booted VM produces `runtime-metrics.json`.
- `smth-files` still performs mutations in-process and swallows `OSError`; moving
  it onto the Rust `fsops` backend is the next milestone.
