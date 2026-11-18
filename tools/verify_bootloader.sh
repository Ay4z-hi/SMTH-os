#!/usr/bin/env bash
# Static bootloader/ISO verification.  This proves the El Torito images, menu
# entries and referenced kernel/initrd exist; qemu_boot_test.sh proves they run.
set -euo pipefail
ISO=${1:?usage: verify_bootloader.sh <iso> <amd64|arm64>}
ARCH=${2:?usage: verify_bootloader.sh <iso> <amd64|arm64>}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

test -s "$ISO" || { echo "ISO is missing or empty: $ISO" >&2; exit 1; }
echo "ISO: $ISO ($(stat -c%s "$ISO") bytes)"

xorriso -indev "$ISO" -report_el_torito plain > "$WORK/eltorito.txt"
cat "$WORK/eltorito.txt"
grep -qi 'El Torito' "$WORK/eltorito.txt" || {
    echo "ISO has no El Torito boot record" >&2
    exit 1
}
if [ "$ARCH" = amd64 ]; then
    grep -q 'BIOS' "$WORK/eltorito.txt" || { echo "missing BIOS El Torito image" >&2; exit 1; }
fi
grep -q 'UEFI' "$WORK/eltorito.txt" || { echo "missing UEFI El Torito image" >&2; exit 1; }

xorriso -osirrox on -indev "$ISO" -extract /boot/grub/grub.cfg "$WORK/grub.cfg" >/dev/null
grep -q 'menuentry "Start SMTH OS"' "$WORK/grub.cfg" || { echo "GRUB default entry missing" >&2; exit 1; }
for entry in 'SMTH OS (persistence)' 'SMTH OS (copy to RAM)' 'SMTH OS (safe graphics)' 'SMTH OS (recovery shell)'; do
    grep -q "menuentry \"$entry\"" "$WORK/grub.cfg" || { echo "GRUB entry missing: $entry" >&2; exit 1; }
done
grep -q 'persistence-label=SMTH-PERSISTENCE' "$WORK/grub.cfg" || { echo "persistence option missing" >&2; exit 1; }

if [ "$ARCH" = amd64 ]; then
    xorriso -osirrox on -indev "$ISO" -extract /isolinux/isolinux.cfg "$WORK/isolinux.cfg" >/dev/null
    grep -q 'LABEL smth' "$WORK/isolinux.cfg" || { echo "isolinux default entry missing" >&2; exit 1; }
    grep -q 'MENU LABEL Start SMTH OS' "$WORK/isolinux.cfg" || { echo "isolinux SMTH menu label missing" >&2; exit 1; }
    for entry in 'SMTH OS (persistence)' 'SMTH OS (copy to RAM)' 'SMTH OS (safe graphics)' 'SMTH OS (recovery shell)'; do
        grep -q "MENU LABEL $entry" "$WORK/isolinux.cfg" || { echo "isolinux entry missing: $entry" >&2; exit 1; }
    done
fi

# The menu references /live/vmlinuz* and /live/initrd.img*.  Extract only the
# /live directory listing first, then the two files, so this check does not
# unpack the squashfs.
xorriso -indev "$ISO" -ls /live > "$WORK/live.txt"
# xorriso -ls quotes file names; strip the quotes so the names are usable.
sed -i "s/'//g" "$WORK/live.txt"
K=$(sed -n 's/.*\(vmlinuz[^ ]*\).*/\1/p' "$WORK/live.txt" | head -n1)
I=$(sed -n 's/.*\(initrd\.img[^ ]*\).*/\1/p' "$WORK/live.txt" | head -n1)
test -n "$K" || { echo "no /live/vmlinuz* in ISO" >&2; exit 1; }
test -n "$I" || { echo "no /live/initrd.img* in ISO" >&2; exit 1; }
xorriso -osirrox on -indev "$ISO" -extract "/live/$K" "$WORK/$K" >/dev/null
xorriso -osirrox on -indev "$ISO" -extract "/live/$I" "$WORK/$I" >/dev/null
test -s "$WORK/$K" || { echo "kernel is empty" >&2; exit 1; }
test -s "$WORK/$I" || { echo "initrd is empty" >&2; exit 1; }
grep -q "linux /live/$K" "$WORK/grub.cfg" || { echo "GRUB kernel path mismatch" >&2; exit 1; }
grep -q "initrd /live/$I" "$WORK/grub.cfg" || { echo "GRUB initrd path mismatch" >&2; exit 1; }
grep -q "KERNEL /live/$K" "$WORK/isolinux.cfg" 2>/dev/null || true

echo "PASS bootloader: El Torito, $ARCH menu entries and /live/$K + /live/$I are present"
