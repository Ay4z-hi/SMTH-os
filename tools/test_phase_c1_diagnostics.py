#!/usr/bin/env python3
"""Regression checks for the Phase C.1 boot diagnostics.

Static checks prove the capture is wired into the boot path; the functional
checks drive `smth-diag` against stub `pgrep`/`journalctl`/`systemctl` so the
counting, the missing-process path and the stderr tee are exercised without a
running desktop.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
INC = ROOT / "config/includes.chroot_after_packages"
DIAG = INC / "usr/local/bin/smth-diag"
BOOTCHECK = INC / "usr/local/bin/smth-bootcheck"
SESSION = INC / "usr/local/bin/smth-session"

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
    return cond


def read(p):
    return pathlib.Path(p).read_text(encoding="utf-8")


# --- static checks ---------------------------------------------------------

def test_diag_is_executable_shell():
    check(DIAG.exists(), "smth-diag must exist in usr/local/bin")
    check(os.access(DIAG, os.X_OK), "smth-diag must be executable")


def test_bootcheck_takes_snapshots():
    text = read(BOOTCHECK)
    check("smth-diag snapshot --label ready" in text, "bootcheck must snapshot at readiness")
    check("smth-diag snapshot --label settle" in text, "bootcheck must snapshot after the settle")
    check("smth-diag stderr" in text, "bootcheck must summarise captured session stderr")
    check("SMTH_DIAG_SETTLE" in text, "the settle window must be overridable")
    # The original readiness checks must survive: diagnostics are additive.
    for marker in ('say "OK ', 'say "FAIL ', "process $proc=yes", "socket wayland"):
        check(marker in text, f"bootcheck lost its original check: {marker!r}")


def test_session_captures_stderr():
    text = read(SESSION)
    check("2>>" in text, "smth-session must send the session stderr to a file")
    check("smth-session.log" in text, "smth-session must use the log smth-diag summarises")
    check("XDG_RUNTIME_DIR" in text, "smth-session must place the log in the user runtime dir")
    check("exec dbus-run-session -- labwc" in text, "smth-session must still exec the session")
    # A pipe to a helper would let a dead reader SIGPIPE the compositor.
    check("2> >(" not in text, "session stderr must not go through a pipe")
    # The fallback must start the session even when the log is unwritable.
    check(text.count("exec dbus-run-session -- labwc") == 2,
          "smth-session needs a no-logging fallback exec")


def test_diag_emits_required_fields():
    text = read(DIAG)
    required = [
        "proc waybar.count=",
        "duplicate=",
        "proc smth-home.count=",
        "proc smth-notifd.count=",
        "proc smth-moded.count=",
        "state=absent",
        "session.ready=",
        "session.layer_shell.errors=",
        "session.gtk.errors=",
        "session.tracebacks=",
        "kernel.segfaults=",
        "kernel.oom=",
        "journal.smth_restarts=",
        "units.failed=",
        "unit name=",
        "result=",
        "stderr summary path=",
    ]
    for field in required:
        check(field in text, f"smth-diag must emit {field}")


# --- functional checks -----------------------------------------------------

PGREP_STUB = """#!/bin/sh
# pgrep -xc NAME / pgrep -fc PATTERN: $2 is the key.
case "$2" in
    waybar) echo 2; exit 0 ;;
    labwc) echo 1; exit 0 ;;
    smthd) echo 1; exit 0 ;;
    smth-moded) echo 0; exit 1 ;;
    *notifd*) echo 0; exit 1 ;;
    *home*) echo 1; exit 0 ;;
    *) echo 0; exit 1 ;;
esac
"""

JOURNALCTL_STUB = """#!/bin/sh
case " $* " in
    *" -k "*)
        printf '%s\\n' 'kernel: segfault at 0 ip 00007f' \
                      'kernel: Out of memory: Killed process 42 (python3)'
        ;;
    *)
        printf '%s\\n' 'smthd: restarting notifd (attempt 1)'
        ;;
esac
"""

SYSTEMCTL_STUB = """#!/bin/sh
case "$1" in
    --failed) exit 0 ;;
    show) echo success ;;
    is-active) echo active ;;
    *) exit 0 ;;
