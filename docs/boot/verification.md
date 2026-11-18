# Boot verification

Status: **`amd64` and `arm64` boot verified in CI for `b70bc09`** (Build SMTH OS
run #164, both `Boot ISO` jobs green, each gated on `SMTH_BOOT: OK` in the
serial log).

## Local / CI commands

Both commands take a built ISO and architecture:

```sh
bash tools/verify_bootloader.sh out/smth-os-amd64.iso amd64
bash tools/qemu_boot_test.sh out/smth-os-amd64.iso amd64
```

`verify_bootloader.sh` checks the El Torito images (UEFI; BIOS as well on
amd64), the GRUB and isolinux menu entries, and that the referenced
`/live/vmlinuz*` and `/live/initrd.img*` exist and are non-empty.

`qemu_boot_test.sh` extracts the live kernel/initrd, starts QEMU with 2 GB RAM
and two vCPUs, and attaches the ISO read-only plus a `virtio-rng` device. It
uses KVM only when the device is readable/writable; otherwise it uses TCG. The
kernel command line adds `smth.bootcheck=1`, which enables the `smth-bootcheck`
systemd unit. The script waits up to eight minutes on `amd64` and thirty minutes
on `arm64` (TCG) for `SMTH_BOOT: OK` on the serial console, and fails on
`SMTH_BOOT: FAIL` or QEMU exit.

The graphical session is started from tty1 autologin, not a display manager:
`.bash_profile` runs `smth-session`, which starts `dbus-run-session -- labwc`;
labwc's autostart starts `smthd`, `smth-home`, the startup overlay and
`swayidle`. `smth-bootcheck` waits for `labwc`, `waybar`, `smthd`, the GTK helper
processes and the Wayland/smthd sockets, then checks that `smth-extensions` and
`nftables` are active.

## CI

`.github/workflows/build.yml` has a `boot` matrix (`amd64` on `ubuntu-latest`,
`arm64` on `ubuntu-24.04-arm`) that downloads each ISO, installs `xorriso` and
QEMU, runs both checks, and uploads the serial log when the job fails.

## What this does not prove

- Direct-kernel boot bypasses GRUB/El Torito execution; the bootloader itself is
  checked statically.
- QEMU is not hardware. Audio, Wi-Fi, Bluetooth, suspend, GPU acceleration and
  firmware loading on real devices are not covered.
- The installed-system workflow is separate and is not exercised by this job.

Do not mark an architecture "boot tested" until its `boot` job has a recorded
`SMTH_BOOT: OK` and the log has been inspected.
