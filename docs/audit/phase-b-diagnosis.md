# SMTH OS — Phase B diagnosis report

Date: 2026-11-24  
Repository: Ay4z-hi/SMTH-os  
Branch: freebuff/c4825a929e7ec0611cffd1b8  
Current commit: bf11090 ("Add a bootable RAM audit harness for the live image")  
Phase A progress commit: 3232db7

Scope: diagnosis only. No source code, ISO, or VM changes were made in this
phase. No QEMU matrix was run.

## 1. Summary of confirmed causes

### 1.1 Duplicate Waybar startup (confirmed)

Two independent boot paths both invoke `smth-mode auto` at session start, and
`smth-mode` is not safe to run concurrently.

Evidence:

- `config/includes.chroot_after_packages/etc/skel/.config/labwc/autostart`:
  - line `smth-mode auto >/dev/null 2>&1 &` starts one instance in the
    background.
  - lines `( smthd --config /etc/smth/services.json ... || { smth-notifd & smth-moded & } ) ... &`
    start `smthd`, which supervises `notifd` and `moded`.
- `native/smth-moded.c`, `main()`: calls `run_layout()` once before entering the
  uevent loop. `run_layout()` forks and execs `/usr/local/bin/smth-mode auto`.
- `config/includes.chroot_after_packages/usr/local/bin/smth-mode`:
  - guard: `[ "$(cat "$D/.current" ...)" = "$want" ] && exit 0`
  - then: `echo "$want" > "$D/.current"`
  - then: `pkill -x waybar; setsid waybar -c ... &`

The guard is a plain read/compare with no lock. At first boot both invocations
read a missing/empty `.current`, both pass the guard, both write `.current`, and
both execute `pkill -x waybar` followed by `setsid waybar ...`. The result is a
Waybar start race: two starts, a kill of a just-started instance, or a
temporarily absent taskbar. This is the exact duplicate-process path named in
the Phase A report.

### 1.2 `swaybg` fallback is intentional, not a separate feature (confirmed)

Evidence:

- `config/.../etc/skel/.config/labwc/autostart`:
  `( smth-home || swaybg -m fill -i /usr/share/backgrounds/smth/wallpaper.png ) ... &`

`swaybg` only runs when `smth-home` exits non-zero. Any observation of
`swaybg` as the wallpaper therefore means `smth-home` crashed or exited. The
fallback itself is correct; the problem is the `smth-home` failure that
triggers it.

### 1.3 `smth-home` and `smth-notifd` are unsupervised (confirmed)

Evidence:

- `config/.../etc/smth/services.json` supervises only `notifd` and `moded`.
- `smth-home` is launched directly from autostart with no supervisor and no
  restart. A crash leaves the desktop without its background/helper and relies on
  the `swaybg` fallback; nothing restarts `smth-home`.

### 1.4 Layer-shell use is unconditional and unguarded in the Python helpers (confirmed)

Evidence:

- `config/.../usr/local/lib/smth/home.py`, `on_activate()`:
  ```
  LS.init_for_window(win); LS.set_namespace(win, "smth-home");
  LS.set_layer(win, LS.Layer.BACKGROUND)
  for e in (...): LS.set_anchor(win, e, True)
  LS.set_exclusive_zone(win, -1); LS.set_keyboard_mode(win, LS.KeyboardMode.NONE)
  ```
  with no error handling around any of these calls.
- `config/.../usr/local/lib/smth/notifd.py`, `do_activate()`:
  ```
  LS.init_for_window(self.toast_win); ...
  LS.init_for_window(self.center); ...
  ```
  likewise unguarded.
- By contrast, `startup.py` and `ahian_startup.py` wrap the same block in
  `try/except` and fall back to `win.fullscreen()`. `home.py` and `notifd.py`
  do not, so a layer-shell failure there propagates as an unhandled exception
  (and, depending on the binding, can emit "GtkWindow is not a layer surface"
  from libgtk4-layer-shell before raising).

The wrappers in `usr/local/bin/smth-home` and `smth-notifd` set
`LD_PRELOAD` to `libgtk4-layer-shell.so` only if `ldconfig -p` finds it:
```
lib="$(ldconfig -p ... | awk '/libgtk4-layer-shell\.so /{print $NF; exit}')"
[ -n "$lib" ] && export LD_PRELOAD="$lib"
```
If that lookup fails at runtime, the GI `Gtk4LayerShell` binding still loads but
the underlying layer surface is never created, which is the documented trigger
for "GtkWindow is not a layer surface".

