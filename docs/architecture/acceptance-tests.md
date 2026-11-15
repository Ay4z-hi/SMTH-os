# SMTH OS acceptance tests

Status: TEST PLAN ONLY — not yet run on a booted ISO.

## Build and boot
- [ ] Native amd64 build completes and emits ISO + SHA-256.
- [ ] Native arm64 build completes and emits ISO + SHA-256.
- [ ] Verify ISO checksums.
- [ ] Boot Live mode in UEFI QEMU at 2GB RAM.
- [ ] Boot safe graphics and recovery shell.
- [ ] Boot persistence mode and verify a file survives reboot.
- [ ] Install to a disposable virtual disk and verify reboot into installed system.

## Desktop
- [ ] Start menu opens, filters apps, launches apps, closes with Escape.
- [ ] Centered taskbar and desktop/mobile layout switch work at portrait and landscape sizes.
- [ ] Snap left/right and keyboard shortcuts work.
- [ ] Quick settings, notifications, lock screen and power actions work.
- [ ] Reduce Motion disables decorative motion.

## Apps
- [ ] Settings display, network, sound, power and security controls change actual system state.
- [ ] Files can create, copy, move, rename, delete, mount ISO and safely extract archives.
- [ ] Calculator handles precedence, parentheses, decimals, divide-by-zero and rejects code execution.
- [ ] Store verifies package hashes and rejects unsigned/invalid extensions.
- [ ] Browser, media player and terminal launch and close normally.

## Extensions and security
- [ ] Invalid signature is rejected.
- [ ] Payload hash mismatch is rejected.
- [ ] Wrong architecture is rejected.
- [ ] Valid extension mounts read-only with nodev/nosuid.
- [ ] Extension apps appear and disappear when enabled/removed.
- [ ] Extension mounts are restored at boot.
- [ ] No root desktop login; firewall and sandbox policies are active.

## Performance
Record hardware, VM configuration, kernel, commit, and measurement method.
- [ ] Core ISO <=450MB.
- [ ] Idle RAM <=350MB on 2GB VM.
- [ ] Boot <=12s SSD / <=20s USB.
- [ ] Start menu <=150ms.
- [ ] Settings <=500ms.
- [ ] Cold app launch <=700ms.
- [ ] Idle CPU <3%.
- [ ] CI fails when a measured budget is exceeded.

Do not mark a checkbox complete from source inspection alone.
