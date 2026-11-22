#!/usr/bin/env bash
# Host-side driver for the live RAM audit.
#
#   bash tools/ram_audit_qemu.sh instrument <iso> <out.iso>
#   bash tools/ram_audit_qemu.sh run <iso> <amd64|arm64> <mib> [<mib> ...]
#
# "instrument" unpacks the live squashfs, adds the read-only audit harness
# (smth-ramaudit + ram_audit_snapshot.py + a systemd unit that only starts when
# the kernel command line asks for it) and writes a new ISO with the original
# boot images.  The running system, its packages and its services are
# untouched; only the harness is added.
#
# "run" boots the instrumented image in QEMU at each memory size, in parallel,
# and keeps one serial log per size.  Serial output is the only channel back,
# so the guest prints a JSON snapshot per phase between SMTH_AUDIT markers.
#
# Rootless: set XORRISO/UNSQUASHFS/MKSQUASHFS/QEMU_X86/QEMU_ARM to binaries
# unpacked from distribution packages (see the report for the exact commands),
# or have them on PATH.
set -uo pipefail

ARCH_ISO="$PWD"

tool() {
    local name=$1
    local var=$2
    if [ -n "${!var:-}" ]; then echo "${!var}"; else command -v "$name" || true; fi
}

XORRISO=$(tool xorriso XORRISO)
UNSQUASHFS=$(tool unsquashfs UNSQUASHFS)
MKSQUASHFS=$(tool mksquashfs MKSQUASHFS)

instrument() {
    local iso=$1 out=$2
    local work=${WORK:-$(mktemp -d)}
    mkdir -p "$work"
    echo "== extracting /live from $iso into $work"
    "$XORRISO" -osirrox on -indev "$iso" -extract /live "$work/live" >/dev/null || return 1
    test -s "$work/live/filesystem.squashfs" || { echo "no filesystem.squashfs" >&2; return 1; }

    if [ ! -d "$work/rootfs" ]; then
        echo "== unpacking squashfs"
        "$UNSQUASHFS" -d "$work/rootfs" "$work/live/filesystem.squashfs" >"$work/unsquashfs.log" 2>&1 \
            || { tail -5 "$work/unsquashfs.log" >&2; return 1; }
    fi

    echo "== adding audit harness"
    install -D -m 755 tools/ram_audit_guest.sh "$work/rootfs/usr/local/bin/smth-ramaudit"
    install -D -m 755 tools/ram_audit_snapshot.py "$work/rootfs/usr/local/lib/smth/ram_audit_snapshot.py"
    cat > "$work/rootfs/etc/systemd/system/smth-ramaudit.service" <<'UNIT'
[Unit]
Description=SMTH OS live RAM audit probe
ConditionKernelCommandLine=smth.ramaudit=1
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/smth-ramaudit
StandardOutput=journal+console
StandardError=journal+console
TimeoutStartSec=1800

[Install]
WantedBy=multi-user.target
UNIT
    mkdir -p "$work/rootfs/etc/systemd/system/multi-user.target.wants"
    ln -sf ../smth-ramaudit.service \
        "$work/rootfs/etc/systemd/system/multi-user.target.wants/smth-ramaudit.service"

    echo "== repacking squashfs (1 MiB blocks, zstd)"
    time "$MKSQUASHFS" "$work/rootfs" "$work/filesystem.squashfs" \
        -noappend -comp zstd -b 1M -no-progress -processors "$(nproc)" \
        >"$work/mksquashfs.log" 2>&1 || { tail -5 "$work/mksquashfs.log" >&2; return 1; }

    echo "== rebuilding ISO with the original boot images"
    "$XORRISO" -indev "$iso" -outdev "$out" \
        -map "$work/filesystem.squashfs" /live/filesystem.squashfs \
        -boot_image any replay -commit >"$work/xorriso.log" 2>&1 \
        || { tail -20 "$work/xorriso.log" >&2; return 1; }
    ls -l "$out"
    echo "instrumented ISO: $out (work dir $work)"
}