### 1.5 Application launch sites swallow or omit errors (confirmed)

Evidence:

- `config/.../usr/local/lib/smth/home.py`, `icon_button()`:
  `b.connect("clicked", lambda *_: info.launch([], None))` with no exception
  handling.
- `config/.../usr/local/lib/smth/launcher.py`, `launch()`:
  ```
  try: info.launch([], None)
  except GLib.Error: pass
  ```
  Any launch failure is silently discarded and the launcher then quits, which can
  look like an application disappearing immediately after launch.

## 2. Suspected causes (not yet confirmed)

1. **`smth-home` segmentation fault.** Suspected triggers, in priority order:
   - GTK4 layer-shell initialisation failure when `LD_PRELOAD` is not set or the
     compositor is not ready, followed by unguarded `LS.*` calls (section 1.4).
   - Unhandled exception in `Stats._raw()` / `Stats.mem()` if `/proc/meminfo`
     lacks `MemAvailable` (not expected on Trixie, but unguarded).
   - OOM kill of the largest session process under low memory; `smth-home` is
     estimated at 90-150 MiB and is the largest Python/GTK4 consumer. This is
     environmental and cannot be confirmed from the repository alone.
   - Signal/timer interaction: `GLib.unix_signal_add(SIGUSR1, apply)` runs
     `apply()` which mutates GTK state and timers; a signal arriving during a
     Cairo draw is not excluded by the code.

2. **"GtkWindow is not a layer surface".** Suspected to be the libgtk4-layer-shell
   message emitted when `LS.init_for_window()` did not actually create a layer
   surface (missing preload or unsupported/unready compositor) and a later
   `LS.set_*` call is made. All call sites in `home.py` and `notifd.py` are
   unguarded, so this is consistent with section 1.4.

3. **Applications disappearing after launch.** Suspected causes:
   - Launch failures swallowed by `launcher.py` (section 1.5) and unhandled in
     `home.py`.
   - `Gio.DesktopAppInfo.launch([], None)` with no `GAppLaunchContext`; apps
     that need a startup notification or working directory may fail to map.
   - Memory pressure (same as suspected cause 1).
   - Waybar `wlr/taskbar` tracking issues if the app's window `app_id` does not
     match the `.desktop` entry. Not verified.

4. **ARM64 runtime behaviour.** The boot log evidence for ARM64 is incomplete
   (docs/boot/verification.md: ARM64 has not completed `SMTH_BOOT: OK` since
   `b70bc09`). The native C modules build on the ARM runner but their runtime
   (netlink uevent socket, layer shell) is not exercised by tests. Suspected
   only.

5. **Native-C ISO measurements.** No native-C ISO RAM data exists in this
   workspace; the successful CI run's artifacts are not locally available
   (section 3).

## 3. Artifact retrieval status

GitHub Actions run `45057955030` (commit bf11090) has four non-expired
artifacts: `smth-os-amd64`, `smth-os-arm64`, `boot-log-amd64`,
`boot-log-arm64`.

- The artifact *list* is readable without authentication:
  `GET /repos/Ay4z-hi/SMTH-os/actions/runs/45057955030/artifacts` returns 200.
- The artifact *download* endpoints return 401 ("Requires authentication"):
  `GET /repos/.../actions/artifacts/<id>/zip`.
- Local `gh` is not authenticated.

Safe retrieval options (no secret in repository or chat):

1. User authenticates the local `gh` CLI with a read-only token scoped to the
   repository, then `gh run download 45057955030`. The token must be supplied
   through the user's own secret store, never pasted into chat or committed.
2. Add a CI step that attaches the small boot logs to the GitHub release assets
   (the `release` job already publishes ISOs) or publishes them to a public URL,
   then rerun the build. This is a workflow-only change but does require a CI
   run and user authorisation to push.
3. Re-run the build locally only if a root-capable, native-arch environment is
   available; this is the heaviest option and is not recommended for diagnosis.

The older `latest-os` release and its boot logs must not be used as a substitute:
that release predates the native C commits (3ed829d, 7dd4a14) and contains no
`SMTH_AUDIT` markers.

