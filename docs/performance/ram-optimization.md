# SMTH OS — native performance and RAM optimisation (November 2026)

Scope: reduce idle RAM and runtime overhead on the Linux ISO by moving
demonstrably hot, syscall-facing shell helpers to C, and to establish whether
Assembly is justified anywhere in the current process set.

Every number below is either **measured** (with the command shown) or marked
**modelled**. No modelled figure is presented as a result.

## 1. What this environment could and could not measure

| Capability | Available | Consequence |
|---|---|---|
| gcc, make, strace, udevadm, Python 3.12 | yes | C helpers built, benched and tested for real |
| x86-64 Linux 6.1, 8 vCPU, 16 GiB | yes | all measurements below are from this host |
| GTK4 / PyGObject / Wayland compositor | **no** | `smth-home` and `smth-notifd` resident cost **not measured here** |
| cargo / rustc | **no** | Rust core not rebuilt here; CI builds it (`ci.yml` → `core`) |
| root / apt / docker / QEMU | **no** | no ISO build or boot in this environment |
| aarch64 toolchain or emulator | **no** | ARM64 build verified only in CI (native `ubuntu-24.04-arm` runner) |

So: the process-spawn chain, the layout watcher, the C binaries and the
Assembly question are measured. The GTK4/Python and compositor residency is
**not**, and is not claimed. `tools/measure_ram.py` (section 6) is the tool that
turns it into measured numbers on a booted image.

## 2. Audit: what the session actually runs

Persistent processes started by the live session
(`etc/skel/.config/labwc/autostart`, `etc/smth/services.json`):

| Process | Language / toolkit | Role | RAM status |
|---|---|---|---|
| `labwc` | C (wlroots) | compositor | not measured (no display) |
| `waybar` | C++ (GTK3) | taskbar | not measured |
| `smthd` | Rust | supervisor + IPC socket | not measured (no cargo); 250 ms tick |
| `smth-home` → `python3 home.py` | Python + GTK4 + Cairo | wallpaper, clock, glance rings | not measured (no GTK4) |
| `smth-notifd` → `python3 notifd.py` | Python + GTK4 + D-Bus | notification server, alert watchers | not measured (no GTK4) |
| `smth-moded` | **was** bash + udevadm + subshell, **now** C | display hotplug → `smth-mode auto` | **measured, section 4** |
| `swayidle` | C | idle/lock | not measured |
| `smth-glance` (Waybar `custom/*`) | **was** bash + awk + coreutils, **now** C | taskbar CPU/RAM/disk meters, every 3/5/60 s | **measured, section 4** |

Duplicated work found in the audit:

1. **Eight to nine `execve`s per taskbar poll.** `smth-glance cpu` alone spawned
   `bash`, `nproc`, `awk`, `nproc` plus five command-substitution subshells to
   read two numbers that come from `/proc/loadavg` and `sysconf()`.
2. **Three processes to watch one subsystem.** `smth-moded` was
   `bash` + `udevadm monitor` + a `while read` subshell, each holding its own
   libc, to run one command per DRM hotplug.
3. **Three independent `/proc` readers for the same data.** Waybar's meters,
   `home.py`'s glance rings and `notifd.py`'s battery poll each parse
   `/proc` separately in their own runtime. Two of the three are inside a GTK
   process, so the marginal cost there is small; the third was the spawn chain.
4. `freezerd` is still a scaffold and remains **not enabled** — a daemon doing
   nothing forever would be the worst possible RAM trade.

Not a problem, deliberately: `zram-tools` is installed and enabled. Compressed
swap raises the low-memory ceiling instead of lowering idle RSS, which is
exactly what the minimum-boot target needs.

## 3. Baseline (measured before any change)

Host: x86-64, Linux 6.1, 8 vCPU, 16 GiB, Python 3.12.
Command: `python3 tools/bench_native.py --runs 40` (one-shot figures through
`native/bench/one_shot`, a 16 KiB C parent, because a forked child inherits its
parent's high-water RSS — measuring from CPython reports ~11 MiB for a 1 MiB
binary).

| Command | wall | CPU | peak RSS | execve |
|---|---:|---:|---:|---:|
| `smth-glance cpu` (bash) | 11.21 ms | 11.39 ms | 3.5 MiB | 4 |
| `smth-glance mem` (bash) | 9.49 ms | 11.95 ms | 3.4 MiB | 3 |
| `smth-glance disk` (bash) | 8.10 ms | 11.94 ms | 3.4 MiB | 4 |
| `python3 -c pass` (floor) | 31.1 ms | 30.8 ms | 11.4 MiB | 1 |

