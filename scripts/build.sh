#!/usr/bin/env bash
# SMTH OS ISO builder.
#
# Usage: SMTH_ARCH=amd64|arm64 ./scripts/build.sh
# Must run on a native host/container of the target architecture (CI uses an
# arm64 runner for arm64, never emulation).
#
# Stages:
#   1. host dependencies           5. artwork + icons + palette tests
#   2. static repository checks    6. live-build
#   3. Rust core build + tests     7. size budget, checksums, extensions
#   4. runtime asset generation
set -euo pipefail
cd "$(dirname "$0")/.."

export SMTH_ARCH="${SMTH_ARCH:-$(dpkg --print-architecture)}"
[ "$SMTH_ARCH" = "$(dpkg --print-architecture)" ] || {
  echo "Build $SMTH_ARCH on a native $SMTH_ARCH machine (CI uses an arm64 runner)." >&2
  exit 1
}
SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "== SMTH OS build: $SMTH_ARCH =="
$SUDO apt-get update
GRUB="grub-efi-$SMTH_ARCH-bin"
[ "$SMTH_ARCH" = amd64 ] && GRUB="grub-efi-amd64-bin grub-pc-bin syslinux syslinux-common isolinux"
$SUDO apt-get install -y --no-install-recommends \
  live-build debootstrap xorriso squashfs-tools mtools dosfstools \
  cargo rustc rustfmt rust-clippy ca-certificates debian-archive-keyring \
  python3-numpy python3-pil fonts-dejavu-core $GRUB

echo "-- static repository checks"
bash scripts/check-packages.sh
for script in scripts/build.sh auto/build auto/clean config/hooks/normal/*.chroot; do
  bash -n "$script"
done
# check_wiring.py parses every packaged script (Python syntax, shell syntax and
# the executable bit), so a single call covers usr/local/bin.
python3 -m py_compile tools/*.py
python3 tools/check_wiring.py
python3 tools/test_palette.py

echo "-- Rust core: format, lint, test"
( cd core && cargo fmt --all -- --check && cargo clippy --workspace --all-targets -- -D warnings )
( cd core && cargo test --workspace --locked )

echo "-- runtime assets"
python3 tools/gen_tokens.py
python3 tools/gen_assets.py config/includes.chroot_after_packages
python3 tools/gen_cursor.py config/includes.chroot_after_packages
python3 tools/test_palette.py

echo "-- Rust release binaries"
( cd core && cargo build --release --locked )
C=config/includes.chroot_after_packages
install -D -m755 core/target/release/smthd "$C/usr/bin/smthd"
install -D -m755 core/target/release/smth-ahian "$C/usr/bin/smth-ahian"
install -D -m755 core/target/release/smthctl-core "$C/usr/bin/smthctl-core"

chmod +x auto/* config/hooks/normal/* scripts/*.sh \
  "$C"/usr/local/bin/* "$C"/usr/local/lib/smth/* 2>/dev/null || true

if [ -n "${SMTH_SIGNING_PUBKEY:-}" ]; then
  test -f "$SMTH_SIGNING_PUBKEY" || { echo "SMTH_SIGNING_PUBKEY does not exist" >&2; exit 1; }
  install -D -m644 "$SMTH_SIGNING_PUBKEY" "$C/etc/smth/extensions.pub"
fi

echo "STAGE: live-build setup"
echo "-- live-build"
$SUDO lb clean --purge >/dev/null 2>&1 || true
$SUDO env SMTH_ARCH=$SMTH_ARCH lb config
# live-build's teardown (dpkg cleanup of its build-host helpers) can return
# non-zero after the ISO has already been written successfully. Keep the status,
# say so loudly, and let the checks below decide whether the image is usable.
set +e
$SUDO env SMTH_ARCH=$SMTH_ARCH lb build
LB_STATUS=$?
set -e
echo "STAGE: lb build finished exit=$LB_STATUS"

mkdir -p out
ISO="$(find . -maxdepth 1 -type f -name '*.iso' -print -quit)"
test -n "$ISO" || { echo "no ISO produced (lb build exited $LB_STATUS, looked for ./*.iso)" >&2; exit 1; }
if [ "$LB_STATUS" -ne 0 ]; then
  echo "!! lb build reported $LB_STATUS during teardown, but $ISO exists; continuing to verify it" >&2
fi
echo "STAGE: found ISO $ISO size=$(stat -c%s "$ISO")"
# What is actually inside the image, so a budget failure is actionable.
if [ -d chroot/var/lib/dpkg ]; then
  echo "STAGE: chroot $(du -sm chroot 2>/dev/null | cut -f1) MiB installed"
  echo "STAGE: top packages $(dpkg-query --admindir=chroot/var/lib/dpkg -W -f='${Installed-Size} ${Package}\n' 2>/dev/null | sort -rn | head -12 | tr '\n' ';')"
  echo "STAGE: top dirs $(du -sm chroot/usr/* chroot/var/* 2>/dev/null | sort -rn | head -8 | tr '\n' ';')"
fi
python3 tools/check_budgets.py "$ISO" || { echo "budget gate failed for $ISO" >&2; exit 1; }
echo "STAGE: budget ok"
$SUDO mv "$ISO" "out/smth-os-$SMTH_ARCH.iso"
echo "STAGE: moved ISO to out/"
$SUDO chown "$(id -u):$(id -g)" "out/smth-os-$SMTH_ARCH.iso"

if [ -n "${SMTH_SIGNING_KEY:-}" ]; then
  test -n "${SMTH_SIGNING_PUBKEY:-}" || { echo "Set SMTH_SIGNING_PUBKEY with SMTH_SIGNING_KEY" >&2; exit 1; }
  for ext in browser hypervisor creative office-lite developer; do
    $SUDO python3 tools/build_extension.py "$ext" --arch "$SMTH_ARCH" \
      --private-key "$SMTH_SIGNING_KEY" --out out/extensions
  done
else
  echo "SMTH_SIGNING_KEY not set; signed extension artifacts skipped (fail-closed install remains active)."
fi

echo "STAGE: extensions done"
echo "-- checksums"
( cd out && sha256sum smth-os-*.iso > SHA256SUMS \
  && [ -d extensions ] && sha256sum extensions/*.smx >> SHA256SUMS || true )
ls -lh out/
echo "STAGE: checksums written"
echo "== build complete: out/smth-os-$SMTH_ARCH.iso =="
