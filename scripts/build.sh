#!/usr/bin/env bash
# SMTH OS ISO builder. Usage: SMTH_ARCH=amd64|arm64 ./scripts/build.sh (native arch only)
set -euo pipefail
cd "$(dirname "$0")/.."
export SMTH_ARCH="${SMTH_ARCH:-$(dpkg --print-architecture)}"
[ "$SMTH_ARCH" = "$(dpkg --print-architecture)" ] || { echo "Build $SMTH_ARCH on a native $SMTH_ARCH machine (CI uses an arm64 runner)." >&2; exit 1; }
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

$SUDO apt-get update
GRUB="grub-efi-$SMTH_ARCH-bin"; [ "$SMTH_ARCH" = amd64 ] && GRUB="grub-efi-amd64-bin grub-pc-bin syslinux syslinux-common isolinux"
$SUDO apt-get install -y live-build debootstrap xorriso squashfs-tools mtools dosfstools \
  cargo rustc ca-certificates debian-archive-keyring python3-numpy python3-pil fonts-dejavu-core $GRUB

bash scripts/check-packages.sh
bash -n scripts/build.sh
python3 -m py_compile tools/*.py config/includes.chroot_after_packages/usr/local/bin/ahian config/includes.chroot_after_packages/usr/local/bin/smthctl config/includes.chroot_after_packages/usr/local/lib/smth/*.py
python3 tools/gen_tokens.py
python3 tools/gen_assets.py config/includes.chroot_after_packages
python3 tools/gen_cursor.py config/includes.chroot_after_packages
python3 tools/test_palette.py

( cd freezerd && cargo build --release )
chmod +x auto/* config/hooks/normal/* scripts/*.sh
C=config/includes.chroot_after_packages
install -D -m755 freezerd/target/release/freezerd "$C/usr/bin/freezerd"
chmod +x "$C"/usr/local/bin/* "$C"/usr/local/lib/smth/* 2>/dev/null || true

$SUDO lb clean --purge >/dev/null 2>&1 || true
$SUDO env SMTH_ARCH=$SMTH_ARCH lb config
$SUDO env SMTH_ARCH=$SMTH_ARCH lb build
mkdir -p out
ISO="$(find . -maxdepth 1 -type f -name '*.iso' -print -quit)"
test -n "$ISO"
$SUDO mv "$ISO" "out/smth-os-$SMTH_ARCH.iso"
$SUDO chown "$(id -u):$(id -g)" "out/smth-os-$SMTH_ARCH.iso"
( cd out && sha256sum "smth-os-$SMTH_ARCH.iso" > "smth-os-$SMTH_ARCH.iso.sha256" )
ls -lh out/
