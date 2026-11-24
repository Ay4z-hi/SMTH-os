# SMTH OS — Phase C.0 artifact recovery and boot-log inspection

Date: 2026-11-24
Repository: Ay4z-hi/SMTH-os
Branch: freebuff/c4825a929e7ec0611cffd1b8
Current commit: a8fe19c ("Phase B.5: minimal desktop repairs (Waybar race, guarded layer-shell, error reporting)")
Phase A commit: 3232db7 · Phase B commit: c04e8ec

Scope: artifact recovery and boot-log inspection only. No application code was
modified, no QEMU was started, and the RAM matrix was not started.

**Result in one line: artifact download is blocked by missing GitHub
authentication, so the native-C boot logs were not inspected. The steps to
unblock are in section 8, and the inspection can then be repeated verbatim.**

## 1. Repository state (verified)

`git log --oneline` at the start of this phase:

```
a8fe19c Phase B.5: minimal desktop repairs (Waybar race, guarded layer-shell, error reporting)
c04e8ec Document Phase B diagnosis findings
3232db7 Document Phase A RAM audit recovery findings
bf11090 Add a bootable RAM audit harness for the live image
7dd4a14 Skip shell parity where the image lacks the shell's own tools
3ed829d Move the taskbar sampler and layout watcher into native C
```

Working tree was clean (`git status --short` empty). The expected baseline
commit a8fe19c is present, and the Phase A/B reports were re-read:
`docs/audit/ram-audit-progress.md`, `docs/audit/phase-b-diagnosis.md`.

## 2. Authentication check (verified — unavailable)

| Check | Result |
| --- | --- |
| `gh --version` | `gh version 2.45.0 (2025-07-18 Ubuntu 2.45.0-1ubuntu0.3)` — installed |
| `gh auth status` | `You are not logged into any GitHub hosts. To log in, run: gh auth login` (exit 1) |
| `GH_TOKEN` / `GITHUB_TOKEN` in environment | not set |
| `~/.config/gh` | does not exist |
| `git config --get-all credential.helper` | empty |
| Anonymous artifact zip, artifact 14768511672 (`boot-log-amd64`) | HTTP 401 |
| Anonymous artifact zip, artifact 14768572136 (`boot-log-arm64`) | HTTP 401 |
| Anonymous artifact zip, artifact 14768343216 (`smth-os-amd64`) | HTTP 401 |

The artifact *list* endpoint is public and works; the *download* endpoints
require authentication. No bypass was attempted, and no older release ISO was
substituted, per the phase constraints.

## 3. Artifact inventory for run 45057955030 (verified via public API)

Run metadata: `Build SMTH OS`, `head_sha` `bf1109036a86ca19ce302205407fa996dd00c103`,
branch `main`, event `push`, status `completed`, conclusion `success`,
created 2026-11-22T18:57:13Z, updated 2026-11-22T19:11:30Z.

| Artifact ID | Name | Size (bytes) | Expires | Status |
| --- | --- | --- | --- | --- |
| 14768572136 | `boot-log-arm64` | 3,741 | 2026-11-29T19:10:16Z | not expired |
| 14768511672 | `boot-log-amd64` | 3,346 | 2026-11-29T19:06:56Z | not expired |
| 14768343216 | `smth-os-amd64` | 893,341,837 | 2026-12-06T19:04:41Z | not expired |
| 14767998816 | `smth-os-arm64` | 626,513,976 | 2026-12-06T19:02:26Z | not expired |

Time pressure: the two boot logs expire on **2026-11-29**, five days from this
report. Once they expire the boot evidence for commit bf11090 is gone unless the
build is re-run; the ISOs have until 2026-12-06.

## 4. Download and verification status (NOT done)

- Artifacts downloaded: **none**.
- SHA256 checksums: **not computed** — no bytes were retrieved.
- Architecture verification of the ISOs (`file`, El Torito inspection):
  **not performed**.
- The architecture labels above come only from the artifact names and the CI
  matrix entries (`amd64` on `ubuntu-latest`, `arm64` on `ubuntu-24.04-arm`).
  They are consistent with the expected builds but are **not** independently
  verified, because verification requires the downloaded files.

Any statement in a later phase that "the ISOs are amd64/arm64" must therefore
rest on an actual `tools/verify_bootloader.sh` run against the downloaded ISO.

## 5. What the boot logs can and cannot prove (established from source)

