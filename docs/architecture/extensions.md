# SMTH extension format (.smx)

Status: IMPLEMENTED IN SOURCE; build/install/signature round-trip NOT executed in
this environment (needs root, debootstrap and a signing key).

An `.smx` is a ZIP container holding exactly `manifest.json`, `manifest.sig` and
`payload.squashfs`. `manifest.sig` is a detached RSA/SHA-256 signature over the
exact manifest bytes; the payload is independently SHA-256 checked before the
signature is accepted. Fields: `id`, `name`, `version`, `arch`, `sha256`.

Architecture values: `all`, `amd64`, `arm64`, or the host machine name. The public
key lives at `/etc/smth/extensions.pub`; without it, verification and installation
fail closed. Payloads mount read-only at `/opt/smth/extensions/ID` with
`loop,ro,nodev,nosuid`; their `.desktop` files are linked into the application
catalogue (`/usr/local/share/applications/smth-ext-*`), and a systemd unit
re-mounts installed extensions at boot.

## Commands

```sh
smthctl extension verify Browser-amd64.smx
sudo smthctl extension install Browser-amd64.smx
smthctl extension list
sudo smthctl extension remove browser
```

## Per-architecture packages

`extensions/*/packages.txt` accepts an `@arch` suffix, filtered by
`tools/build_extension.py`, `scripts/check-packages.sh` and
`tools/estimate_iso.py`:

```
wine @amd64
box64 @arm64
```

This is how one extension definition serves both targets without shipping
impossible packages.

## Why the core ISO depends on extensions

`docs/architecture/iso-budget.md` records the measurement: including Wine,
WebKitGTK, Vulkan, KDE Connect and WayVNC in the core closure put it at 2233 MiB
installed, far beyond the 450 MiB ISO budget. They now ship in extensions:

| Extension | Contents that matter for size |
|---|---|
| Browser | Firefox ESR, WebKitGTK (SMTH Browser backend) |
| Hypervisor | QEMU, Wine, Vulkan drivers, KDE Connect, WayVNC |
| Creative | Loupe, Snapshot, Drawing |
| Office Lite | AbiWord, Gnumeric, Evince |
| Developer | git, build tools, Python, box64 on arm64 |

Core apps detect missing extension content and name the extension required
(`smth-browser`, `smth-open`, `smth-corelink`) instead of appearing broken.

## Removed pack-import workflows

`.github/workflows/import-smth-v5-pack.yml` pointed at a ZIP that is not in the
repository, and `import-smth-v6-pack.yml` rewrote the working tree from
`smth-v6-pack.zip` on demand with write permissions. The v6 import is the likely
cause of the flattened `config/includes.chroot_after_packages-usr-local-bin-*`
paths described in `docs/audit/2026-11-audit.md`. Both workflows and the ZIP were
removed; the tracked files are the source of truth.

## Not yet implemented

Dependency solving between extensions, automatic updates, version rollback and a
graphical extension browser. Extension installation is a root operation by design.
