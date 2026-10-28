#!/usr/bin/env bash
# SMTH OS ISO builder. Run on Debian/Ubuntu (root or sudo), or let GitHub Actions run it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

$SUDO apt-get update
$SUDO apt-get install -y live-build debootstrap xorriso squashfs-tools mtools \
  cargo rustc ca-certificates debian-archive-keyring

# 1. build SMTH binaries
( cd "$ROOT/freezerd" && cargo build --release )

# 2. assemble live-build tree
rm -rf "$ROOT/build"; mkdir -p "$ROOT/build"; cd "$ROOT/build"
lb config \
  --distribution trixie --architectures amd64 \
  --archive-areas "main contrib non-free-firmware" \
  --binary-images iso-hybrid --bootloaders "grub-efi,syslinux" \
  --debian-installer none --linux-flavours amd64 \
  --iso-application "SMTH OS" --iso-volume "SMTH_OS" \
  --bootappend-live "boot=live components quiet splash username=smth hostname=smth"

cp "$ROOT/live/package-lists/"* config/package-lists/
cp "$ROOT/live/hooks/"* config/hooks/normal/
chmod +x config/hooks/normal/*
mkdir -p config/includes.chroot_after_packages/usr/bin
cp -r "$ROOT/overlay/"* config/includes.chroot_after_packages/
cp "$ROOT/freezerd/target/release/freezerd" config/includes.chroot_after_packages/usr/bin/

# 3. build
$SUDO lb build
ls -lh ./*.iso
mv ./*.iso "$ROOT/build/smth-os-amd64.iso" 2>/dev/null || true
echo "DONE: $ROOT/build/smth-os-amd64.iso"
