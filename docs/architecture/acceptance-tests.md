# SMTH OS acceptance tests

Status: **plan with a verified subset**. Items marked DONE were executed and their
output is reproducible with the command shown. Everything else is still a manual
journey on a booted image and must not be claimed as passing.

## Repository checks (no ISO, no root) — DONE

- [x] Rust core tests: `cd core && cargo test --workspace --locked` → 50 passed.
      Covers palette parsing/contrast, cascade/snap/split geometry, AHIAN timing
      and copy, IPC round-trip and wire stability, file operations (collision
      names, traversal rejection, trash metadata), settings atomic write and
      schema handling, island priority, supervisor start/stop/backoff and the
      daemon socket end to end.
- [x] Rust lints: `cargo clippy --workspace --all-targets -- -D warnings`.
- [x] Rust formatting: `cargo fmt --all -- --check`.
- [x] Palette + artwork + bundled fonts: `python3 tools/test_palette.py` → every
      generated PNG is black + palette (AHIAN images use only the AHIAN pair),
      all four fonts and licences present.
- [x] Desktop wiring: `python3 tools/check_wiring.py` → every `.desktop` Exec,
      autostart line, keybind, Waybar module command and packaged script resolves;
      scripts parse and are executable.
- [x] Size model: `python3 tools/estimate_iso.py --arch amd64 --check-names`
      (also `--arch arm64`) → no unknown package names; core ~1050 MiB installed,
      estimated ~381 MiB ISO against the 450 MiB budget.
- [x] Shell/Python syntax for every packaged script (covered by the wiring check)
      and `bash -n` for build scripts and hooks.
- [x] Android APK compiles (`gradle assembleDebug`, JDK 17 + SDK 35) and passes
      zip integrity, DEX presence, bundled-font presence, package identity,
      launchable-activity identity and `apksigner verify` (894,010 bytes,
      sha256 `fe2a87fd1397f56280193363ff58109fad80c1fc04c559a59d7a74bac92315a2`).
- [x] Android APK installs and launches: GitHub Actions run 43936372541 (API 35,
      x86_64, pixel_2) — `adb install -r` ok, `am start -W -n
      os.smth.launcher/.MainActivity` ok, process still alive after 8 s, HOME
      resolves to the launcher.
- [x] Windows EXE builds and stays running: same run, windows-latest,
      PyInstaller one-file build then an 8 s liveness check (10.7 MB artifact).
- [x] CI on every push: `.github/workflows/ci.yml` ran 5 times green (rustfmt,
      clippy -D warnings, 50 Rust tests, package names, asset generation, palette,
      wiring and committed-token checks).
- [x] Startup construction model: `python3 tools/test_startup.py` → 8/8 tests
      pass (timeline 9.6 s, logo reveal, seven independent cursors, six boxes,
      construction items, landscape/portrait bounds, Reduced Motion);
      `python3 -m startup.py --print-plan` returns phase/plan without a display.
- [ ] Startup construction renderer on a booted compositor: layer-shell
      overlay, fade, click/key skip, Settings toggle. Not run in this
      environment; the QEMU boot job does not yet assert the overlay visually.

## Build and boot

- [x] Native amd64 build completes and emits an ISO: run 43951424994 wrote
      `live-image-amd64.hybrid.iso` (1,170,964,480 bytes) after `lb build` exited 0.
- [x] Native arm64 build completes and emits an ISO: same run,
      `live-image-arm64.hybrid.iso` (1,267,804,160 bytes).
- [ ] `sha256sum -c SHA256SUMS` for both ISOs (the size gate fails first, so the
      artifacts are never published).
- [ ] `tools/check_budgets.py` passes on the real ISO: **FAILS**, 1117 MiB and
      1209 MiB against 450 MiB. See `iso-budget.md`.
- [ ] Boot Live mode in UEFI QEMU at 2 GB RAM. Harness: `tools/qemu_boot_test.sh`
      plus the `boot` matrix in `.github/workflows/build.yml`; no recorded run
      for the current revision.
- [ ] Boot safe graphics and recovery shell.
- [ ] Persistence: file survives a reboot with a SMTH-PERSISTENCE partition.
- [ ] Install to a disposable disk and boot the installed system.
- [ ] Verify `smthd` starts, supervises `notifd`/`moded`, and restarts a killed
      child (backoff visible in `smthctl-core status`).

## Desktop — NOT RUN

- [ ] Start menu opens, filters, launches, closes with Escape.
- [ ] Taskbar modules (`smth-glance`) render; every dock/taskbar icon launches.
- [ ] Cascade placement new windows without overlapping exactly.
- [ ] Snap left/right (W-Left/W-Right) and split-screen arrangement.
- [ ] Quick settings, notifications (bell + DND), lock and power actions.
- [ ] Reduce Motion disables decorative animation, including AHIAN.
- [ ] Layout switch desktop/mobile at portrait and landscape sizes.

## AHIAN — timeline VERIFIED, animation NOT RUN

- [x] Plan contains progressive terminal errors before the storm.
- [x] Dialog storm spans ~10 s, all dialogs on-screen, chronological.
- [x] Blue screen text is exactly "wants to make your life beautiful".
- [x] Countdown is 9 seconds.
- [x] AHIAN wallpaper path exists and uses the purple/teal pair.
- [x] `unahian` copy is exactly "looks like you dont like ahian", restores normal.
- [ ] Run `ahian` on a booted image: dialogs appear gradually, BSOD shows, 9 s
      countdown, then the purple/teal desktop.
- [ ] Run `unahian`: red screen appears, normal wallpaper/mode restored.

## Apps — NOT RUN

- [ ] Settings: Wi-Fi connect/disconnect, Bluetooth pair, volume/mute, power
      profile, wallpaper, Reduce Motion, AHIAN toggle.
- [ ] Files: create, rename, copy, move, trash, extract zip/tar, mount ISO; a
      failing operation must show a notification (no silent `except: pass`).
- [ ] Calculator: precedence, parentheses, decimals, divide-by-zero.
- [ ] Clock: world time, stopwatch start/stop/reset, timer notification, alarm.
- [ ] Store: signed index verify, hash-mismatch rejection, install/remove.
- [ ] Browser: shows the extension prompt when WebKit is absent; browses when the
      Browser extension is installed.
- [ ] Media player: audio/video playback, background playback.
- [ ] Terminal: AHIAN sequence, `unahian`.

## Extensions and security — NOT RUN

- [ ] Invalid signature rejected; payload hash mismatch rejected.
- [ ] Wrong architecture rejected.
- [ ] Valid extension mounts read-only with `nodev,nosuid`.
- [ ] Extension apps appear/disappear on install/remove; mounts restored at boot.
- [ ] No root desktop login; nftables default-deny inbound active.

## Performance — NOT RUN

Record hardware, VM configuration, kernel, commit and method. Budgets:
core ISO ≤ 450 MiB preferred (≤ 900 MiB maximum acceptable), idle RAM ≤ 350 MB on 2 GB, boot ≤ 12 s SSD / ≤ 20 s USB,
start menu ≤ 150 ms, settings ≤ 500 ms, cold app ≤ 700 ms, idle CPU < 3 %.

Do not mark a checkbox complete from source inspection alone.