run_tier() {
    local iso=$1 arch=$2 mib=$3 log=$4
    local kernel initrd append qemu machine media gpu rng
    mkdir -p "$(dirname "$log")"
    if [ "$arch" = amd64 ]; then
        qemu=${QEMU_X86:-qemu-system-x86_64}
        machine=(-machine q35)
        media=(-cdrom "$iso")
        gpu=()
        rng=(-device virtio-rng-pci)
        append="boot=live components console=tty0 console=ttyS0,115200 smth.bootcheck=1 smth.ramaudit=1 username=smth hostname=smth loglevel=4"
    else
        qemu=${QEMU_ARM:-qemu-system-aarch64}
        machine=(-machine virt)
        media=(-drive "file=$iso,format=raw,if=virtio,readonly=on")
        gpu=(-device virtio-gpu-pci)
        rng=(-device virtio-rng-device)
        append="boot=live components console=ttyAMA0,115200 smth.bootcheck=1 smth.ramaudit=1 username=smth hostname=smth loglevel=4"
    fi
    kernel=$(ls "$KERNEL_DIR"/vmlinuz* 2>/dev/null | head -n1)
    initrd=$(ls "$KERNEL_DIR"/initrd.img* 2>/dev/null | head -n1)
    test -n "$kernel" && test -n "$initrd" || { echo "no kernel/initrd in $KERNEL_DIR" >&2; return 1; }

    echo "== $arch ${mib} MiB -> $log"
    "$qemu" "${machine[@]}" -accel tcg -cpu max -m "$mib" -smp 2 -no-reboot \
        -display none -serial "file:$log" -monitor none \
        -kernel "$kernel" -initrd "$initrd" -append "$append" \
        "${media[@]}" "${rng[@]}" "${gpu[@]}" \
        -device virtio-net-pci,netdev=n0 -netdev user,id=n0 \
        >"$log.qemu" 2>&1 &
    echo $! > "$log.pid"
}

wait_tiers() {
    local timeout=${1:-2400} start=$SECONDS
    while :; do
        local alive=0
        for pidfile in "$LOG_DIR"/*.pid; do
            [ -f "$pidfile" ] || continue
            pid=$(cat "$pidfile")
            if kill -0 "$pid" 2>/dev/null; then
                alive=$((alive + 1))
            fi
        done
        local done_markers
        done_markers=$(grep -l 'SMTH_AUDIT: DONE' "$LOG_DIR"/*.log 2>/dev/null | wc -l)
        echo "[$((SECONDS - start))s] vms alive=$alive done=$done_markers/$(ls "$LOG_DIR"/*.log 2>/dev/null | wc -l)"
        [ "$alive" -eq 0 ] && break
        [ $((SECONDS - start)) -gt "$timeout" ] && { echo "timeout after ${timeout}s"; break; }
        # Stop a VM once it reported DONE: qemu would otherwise sit at the
        # powered-off prompt forever.
        for log in "$LOG_DIR"/*.log; do
            [ -f "$log.pid" ] || continue
            if grep -q 'SMTH_AUDIT: DONE' "$log" 2>/dev/null; then
                pid=$(cat "$log.pid")
                kill "$pid" 2>/dev/null
                rm -f "$log.pid"
            fi
        done
        sleep 15
    done
}

run_matrix() {
    local iso=$1 arch=$2; shift 2
    LOG_DIR=${LOG_DIR:-/tmp/audit/$arch}
    KERNEL_DIR=${KERNEL_DIR:-$ARCH_ISO/live-$arch}
    mkdir -p "$LOG_DIR"
    echo "== extracting kernel/initrd for $arch"
    rm -rf "$KERNEL_DIR"; mkdir -p "$KERNEL_DIR"
    "$XORRISO" -osirrox on -indev "$iso" -extract /live "$KERNEL_DIR" >/dev/null || return 1
    for mib in "$@"; do
        run_tier "$iso" "$arch" "$mib" "$LOG_DIR/$arch-$mib.log" &
    done
    wait_tiers "${WAIT_TIMEOUT:-2400}"
}

case "${1:-}" in
    instrument) shift; instrument "$@" ;;
    run) shift; run_matrix "$@" ;;
    *) sed -n '2,20p' "$0"; exit 2 ;;
esac