esac
"""


def _write_stub(bindir, name, body):
    p = bindir / name
    p.write_text(body)
    p.chmod(0o755)


def _sandbox(tmp):
    bindir = tmp / "bin"
    bindir.mkdir()
    _write_stub(bindir, "pgrep", PGREP_STUB)
    _write_stub(bindir, "journalctl", JOURNALCTL_STUB)
    _write_stub(bindir, "systemctl", SYSTEMCTL_STUB)
    session_log = tmp / "session.log"
    session_log.write_text(
        "labwc: session started\n"
        "Gtk-WARNING: GtkWindow is not a layer surface\n"
        "Traceback (most recent call last):\n"
        "  File \"home.py\", line 1, in <module>\n"
        "ordinary noise line\n"
    )
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env.get('PATH', '')}"
    env["SMTH_DIAG_CONSOLE"] = str(tmp / "console.txt")
    env["SMTH_DIAG_LOG"] = str(tmp / "diag.log")
    env["SMTH_DIAG_SESSION_LOG"] = str(session_log)
    return env, session_log


def test_snapshot_counts_processes():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        env, _ = _sandbox(tmp)
        r = subprocess.run([str(DIAG), "snapshot", "--label", "test"],
                           env=env, capture_output=True, text=True)
        out = r.stdout
        check(r.returncode == 0, f"snapshot exited {r.returncode}: {r.stderr}")
        check("proc waybar.count=2 duplicate=yes" in out,
              f"snapshot must count duplicate Waybar instances: {out!r}")
        check("proc smth-home.count=1" in out, "snapshot must count smth-home")
        check("proc smth-notifd.count=0" in out, "snapshot must report a missing smth-notifd as 0")
        check("proc smth-moded.count=0 state=absent" in out, "snapshot must report smth-moded state")
        check("session.ready=yes" in out, "snapshot must report readiness")
        check("label=test" in out, f"snapshot must carry its label: {out!r}")
        check("label=--label" not in out, "snapshot must consume --label, not use it as the label")


def test_snapshot_reports_crashes_and_units():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        env, _ = _sandbox(tmp)
        r = subprocess.run([str(DIAG), "snapshot"], env=env, capture_output=True, text=True)
        out = r.stdout
        check("kernel.segfaults=1" in out, f"snapshot must count kernel segfaults: {out!r}")
        check("kernel.oom=1" in out, "snapshot must count OOM kills")
        check("journal.smth_restarts=1" in out, "snapshot must report helper restarts")
        check("units.failed=0" in out, "snapshot must report failed units")
        check("session.layer_shell.errors=1" in out,
              "snapshot must count layer-shell errors from the session log")
        check("session.tracebacks=1" in out, "snapshot must count Python tracebacks")


def test_snapshot_tolerates_missing_console_and_log():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        env, _ = _sandbox(tmp)
        # A read-only/absent log directory must not break the snapshot.
        env["SMTH_DIAG_LOG"] = str(tmp / "missing-dir" / "nested" / "diag.log")
        env["SMTH_DIAG_CONSOLE"] = str(tmp / "missing-dir" / "console.txt")
        r = subprocess.run([str(DIAG), "snapshot"], env=env, capture_output=True, text=True)
        check(r.returncode == 0, f"snapshot must survive unwritable sinks: {r.stderr}")
        check("proc waybar.count=2" in r.stdout, "snapshot output must still reach stdout")


def test_stderr_summary_without_session_log():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        env, _ = _sandbox(tmp)
        env["SMTH_DIAG_SESSION_LOG"] = str(tmp / "does-not-exist.log")
        r = subprocess.run([str(DIAG), "stderr", "--tail", "5"],
                           env=env, capture_output=True, text=True)
        check(r.returncode == 0, f"stderr summary must not fail on a missing log: {r.stderr}")
        check("stderr unavailable" in r.stdout, "stderr summary must report a missing log")
        check("stderr summary path=" in r.stdout, "stderr summary must name the path it looked at")


def test_stderr_summary_lists_interesting_lines():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        env, _ = _sandbox(tmp)
        r = subprocess.run([str(DIAG), "stderr", "--tail", "5"],
                           env=env, capture_output=True, text=True)
        check("stderr line=Gtk-WARNING: GtkWindow is not a layer surface" in r.stdout,
              "stderr summary must surface layer-shell errors")
        check("ordinary noise line" not in r.stdout,
              "stderr summary must not echo unrelated noise")


def test_session_and_diag_agree_on_log_path():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        env, _ = _sandbox(tmp)
        env.pop("SMTH_DIAG_SESSION_LOG", None)
        env["XDG_RUNTIME_DIR"] = str(tmp)
        r = subprocess.run([str(DIAG), "stderr", "--tail", "1"],
                           env=env, capture_output=True, text=True)
        check("stderr summary path=" in r.stdout, f"stderr must report its path: {r.stdout!r}")
        check("smth-session.log" in r.stdout,
              "smth-diag must default to the log smth-session writes")


def test_snapshot_truncates_long_lines():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        env, session_log = _sandbox(tmp)
        session_log.write_text("Gtk-ERROR: " + "x" * 2000 + "\n")
        r = subprocess.run([str(DIAG), "stderr", "--tail", "5"],
                           env=env, capture_output=True, text=True)
        lines = [l for l in r.stdout.splitlines() if l.startswith("SMTH_DIAG: stderr line=")]
        check(len(lines) == 1, f"the long line must be summarised: {r.stdout!r}")
        check(all(len(l) <= 330 for l in lines),
              "summarised session lines must be truncated to stay log-safe")


def main():
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
        except Exception as exc:
            failures.append(f"{name}: raised {exc!r}")
            print(f"FAIL {name}: {exc}")
        else:
            print(f"ok   {name}")
    if failures:
        print(f"FAIL phase c1 diagnostics: {len(failures)} problem(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS phase c1 diagnostics")
    return 0


if __name__ == "__main__":
    sys.exit(main())
