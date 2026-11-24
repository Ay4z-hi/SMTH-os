# SMTH OS RAM audit — Phase A recovery report

Date: 2026-11-24  
Repository: Ay4z-hi/SMTH-os  
Current branch: freebuff/c4825a929e7ec0611cffd1b8  
Current commit: bf11090 — "Add a bootable RAM audit harness for the live image"

## 1. Repository and current state

- Working tree at this commit contains the native C modules and the new live RAM audit harness.
- Native C commits:
  - 3ed829d — "Move the taskbar sampler and layout watcher into native C"
  - 7dd4a14 — "Skip shell parity where the image lacks the shell's own tools"
- Audit harness commit:
  - bf11090 — adds `tools/ram_audit_qemu.sh`, `tools/ram_audit_guest.sh`, and `tools/ram_audit_snapshot.py`
- Relevant prior reports:
  - `docs/audit/2026-11-audit.md`
  - `docs/performance/ram-optimization.md`

## 2. Existing audit tooling found in repository

Host-side:
- `tools/ram_audit_qemu.sh`
- `tools/qemu_boot_test.sh`
- `tools/verify_bootloader.sh`

In-guest:
- `tools/ram_audit_guest.sh`
- `tools/ram_audit_snapshot.py`

Measurement and native validation:
- `tools/measure_ram.py`
- `tools/bench_native.py`
- `tools/test_native.py`
- `tools/check_wiring.py`

## 3. Existing measurement artifacts found locally

No ISOs, VM logs, snapshots, or previous Cloud session artifacts were present in this workspace at the start of recovery. In particular, no `/tmp` audit work directories or running VM processes were assumed to exist.

Downloaded for comparison only (not ISOs):
- GitHub release `latest-os` boot logs:
  - `qemu-amd64.log`
  - `qemu-arm64.log`
- These logs show successful desktop session boot for the pre-audit, pre-native-C release image. They do not contain `SMTH_AUDIT` markers and therefore do not provide the RAM measurements requested by this task.

## 4. GitHub release and CI artifact status

GitHub releases:
- `latest-os` was published 2026-11-20, before native C commits 3ed829d and 7dd4a14.
- Its ISOs are therefore not the native-C/audit-harness builds.
- Its boot logs contain no RAM audit snapshots.

GitHub Actions `build.yml`:
- Run for commit 3ed829d: failed
- Run for commit 7dd4a14: failed
- Run for current commit bf11090: completed successfully

Current successful run:
- Run ID: 45057955030
- Artifacts observed:
  - `smth-os-amd64` (ISO, not expired)
  - `smth-os-arm64` (ISO, not expired)
  - `boot-log-amd64`
  - `boot-log-arm64`

Artifact download requires GitHub authentication. The local `gh` CLI is not authenticated, so the CI ISOs and boot logs were not downloaded in this phase. Their existence and non-expired status were verified through the GitHub API.

## 5. Recovered conclusions from repository and artifacts

- The repository already has the measurement harness needed for a reliable live RAM audit.
- The native C modules are present in source form.
- The latest published release is older than the native C work and is not suitable as the native-C baseline.
- A successful current-commit CI build exists, but its artifacts are not locally available without authenticated GitHub access.
- No actual native-C ISO RAM measurements have yet been recovered in this workspace.

## 6. What remains unverified

The following items are explicitly unverified at the end of Phase A:

1. AMD64 RAM measurements for the native-C/audit-harness image.
2. ARM64 RAM measurements for the native-C/audit-harness image.
3. Idle, boot, settings, file manager, music, and multi-application memory phases.
4. Root cause and fix for `smth-home` high memory consumption.
5. Root cause and fix for the GTK "GtkWindow is not a layer surface" error.
6. Root cause and fix for the duplicate Waybar process.
7. Root cause and fix for disappearing application processes.
8. Before/after memory measurements after optimizations.
9. ARM64-specific native C build and runtime behavior.
10. Any on-image measurement produced by `tools/ram_audit_snapshot.py`.

## 7. Phase A boundary

No QEMU VMs were launched, no ISOs were rebuilt, and no native code was modified in this phase. The next phase should diagnose the desktop helper crashes and duplicate processes before running the live RAM matrix.