This section is derived from the repository, not from the un-downloaded logs, so
it is confirmed. It matters because it determines what Phase C.1 can conclude
even once the artifacts are in hand.

The serial log is produced by `tools/qemu_boot_test.sh`:

- QEMU is started with `-display none -serial "file:$LOG"`, so the log is the
  raw serial console of the guest (ttyS0 on amd64, ttyAMA0 on arm64).
- The CI job sets `SMTH_QEMU_LOG=${workspace}/qemu-<arch>.log` and uploads that
  exact file as `boot-log-<arch>` (`.github/workflows/build.yml`, "Keep the
  serial boot log", `if: always()`).
- The desktop is started from tty1 autologin (`.bash_profile` →
  `smth-session` → `dbus-run-session -- labwc`), which is **not** the serial
  console.

The only structured content comes from
`config/.../usr/local/bin/smth-bootcheck`, which prints `SMTH_BOOT:` lines to
stdout and to `/dev/console`. It reports presence only:

- `process labwc=yes|no`, `process waybar=yes|no`, `process smthd=yes|no`
  — `pgrep -x`, i.e. *existence*, never a count.
- `process /usr/local/lib/smth/home.py=yes|no`,
  `process /usr/local/lib/smth/notifd.py=yes|no` — `pgrep -f`, again a single
  instant of existence.
- `socket wayland=yes|no path=...`, `socket smthd=yes|no path=...`
- `unit smth-extensions.service=<state>`, `unit nftables.service=<state>`,
  plus advisory `bluetooth`/`NetworkManager` states and `failed-units=<n>`.
- `OK desktop session is up arch=<arch>` on success.
- On failure only, it also dumps `journalctl -b -p err --no-pager -n 25|40`.

Mapping to the five inspection items requested for this phase:

| Requested inspection | Represented in the artifact? | Notes |
| --- | --- | --- |
| `smth-home` startup | Partly | `process .../home.py=yes` proves it was alive at the check instant. |
| `smth-home` crashes / restarts | **No** | No PID count, no restart counter, no crash marker; a crash before the check only shows as `=no` or the `swaybg` fallback, which is invisible on serial. |
| Waybar process count / duplicate startup | **No** | `pgrep -x waybar` is a boolean. A duplicate Waybar is indistinguishable from a healthy single instance. |
| `smth-moded` / native-C daemon startup | Partly | Only `process smthd=yes`; the log does not separate `smthd`, `smth-moded` or the native C samplers. |
| GTK / layer-shell errors | **No (unreliable)** | `home.py`/`notifd.py` stderr goes to the tty1 VT, not ttyS0. It reaches the log only if journald happened to capture the session stream and the check failed, which is not the passing-run path. |
| Desktop-session readiness | Yes | `SMTH_BOOT: OK` plus wayland/smthd socket checks is a genuine readiness signal. |

Consequence for C.1: the surviving artifacts can confirm or refute **only**
desktop readiness and coarse process presence. They **cannot** confirm the
duplicate-Waybar fix, the `smth-home` crash/restart behaviour, or the layer-shell
error path. Those need either a boot-check extension (a config script change,
out of scope for this phase) or an interactive session capture.

## 6. Comparison against Phase B diagnosis and Phase B.5 repairs

Confirmed in this phase (source and API evidence only):

1. Run 45057955030 built commit bf11090 successfully; four non-expired artifacts
   exist with the IDs and sizes in section 3.
2. The boot probe's evidence model is presence-only (section 5); this is a real
   limitation of the existing artifacts, independent of authentication.
3. The desktop session's GUI stderr is not routed to the serial console, so
   layer-shell messages are not part of a passing boot log.

Still unverified — unchanged by this phase:

| Phase B item | B.5 repair | Status after C.0 |
| --- | --- | --- |
| 1.1 duplicate Waybar race | `flock` + atomic `.current` in `smth-mode` | Repair is in source and covered by `tools/test_phase_b5_repairs.py`; **no runtime confirmation** exists, and the artifacts could not provide it even if downloaded. |
| 1.2 `swaybg` fallback means `smth-home` exited | unchanged (intentional) | Still an inference, not observed in a log. |
| 1.3 `smth-home` unsupervised | intentionally unchanged | Still true by design; needs a measurement decision before changing. |
| 1.4 unguarded layer-shell calls | now guarded and logged | Guarding is in source; **the "GtkWindow is not a layer surface" trigger is still suspected**, and its stderr is not captured by these artifacts. |
| 1.5 swallowed launch errors | now reported | Source-level only; not exercised at runtime. |
| Suspected `smth-home` segfault | not addressed | Unconfirmed. A segfault would appear in `journalctl -p err` only in the FAIL dump path. |
| ARM64 runtime | not addressed | Boot log for arm64 not inspected; `docs/boot/verification.md` still records no `SMTH_BOOT: OK` since `b70bc09`. |

No claim in this phase should be read as "the B.5 repairs are verified". They
remain source-level changes with unit/static coverage only.

## 7. Blockers

1. **GitHub authentication is absent** — the only hard blocker for section 4 and
   for the log inspection that depends on it.
2. **Boot-log retention** — both boot logs expire 2026-11-29; after that the
   evidence for bf11090 requires a rebuild.
3. **Artifact evidence gap** — even with authentication, items 2, 3 and 5 of the
   requested inspection (Waybar count, `smth-home` restarts, layer-shell errors)
   are not recorded by the current boot probe. Resolving them needs a boot-check
   change or a live session capture, which this phase is not authorised to make.
4. No live GTK/Wayland device session exists in this workspace, so runtime
   behaviour cannot be observed directly here.

## 8. Simplest exact steps to authenticate (for the user)

Run these on a machine that has a browser, then repeat Phase C.0. The token must
stay in the user's own credential store — never pasted into chat, committed, or
written into the repository.

Option A — device login (recommended, no token handling):

```sh
gh auth login --hostname github.com --git-protocol https --web
gh auth status
```

Choose the GitHub account that can read `Ay4z-hi/SMTH-os`. The default scopes
are sufficient for reading Actions artifacts.

Option B — fine-grained token with read-only access:

```sh
# Create a fine-grained PAT with: Repository access = Ay4z-hi/SMTH-os,
# Permissions = Actions: Read-only. Then:
read -rs GH_TOKEN && export GH_TOKEN      # paste at the prompt, not in chat
gh auth status
```

Then download and verify:

```sh
cd /workspace/chats/c4825a929e7ec0611cffd1b8   # or this chat's worktree
mkdir -p .audit-c0 && gh run download 45057955030 --dir .audit-c0
sha256sum .audit-c0/smth-os-amd64/*.iso .audit-c0/smth-os-arm64/*.iso \
          .audit-c0/boot-log-amd64/*.log .audit-c0/boot-log-arm64/*.log \
  | tee .audit-c0/SHA256SUMS
file .audit-c0/smth-os-amd64/*.iso .audit-c0/smth-os-arm64/*.iso
bash tools/verify_bootloader.sh .audit-c0/smth-os-amd64/*.iso amd64
bash tools/verify_bootloader.sh .audit-c0/smth-os-arm64/*.iso arm64
```

`.audit-c0/` must stay untracked (add it to `.gitignore` locally if needed); it
holds ~1.5 GB and does not belong in the repository or in a checkpoint.

## 9. Phase C.1 — precise next step

Phase C.1 is **boot-log inspection against the diagnostic checklist**, and it is
sequenced strictly after the download above. Concretely, once section 8 has
produced `.audit-c0/`:

1. Record the SHA256SUMS and `verify_bootloader.sh` results in the C.1 report
   before interpreting anything (architecture and integrity first).
2. Extract every `SMTH_BOOT:` line from both logs:
   `grep -n 'SMTH_BOOT' .audit-c0/boot-log-amd64/*.log .audit-c0/boot-log-arm64/*.log`
   and record the final marker per architecture (`OK` / `FAIL` / absent).
3. Record the presence fields verbatim (`process ...`, `socket ...`, `unit ...`,
   `failed-units=`), and the `journalctl -b -p err` dump if the run failed.
4. Search both logs for `GtkWindow is not a layer surface`, `Segmentation fault`,
   `segfault`, `swaybg`, `waybar`, `smth-moded`, `OOM`/`Killed process`, and
   record hit counts — expecting zero hits for the GUI-stderr items per section
   5, which is itself a finding, not a clean bill of health.
5. Update `docs/audit/phase-c0-artifact-inspection.md` (or add
   `phase-c1-boot-log-inspection.md`) with confirmed vs suspected, and only then
   consider the RAM matrix.

If authentication is not provided, the honest state of the audit is: Phase A,
B and B.5 are documented and source-complete, the native-C ISO evidence remains
unrecovered, and no RAM measurement exists. The RAM matrix must not start until
either the artifacts land or the boot probe is extended to record per-process
counts and session stderr.
