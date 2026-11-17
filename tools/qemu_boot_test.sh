#!/usr/bin/env bash
# Boot a built live ISO in QEMU, wait for the real graphical session, and fail
# unless smth-bootcheck prints SMTH_BOOT: OK over the serial console.
set -euo pipefail
ISO=${1:?usage: qemu_boot_test.sh <iso> <amd64|arm64>}
ARCH=${2:?usage: qemu_boot_test.sh <iso> <amd64|arm64>}
WORK=$(mktemp -d)
LOG="${SMTH_QEMU_LOG:-$WORK/qemu.log}"
PID=""
cleanup() {
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        wait "$PID" 2>/dev/null || true
    fi
    if [ "${KEEP_QEMU_LOG:-0}" = "1" ] || [ -n "${SMTH_QEMU_LOG:-}" ]; then
        echo "QEMU log kept at $LOG"
    else
        rm -rf "$WORK"
    fi
}
trap cleanup EXIT

test -s "$ISO" || { echo "ISO is missing or empty: $ISO" >&2; exit 1; }
echo "Extracting kernel and initrd from $ISO"
xorriso -osirrox on -indev "$ISO" -extract /live "$WORK/live" >/dev/null
K=$(ls "$WORK"/live/vmlinuz* 2>/dev/null | head -n1)
I=$(ls "$WORK"/live/initrd.img* 2>/dev/null | head -n1)
test -n "$K" && test -n "$I" || { echo "no kernel/initrd in /live" >&2; exit 1; }
echo "kernel: $(basename "$K")  initrd: $(basename "$I")"

ACCEL=tcg
CPU=max
if [ -w /dev/kvm ] && [ -r /dev/kvm ]; then
    ACCEL=kvm
    CPU=host
fi
echo "architecture=$ARCH accel=$ACCEL cpu=$CPU"

if [ "$ARCH" = amd64 ]; then
    QEMU=qemu-system-x86_64
    APPEND="boot=live components console=tty0 console=ttyS0,115200 smth.bootcheck=1 username=smth hostname=smth loglevel=4"
    MACHINE=(-machine q35)
    MEDIA=(-cdrom "$ISO")
else
    QEMU=qemu-system-aarch64
    APPEND="boot=live components console=ttyAMA0,115200 smth.bootcheck=1 username=smth hostname=smth loglevel=4"
    MACHINE=(-machine virt)
    # virt has no IDE bus; attach the ISO as a readable virtio disk.  live-boot
    # scans block devices for /live/filesystem.squashfs, not only sr0.
    MEDIA=(-drive "file=$ISO,format=raw,if=virtio,readonly=on")
fi
command -v "$QEMU" >/dev/null || { echo "$QEMU is not installed" >&2; exit 1; }

"$QEMU" \
    "${MACHINE[@]}" -accel "$ACCEL" -cpu "$CPU" \
    -m 2048 -smp 2 -no-reboot -display none \
    -serial "file:$LOG" -monitor none \
    -kernel "$K" -initrd "$I" -append "$APPEND" \
    "${MEDIA[@]}" &
PID=$!
echo "QEMU pid=$PID; waiting for SMTH_BOOT: OK (up to 8 minutes)"

ok=0
failed=0
for _ in $(seq 1 240); do
    if grep -q 'SMTH_BOOT: OK' "$LOG" 2>/dev/null; then ok=1; break; fi
    if grep -q 'SMTH_BOOT: FAIL' "$LOG" 2>/dev/null; then failed=1; break; fi
    if ! kill -0 "$PID" 2>/dev/null; then break; fi
    sleep 2
done

echo "---- serial console (tail) ----"
tail -n 160 "$LOG" 2>/dev/null || true
echo "-------------------------------"

if [ "$ok" -eq 1 ]; then
    echo "PASS boot: $ARCH live image reached the desktop and all boot checks"
    exit 0
fi
if [ "$failed" -eq 1 ]; then
    echo "FAIL boot: smth-bootcheck reported a session/service failure" >&2
else
    echo "FAIL boot: no SMTH_BOOT marker within 8 minutes (qemu alive=$(kill -0 "$PID" 2>/dev/null && echo yes || echo no))" >&2
fi
exit 1
