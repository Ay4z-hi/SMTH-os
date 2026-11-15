# SMTH OS

A modular Debian Trixie-based desktop OS for amd64 and arm64. The current repository contains a live-build system, a Wayland desktop shell, GTK4/libadwaita apps, palette-driven dot artwork, and an early signed extension framework.

## Current status

This is an active engineering build, not a finished daily-driver OS. Source availability does not mean runtime verification. See:
- docs/architecture/roadmap-status.md
- docs/architecture/acceptance-tests.md
- docs/architecture/extensions.md

## Design contract

- Palette source: tools/palette.json only.
- Black #000000, A #FF7A00, B #2F6BFF, white foreground.
- No gradients, blur, glows, shadows, acrylic, or translucent surfaces.
- Inter + JetBrains Mono bundled offline.
- 4px spacing grid; 4px control radius; 8px window/flyout radius.
- Reduce Motion is available in Settings and AHIAN reads the same preference.
- Offline-first; no account requirement or telemetry.

## Build

Build on a native Debian 13 (Trixie) host or matching container:

    SMTH_ARCH=amd64 sudo -E ./scripts/build.sh
    SMTH_ARCH=arm64 sudo -E ./scripts/build.sh

The build validates package names, Python syntax, generated artwork pixels, and the 450 MiB ISO size budget. Runtime RAM/boot/latency budgets remain unmeasured until a booted VM produces a metrics JSON file.

## Signed extensions

The optional Browser, Hypervisor, Creative, Office Lite and Developer extensions are separate SquashFS images packaged as .smx files. To build signed extension artifacts, provide an RSA private key and its matching public key:

    SMTH_SIGNING_KEY=/secure/path/smth-release.key \
    SMTH_SIGNING_PUBKEY=/secure/path/smth-release.pub \
    SMTH_ARCH=amd64 sudo -E ./scripts/build.sh

Keep the private key outside the repository and never put it in the ISO. The public key is copied into /etc/smth/extensions.pub. Without a trusted key, extension verification and installation fail closed.

Manage extensions:

    smthctl extension verify Browser-amd64.smx
    sudo smthctl extension install Browser-amd64.smx
    smthctl extension list
    sudo smthctl extension remove browser

## Boot modes

The boot menu provides Live, Persistence, Copy to RAM, Safe Graphics and Recovery Shell. The guided installer is not implemented yet; do not use this image as an installer for a device with important data.

## Test in QEMU

    qemu-system-x86_64 -m 2G -smp 2 -bios /usr/share/OVMF/OVMF_CODE_4M.fd \
      -display gtk -cdrom out/smth-os-amd64.iso

## Important limitations

- Native amd64/arm64 ISO builds and boot tests are still pending.
- The current shell is labwc + Waybar; not all requested Windows-like behaviours have been acceptance-tested.
- The signed extension format has source implementation, but needs a real signing key and integration tests.
- The 450 MiB ISO gate may fail until the base package set is slimmed.
- Runtime performance budgets, full disk installer, encrypted install, A/B updates and rollback are not yet complete.