## 8. Phase B.5 minimal repairs (2026-11-24)

Confirmed repairs applied (no RAM optimization started):

1. Duplicate Waybar startup race fixed in `config/.../usr/local/bin/smth-mode`:
   - Added `flock -x` over the whole start/restart block using `~/.config/smth/.mode.lock`.
   - `.current` is now written atomically via temp file + `mv`.
   - Autostart and `smth-moded` may both invoke `smth-mode auto`; the lock serialises them and the second exits through the `.current` guard instead of starting a second Waybar.
2. GTK layer-shell initialisation guarded in `home.py` and `notifd.py` (try/except with stderr logging; home falls back to `fullscreen()`), preserving desktop design and apps.
3. Application launch failures are now reported instead of swallowed in `home.py` (`icon_button`) and `launcher.py` (`launch()`).
4. `Stats._raw()`/`Stats.mem()`/`Stats.disk()` in `home.py` now guard missing `/proc` fields (including missing `MemAvailable`) and return `None`/`0` instead of raising.
5. `smth-home`/`smth-notifd` wrappers now search standard library paths (and `find`) when `ldconfig` has no cache entry, reducing the missing-preload trigger for "GtkWindow is not a layer surface".

Regression coverage added:
- `tools/test_phase_b5_repairs.py` (source assertions + sequential and concurrent `smth-mode` locking test).
- `tools/check_wiring.py` now knows `flock`.

Checks run:
- `python3 tools/check_wiring.py` -> PASS
- `make -C native clean all` -> OK
- `python3 tools/test_native.py` -> PASS
- `python3 tools/test_phase_b5_repairs.py` -> PASS
- `python3 -m py_compile` on changed Python files -> OK
- `bash -n` on changed shell wrappers -> OK
- All `tools/test_*.py` previously passing remain unchanged.

Remaining blockers / not verified:
- GitHub CI artifact download still requires authentication (run 45057955030).
- `smth-home` supervision/restart policy in `services.json` left unchanged (optional behaviour change; needs live measurement).
- Native C `smth-moded.c` unchanged; coordination is handled by the `smth-mode` lock.
- No live GTK/Wayland device test performed in this workspace; layer-shell crash root cause is suspected (missing preload/compositor readiness) and now guarded + logged, not yet confirmed.
- ARM64 runtime behaviour still unverified.
- RAM measurements remain unstarted.

## 9. Phase C.0 artifact recovery (2026-11-24)

Full report: `docs/audit/phase-c0-artifact-inspection.md`.

Verified:
- Baseline commit `a8fe19c`, clean tree; Phase A/B reports re-read.
- `gh` 2.45.0 is installed but **not authenticated**; no `GH_TOKEN`/
  `GITHUB_TOKEN`, no `~/.config/gh`, no git credential helper. Anonymous
  artifact-zip requests return HTTP 401 for artifact IDs 14768511672,
  14768572136 and 14768343216.
- Run `45057955030` (commit `bf11090`) is a successful `push` build. Four
  non-expired artifacts: `boot-log-arm64` (14768572136, 3,741 B, expires
  2026-11-29), `boot-log-amd64` (14768511672, 3,346 B, expires 2026-11-29),
  `smth-os-amd64` (14768343216, 893,341,837 B, expires 2026-12-06),
  `smth-os-arm64` (14767998816, 626,513,976 B, expires 2026-12-06).
- The boot probe (`usr/local/bin/smth-bootcheck`) records presence only:
  `pgrep -x`/`pgrep -f` booleans, sockets and unit states, plus a
  `journalctl -b -p err` dump **only on failure**. `smth-bootcheck` is echoed to
  the serial console; the GUI session runs on tty1, so `home.py`/`notifd.py`
  stderr is not in a passing serial log.

Not done:
- No artifact was downloaded; **no checksums computed** and no ISO architecture
  verification.
- No boot log was inspected, so nothing in Phase B.5 is runtime-verified.

Consequence: even with authentication, the surviving artifacts can confirm only
session readiness and coarse process presence — not Waybar instance count,
`smth-home` crash/restart history, or layer-shell errors. Those need a boot-check
change or a live session capture.