| Layout watcher (resident, median of 3) | processes | PSS | RSS |
|---|---:|---:|---:|
| `bash` + `udevadm monitor` + `read` subshell | 4 | 3.1 MiB | 12.0 MiB |

With the shipped Waybar intervals (`cpu` 3 s, `mem` 5 s, `disk` 60 s), one
minute of idle taskbar polling was:

* CPU: 20 × 11.39 + 12 × 11.95 + 1 × 11.94 ≈ **383 ms per minute** of CPU
  (arithmetic from the measured medians, ≈0.64 % of one core), and
* **120 `execve` calls per minute**, transient peaks of ~3.5 MiB each.

## 4. What was rewritten in C, and what it measures now

Two modules, both in `native/`, both dependency-free (libc only), both built on
the target architecture by `scripts/build.sh`, so amd64 and arm64 images get
native binaries from their own runners.

### 4.1 `native/smth-glance.c` → `/usr/local/bin/smth-glance` (17,256 bytes)

Reads `/proc/loadavg`, `/proc/meminfo` and `statvfs("/")` directly, formats the
five-glyph dot meter with the same rule as before
(`n = (pct*5+50)/100`, `hot` above 85 %, `df`'s ceiling capacity formula), and
writes one Waybar JSON line with a single `write(2)`. **No heap allocation**:
three stack buffers and no stdio. Subcommands: `cpu`, `mem`, `disk`, `all`
(one snapshot for any future consumer), `fmt` (pure formatter, used by tests).

Verified byte-identical to the shell implementation on the same machine:

```
legacy: {"text":"SSD ●○○○○","tooltip":"24% of / used"}
native: {"text":"SSD ●○○○○","tooltip":"24% of / used"}
```

Measured after the change (`tools/bench_native.py`, 40 runs, medians):

| Command | wall | CPU | peak RSS | execve |
|---|---:|---:|---:|---:|
| `smth-glance cpu` C | **1.05 ms** (−90.6 %) | **0.88 ms** (−92.3 %) | **1.6 MiB** | **1** (−75 %) |
| `smth-glance mem` C | **1.08 ms** (−88.6 %) | **0.89 ms** (−92.5 %) | 1.6 MiB | 1 |
| `smth-glance disk` C | **0.95 ms** (−88.2 %) | **0.82 ms** (−93.1 %) | 1.6 MiB | 1 |

The one-shot RSS floor of the measuring launcher is 1.3 MiB, so 1.6 MiB is
essentially libc + binary; the process is at the floor, not "1.6 MiB of work".

Per minute of idle taskbar polling: **383 ms → 29 ms of CPU** (−92 %) and
**120 → 33 `execve`** (−73 %).

### 4.2 `native/smth-moded.c` → `/usr/local/bin/smth-moded` (17,104 bytes)

Subscribes to the kernel uevent netlink group directly (`NETLINK_KOBJECT_UEVENT`,
group 1), filters `SUBSYSTEM=drm`, debounces a burst of events into one
`smth-mode auto` (1 s settle, replacing the per-event `sleep 1`), and runs
`smth-mode auto` once at startup exactly like the script did. `SIGCHLD` is
ignored so `smth-mode` is fire-and-forget; a missing uevent socket logs once and
exits 0 rather than being restarted in a loop by `smthd`.

| Layout watcher | processes | PSS | RSS |
|---|---:|---:|---:|
| before | 4 | 3.1 MiB | 12.0 MiB |
| after | **1** | **0.2 MiB** | **1.3 MiB** |

Net idle saving: **3 fewer processes and ~10.7 MiB RSS / ~2.9 MiB PSS**.
Verified in this environment: the unprivileged netlink bind succeeds, the
daemon applies the layout once, idles with ≤4 CPU ticks per 0.8 s, and exits 0
on `SIGTERM`. A real DRM hotplug could not be injected (no `CAP_NET_ADMIN`, no
display), so the *event* path is exercised by unit-level filtering only — stated
as a limitation, not a result.

### 4.3 Packaging and interface preservation

* Same command names, same Waybar JSON contract, same `services.json` entries,
  same autostart lines — no desktop configuration changed.
* The superseded scripts are kept in `native/legacy/` for A/B measurement and
  manual rollback; they are no longer installed in the image.
* `tools/check_wiring.py` resolves the two names as build-produced binaries
  (`NATIVE_BINS`), the same way it already handled `RUST_BINS`.

## 5. Assembly: investigated and rejected, with numbers

Only one routine runs on every poll: the five-glyph meter (≈6 ns). A
hand-written AMD64 implementation (`native/bench/dots_asm_amd64.S`) was compared
with the compiler's output for 20 M calls in both orders
(`make -C native bench`):

```
dots_c   : 6.01 / 6.00 ns/call (C first / asm first)
dots_asm : 6.80 / 6.80 ns/call (C first / asm first)
average  : C 6.00 ns  asm 6.80 ns  delta +0.79 ns (+13.2%)
```

The compiler wins by 13 %, consistently. And the scale settles it: one
`smth-glance cpu` process costs **1,050,000 ns** end to end (exec, `/proc`,
format, write). A ±1 ns inner loop is 0.0001 % of that. **No Assembly ships.**

What Assembly would need to be justified here: a per-frame rasteriser for the
AHIAN dot field or the wallpaper, or a boot-stage routine on the critical path.
Neither exists as a measured hot spot in the current architecture — the AHIAN
scene is drawn in Python/Cairo at 30 fps only while AHIAN mode is on, and its
cost is dominated by Cairo calls, not by a loop C could beat. If such a renderer
is ever written in C, the first candidate is SIMD (SSE2/AVX2 on AMD64, NEON on
ARM64) for dot rasterisation, measured against `-O3 -ftree-vectorize`; it is
not justified today. ARM64 assembly was not built or run here (no aarch64
toolchain or emulator in this environment) — nothing ships, so there is no
untested arch-specific path.

## 6. The reproducible baseline: `tools/measure_ram.py`

The measurement that decides whether the RAM targets are met has to run on a
booted image. This tool does exactly that, needs no root and reads only
`/proc`:

```
python3 tools/measure_ram.py --seconds 30 --json baseline.json
python3 tools/measure_ram.py --compare baseline.json        # before/after deltas
python3 tools/measure_ram.py --markdown report.md
```

It reports, per watched process: RSS, **PSS** (shared library pages split
between their users, so the total is meaningful), private dirty+clean, swap,
threads, idle CPU over the window and process age (= time since session start,
the startup anchor). It also reports system used/available, idle/busy CPU, load
and uptime, plus session totals. When `smaps_rollup` is unreadable (another
user's process) it says so and falls back to RSS instead of mislabelling it.

Exercised in this environment (correct output, 3 watched system daemons, PSS
fallback flagged for other users' processes). **No SMTH desktop process exists
in this VM, so the on-image baseline is still outstanding** — that is the first
item in "remaining work", not a completed measurement.

## 7. RAM targets: what the architecture can and cannot reach

Stated honestly: the requested targets are **not verified** by this pass, and
two of them are only reachable by replacing the two GTK4/Python helpers, which
this pass deliberately did not touch.

| Component | Idle cost | Status |
|---|---:|---|
| kernel + initramfs + systemd/journald/udev | ~120–200 MiB | modelled — Debian live baseline |
| NetworkManager, bluetoothd, pipewire/wireplumber, dbus, udisks, PPD | ~60–90 MiB | modelled — distribution daemons, all features in use |
| `labwc` + wlroots + mesa (llvmpipe when no GPU) | ~60–150 MiB | modelled; llvmpipe dominates in VMs |
| `waybar` (GTK3) | ~40–70 MiB | modelled |
| `smth-home` (Python + GTK4 + Cairo + wallpaper) | ~90–150 MiB | modelled; **not measured** (no GTK4 here) |
| `smth-notifd` (Python + GTK4 + D-Bus) | ~80–120 MiB | modelled; shares GTK4 pages with `smth-home` |
| `smthd` (Rust) + `swayidle` | ~5 MiB | not measured (no cargo) |
| `smth-moded` (C, after this change) | **1.3 MiB** | measured |
| `smth-glance` (C, per poll) | ~1.6 MiB transient, 0.9 ms | measured |

Why 256–384 MiB minimum boot is a stretch: a GTK4 desktop session plus an
llvmpipe software GL stack in a VM does not fit in ~300 MiB regardless of
language choices; the toolkit mappings alone are the floor. 350–500 MiB is
plausible **if** the two Python/GTK4 helpers become one small C/Wayland client
and one C D-Bus daemon (item 9.1). 500–700 MiB full idle and 1 GB comfortable
are realistic today.

The honest ranking of RAM levers, largest first:

1. `smth-home` + `smth-notifd` GTK4/Python residency (largest, risky, visual).
2. llvmpipe/software GL in VMs (drop `libllvm19`, or prefer hardware GL) — size
   and RAM, not language.
3. Distribution daemons that are enabled but idle (bluetooth without an
   adapter, `power-profiles-daemon` on fixed hardware) — feature decisions.
4. This pass: process chain and watcher (done, measured).
5. Everything else is noise at MiB scale.

## 8. Build and test results (this environment)

| Check | Result |
|---|---|
| `make -C native clean check` (`-O2 -Wall -Wextra -Werror -pedantic`) | **pass** |
| `python3 tools/test_native.py` | **pass** — JSON contract, formatter rules (clamping, `hot` at >85 %, `df` ceiling), `/proc`/`statvfs`/`df` parity, parity with the bash implementation, usage errors, layout watcher (`--once`, residency, idle CPU, RSS, `SIGTERM`) |
| `python3 tools/bench_native.py --runs 40` | **pass**, numbers in §3/§4 |
| `make -C native bench` (Assembly A/B) | **pass**, numbers in §5 |
| `python3 tools/measure_ram.py --seconds 2` | **pass** (collector validated; no desktop in this VM) |
| `python3 tools/check_wiring.py` | **pass** — taskbar, autostart, keybinds, hooks still resolve |
| `bash -n scripts/build.sh`; `ci.yml` YAML parse | **pass** |
| Existing suites (`test_palette`, `test_startup`, `test_ahian_*`, `test_desktop_grid`, `test_icon_containers`, `test_orbit`) | **pass** (unchanged by this work) |
| ISO amd64/arm64, APK, EXE | **CI only** — `make -C native` + `tools/test_native.py` are now part of `scripts/build.sh` and of `ci.yml`'s `native` job |

Nothing in the launchers, the Rust core, the AHIAN flow, the icon geometry or
the visual identity was modified by this pass.

## 9. Remaining bottlenecks and recommended next steps

Ranked by expected RAM per unit of risk. Each is a separate change with its own
benchmark, as required.

1. **Replace `smth-home` with a C Wayland layer-shell client** (wallpaper,
   clock, glance rings) and `smth-notifd` with a C D-Bus daemon. Expected: the
   single largest idle-RAM reduction available (two GTK4 stacks down to two
   small clients); highest risk to the liquid-glass identity, so it must be done
   behind the existing visual contract and checked on a booted image. This is
   the only path to the 350–500 MiB idle target.
2. **Measure before touching anything else.** Run `tools/measure_ram.py` on the
   booted amd64 and arm64 images, commit the JSON baselines to
   `docs/performance/`, and let the ranking above be replaced by measured PSS.
3. **A single native sampler daemon** (`smth-glance all` already produces the
   snapshot) shared over `smthd`'s socket by Waybar, `home.py` and any future
   consumer, removing the three independent `/proc` readers. Only worth it once
   (1) lands and those readers are C; today it would add a resident process.
4. **`smth-mode`'s `timeout 3 hostnamectl chassis`** on the session-start path:
   a ~5-line C read of `/sys/class/dmi/id/chassis_type` removes a D-Bus round
   trip and a 3 s worst case from startup. Risk: layout selection must match
   systemd's mapping exactly, so it needs a table test per chassis type.
5. **Daemon diet as a product decision**, not a silent change: mask
   `bluetooth` when no adapter exists, skip `power-profiles-daemon` on fixed
   hardware, keep `zram` (it is the low-RAM safety net).
6. **Rust core**: unchanged, as required. Its supervisor tick is 250 ms and its
   cost is a `sleep`; there is no measured reason to touch it, and the RAM work
   above is 10–100× larger.

## 10. Reproduce everything in this document

```sh
make -C native clean check && python3 tools/test_native.py
python3 tools/bench_native.py --runs 40        # §3, §4
make -C native bench                           # §5
python3 tools/measure_ram.py --seconds 30 --json /tmp/baseline.json   # on the image
python3 tools/check_wiring.py
```