## 4. Evidence index (source and logs)

Source:
- `config/.../etc/skel/.config/labwc/autostart` — duplicate `smth-mode auto`,
  `smth-home || swaybg` fallback, unsupervised `smth-home`.
- `config/.../etc/smth/services.json` — only `notifd` and `moded` supervised.
- `native/smth-moded.c` — `run_layout()` calls `smth-mode auto` at startup.
- `config/.../usr/local/bin/smth-mode` — racy `.current` guard, `pkill -x waybar`,
  `setsid waybar`.
- `config/.../usr/local/lib/smth/home.py` — unguarded layer-shell calls,
  unsupervised, unhandled launch clicks.
- `config/.../usr/local/lib/smth/notifd.py` — unguarded layer-shell calls.
- `config/.../usr/local/lib/smth/launcher.py` — `launch()` swallows `GLib.Error`.
- `config/.../usr/local/bin/smth-home`, `smth-notifd` — conditional `LD_PRELOAD`.
- `docs/boot/verification.md` — ARM64 not verified since `b70bc09`.
- `docs/performance/ram-optimization.md` — `smth-home` estimated 90-150 MiB,
  ranked largest idle-RAM lever.

Logs:
- `/tmp/auditlogs/qemu-amd64.log`, `/tmp/auditlogs/qemu-arm64.log` — old
  release boot logs; both reach `SMTH_BOOT: OK` for amd64, no
  `SMTH_AUDIT` markers, no "GtkWindow is not a layer surface", no segfault.
  Not a native-C baseline.
- CI artifact boot logs for run `45057955030` not downloaded (auth required).

## 5. Exact files requiring changes (for the later repair phase)

Minimal set, in priority order:

1. `config/includes.chroot_after_packages/etc/skel/.config/labwc/autostart`
   - Remove the redundant `smth-mode auto` invocation, or make it conditional.
2. `config/includes.chroot_after_packages/usr/local/bin/smth-mode`
   - Add an atomic lock (`flock`) around the whole start/restart block and make
     the `.current` update atomic.
3. `native/smth-moded.c` (`run_layout` / startup)
   - Coordinate with autostart so only one path runs `smth-mode auto` at boot,
     or add the same lock.
4. `config/includes.chroot_after_packages/usr/local/lib/smth/home.py`
   - Wrap layer-shell initialisation in `try/except` with a safe fallback, like
     `startup.py`, and log the failure.
   - Handle exceptions from `info.launch`.
   - Guard `Stats._raw()` / `Stats.mem()`.
5. `config/includes.chroot_after_packages/usr/local/lib/smth/notifd.py`
   - Wrap layer-shell initialisation in `try/except`.
6. `config/includes.chroot_after_packages/usr/local/lib/smth/launcher.py`
   - Surface launch failures instead of swallowing them.
7. `config/includes.chroot_after_packages/etc/smth/services.json` (optional)
   - Only if a restart policy for `smth-home` is desired; this is a behaviour
     change and should be measured first.
8. `.github/workflows/build.yml` (optional, for artifact access)
   - Attach boot logs to release assets or expose them publicly.

## 6. Minimal repair plan (not executed)

1. Reproduce/obtain the native-C boot logs using one of the safe methods in
   section 3; confirm which of suspected causes 1-3 actually occur.
2. Fix the duplicate Waybar race first (items 1-3 above); this is the smallest,
   lowest-risk change and directly addresses a confirmed cause.
3. Add guarded layer-shell initialisation and error logging to `home.py` and
   `notifd.py` (items 4-5), preserving the existing fallback pattern.
4. Re-run `python3 tools/check_wiring.py` and the native tests
   (`make -C native check`, `python3 tools/test_native.py`) after edits.
5. Only after a reliable baseline exists, run the live RAM audit matrix
   (`tools/ram_audit_qemu.sh` / `tools/ram_audit_guest.sh`) on the native-C
   ISO and record `docs/performance/` baselines.
6. Defer any C/Assembly rewrite of `smth-home` or `smth-notifd` until the
   measurements above exist; the current evidence does not justify it.

## 7. Phase B boundary

No QEMU VMs were launched, no ISOs were rebuilt or downloaded, no native code
was modified, and no measurements were claimed. The native-C ISO and its boot
logs remain unrecovered in this workspace pending GitHub authentication.
