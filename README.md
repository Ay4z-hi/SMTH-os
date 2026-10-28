# SMTH OS build kit

## Build in the browser (no local machine)
1. Create a free GitHub account and a new repository.
2. Upload everything from this zip (keep the folder structure, including `.github/`).
3. Open the **Actions** tab -> **Build SMTH OS ISO** -> **Run workflow**.
4. After ~15-30 min, open the finished run and download the **smth-os-iso** artifact (zip containing `smth-os-amd64.iso`).

## Build locally (Debian/Ubuntu)
    ./build.sh      # output: build/smth-os-amd64.iso

## Test
    qemu-system-x86_64 -enable-kvm -m 4G -smp 4 -bios /usr/share/OVMF/OVMF_CODE.fd \
      -device virtio-gpu-gl -display gtk,gl=on -cdrom build/smth-os-amd64.iso
Or write it to USB with balenaEtcher / `dd`. It is a live image (runs from the stick); there is no installer yet.

## What you get
Stand-in session: Weston with black desktop, matte-gray panel, `freezerd` running.
`smthd` (the WinTab compositor) is not in here yet: add it as a crate and swap `ExecStart` in
`overlay/etc/systemd/system/smth-session.service`.

Untested: this kit was written offline and never built. Expect to fix small errors on the first run.
