# Rust-first architecture and migration roadmap

Status: **core implemented and unit/integration tested**; shell integration is
partial by design. This document states what is Rust, what is not, and why.

## Principle

Rust replaces logic that is **stateful, safety-relevant or shared between
platforms**. The Linux kernel, drivers, bootloader, live-boot, systemd, labwc,
Waybar and the GTK toolkit stay exactly where they are: replacing proven
infrastructure would add risk without a user-visible gain.

Nothing was rewritten "because Rust". The Python GTK apps remain Python where
they are thin presentations over GTK, because a GTK4 + libadwaita app in Rust
requires gtk4-rs plus a rewritten widget tree for zero behavioural gain at this
stage. What moved into Rust is the part that was previously *missing or wrong*:
geometry, the AHIAN timeline, the service supervisor, file operations, settings
and the IPC contract.

## Crate map (`core/`)

```
core/
├── crates/smth-core        platform-independent logic (no OS calls)
│   ├── palette.rs          four-colour contract, contrast rule, token generation
│   ├── layout.rs           cascade, edge snap, n-way split, off-screen clamping
│   ├── ahian.rs            AHIAN script: errors, dialog storm, blue screen, countdown
│   ├── ipc.rs              versioned line-JSON protocol, service/layout enums
│   ├── fsops.rs            safe joins, collision-free copy/move/rename, trash metadata
│   ├── settings.rs         typed settings, atomic writes, schema handling
│   └── media.rs            dynamic-island pill priority (media/notification/countdown)
├── crates/smthd            supervisor + Unix-socket daemon (bin) and client (bin)
└── crates/smth-ahian       prints the AHIAN plan as JSON for the GTK front end
```

Dependencies: `serde` + `serde_json` only. Deliberately no async runtime, no
GUI toolkit and no `rand`:

* **Tokio / async** — `smthd` handles short request/response messages and one
  timer. A thread per connection and a 250 ms supervisor tick is simpler, has no
  runtime dependency and keeps the ISO payload tiny. Async becomes justified when
  file-copy progress streaming and DBus integration land.
* **Slint / iced** — would mean rewriting the GTK apps and losing libadwaita
  integration, icon themes and accessibility. The shell remains GTK4 + Waybar.
* **winit / Smithay / wlroots bindings** — the compositor is labwc (wlroots).
  Writing a compositor is out of scope; window *geometry* logic is what SMTH
  actually owns, and that is now in `layout.rs`.
* **wayland-client** — not needed yet: the shell talks to labwc/Waybar, not to the
  protocol. `smthd` reports geometry and the shell applies it.

## Runtime story

```
labwc (compositor)
├── smthd            service supervisor + IPC (Unix socket, 0600, $XDG_RUNTIME_DIR)
│   ├── smth-notifd  restarted with exponential backoff on crash
│   └── smth-moded   layout watcher
├── smth-home        GTK background: wallpaper, dot clock, glance rings
├── waybar           taskbar, uses smth-glance and the palette tokens
└── smth-* apps      GTK4/libadwaita front ends
```

`smthctl-core` is the scriptable client:

```sh
smthctl-core ping
smthctl-core layout split 2 1 --screen 1920x1080   # → {"result":"rect", ...}
smthctl-core layout snap left
smthctl-core ahian 42 --screen 1280x720            # → full AHIAN plan
smthctl-core start notifd
```

`ahian` (the Python GTK front end) calls `smth-ahian plan` for its timeline and
falls back to an embedded copy when the binary is absent, so a broken install
degrades to the old behaviour instead of doing nothing.

## Platform sharing

The launchers do not link Rust (NDK/JNI and Windows toolchain work is not
justified for a settings-level shell), but they consume the same rules:

* palette values are generated from `tools/palette.json` and copied into the
  Kotlin constants and the Python theme constants;
* the AHIAN copy/timings are single-sourced in `smth-core::ahian` and exposed to
  every front end through JSON;
* layout constants (cascade step, split gap, minimum window size) live in
  `layout.rs`; the ISO applies them via `smthctl-core`, the launchers use their
  own equivalent responsive grids.

## What is still intentionally not Rust

| Component | Reason | Revisit when |
|---|---|---|
| GTK apps (`smth-files`, `smth-settings`, …) | thin libadwaita UIs; gtk4-rs rewrite has no behaviour gain now | file operations move behind `smthd` RPC (planned) |
| `notifd.py` | DBus notification server already works via PyGObject | a D-Bus crate is adopted and the notification centre is redesigned |
| `smthctl` (extension manager) | one-shot administrative Python; security-critical logic is `openssl`/mount, not Python | extension manifest v2 adds rollback/dependencies |
| `freezerd` | scaffold; no foreground-state source exists yet | `smthd` publishes foreground app state (next milestone) |
| labwc, Waybar, fuzzel, swaylock | proven upstream components | never, barring a hard blocker |

`freezerd` is explicitly **not enabled** in the image: it would loop forever doing
nothing.

## Roadmap

| Phase | Content | State |
|---|---|---|
| 1 | Audit + baseline (this repo, docs/audit) | **done** |
| 2 | Architecture + boundaries (this document, iso-budget) | **done** |
| 3 | Shared core: palette, layout, AHIAN, IPC, fsops, settings, media, supervisor | **done, tested** |
| 4 | Shell integration: supervisor in autostart, AHIAN front end, settings toggle, tokens/typography | **done, unverified on a booted image** |
| 5 | Apps: AHIAN, clock, Files error reporting, honest extension prompts | **partially done** |
| 6 | Launchers: dynamic Android app grid + real dock + bundled fonts; Windows protocol handlers/fallbacks/smoke test | **done in source, verified in CI only** |
| 7 | ISO: budget split, extension packaging, reproducible checks | **split done; ISO build blocked here** |
| 8 | QA: Rust tests, wiring, palette, CI gates | **done here; ISO/APK/EXE in CI** |
| 9 | Release: tag-gated workflow with checksums | **done; not yet run** |

## Next milestone (recommended order)

1. Move `smth-files` mutations behind `smthd` (`fsops` over IPC) so the app stops
   swallowing `OSError` and gains trash/undo semantics.
2. Add a `smthd` foreground-state publisher (labwc foreign-toplevel protocol) and
   only then wire `freezerd` to it.
3. Replace the flag-file AHIAN state with `settings.json` everywhere (the Rust
   store is ready; `home.py` and `notifd.py` still read the flag for
   compatibility).
4. Implement the PIN/pattern lock on top of PAM (`pamtester`-style helper) rather
   than inventing a password store.
