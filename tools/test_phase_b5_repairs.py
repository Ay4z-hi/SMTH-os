#!/usr/bin/env python3
"""Regression checks for the Phase B.5 minimal desktop repairs."""
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
INC = ROOT / "config/includes.chroot_after_packages"
SMTH_MODE = INC / "usr/local/bin/smth-mode"
HOME_PY = INC / "usr/local/lib/smth/home.py"
NOTIFD_PY = INC / "usr/local/lib/smth/notifd.py"
LAUNCHER_PY = INC / "usr/local/lib/smth/launcher.py"
SMTH_HOME = INC / "usr/local/bin/smth-home"
SMTH_NOTIFD = INC / "usr/local/bin/smth-notifd"
CHECK_WIRING = ROOT / "tools/check_wiring.py"

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
    return cond


def read(p):
    return pathlib.Path(p).read_text(encoding="utf-8")


# --- source-level repair checks ---

def test_smth_mode_uses_flock():
    text = read(SMTH_MODE)
    check("flock" in text, "smth-mode must serialise with flock")
    check("exec 9>" in text, "smth-mode must hold a lock file descriptor")
    check(".current.tmp" in text, "smth-mode must write .current atomically")


def test_home_layer_shell_guarded():
    text = read(HOME_PY)
    # The LS block must be inside a try/except.
    idx = text.find("LS.init_for_window(win)")
    check(idx != -1, "home.py must still initialise layer shell")
    # find a try: before it
    before = text.rfind("try:", 0, idx)
    check(before != -1, "home.py layer-shell init must be guarded by try")
    after = text.find("except Exception", idx)
    check(after != -1, "home.py layer-shell init must have except Exception")
    # launch handling
    check("failed to launch" in text, "home.py must report launch failures")
    # stats guards
    check("MemAvailable" in text and "return None" in text, "Stats.mem must guard missing keys")
    check("except (OSError, ValueError, IndexError)" in text, "Stats._raw must guard /proc/stat")


def test_notifd_layer_shell_guarded():
    text = read(NOTIFD_PY)
    check(text.count("LS.init_for_window") == 2, "notifd must still init both layer surfaces")
    check(text.count("except Exception as exc") >= 2, "notifd must guard both layer-shell blocks")
    check("layer-shell unavailable" in text, "notifd must log layer-shell failures")


def test_launcher_surfaces_errors():
    text = read(LAUNCHER_PY)
    check("except Exception as exc" in text, "launcher.launch must catch launch errors")
    check("failed to launch" in text, "launcher.launch must report launch failures")
    check("self.quit()" in text, "launcher.launch must still close after attempt")


def test_wrappers_search_fallback():
    for p in (SMTH_HOME, SMTH_NOTIFD):
        text = read(p)
        check("ldconfig" in text, f"{p.name} must try ldconfig")
        check("/usr/lib/x86_64-linux-gnu" in text or "find /usr/lib" in text,
              f"{p.name} must have a fallback search")


def test_check_wiring_lists_flock():
    text = read(CHECK_WIRING)
    check('"flock"' in text, "check_wiring must know flock")


# --- functional locking test for smth-mode ---

def _make_stubs(root):
    bindir = root / "bin"
    bindir.mkdir()
    home = root / "home"
    (home / ".config" / "smth").mkdir(parents=True)
    (home / ".config" / "labwc").mkdir(parents=True)
    (home / ".config" / "smth" / "rc-desktop.xml").write_text("<labwc/>")
    waybar_log = root / "waybar.log"

    def write(name, body):
        p = bindir / name
        p.write_text(body)
        p.chmod(0o755)

    write("wlr-randr", "#!/bin/sh\nprintf 'DP-1\\n'\n")
    write("hostnamectl", "#!/bin/sh\necho desktop\n")
    write("labwc", "#!/bin/sh\nexit 0\n")
    write("pkill", "#!/bin/sh\nexit 0\n")
    write("pgrep", "#!/bin/sh\nexit 1\n")
    write("notify-send", "#!/bin/sh\nexit 0\n")
    write("setsid", "#!/bin/sh\nexec \"$@\"\n")
    write("waybar", f"#!/bin/sh\nprintf 'waybar %s\\n' \"$*\" >> \"{waybar_log}\"\nexit 0\n")
    return home, bindir, waybar_log


def test_smth_mode_sequential_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        home, bindir, wlog = _make_stubs(root)
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["PATH"] = f"{bindir}:{os.environ.get('PATH', '')}"
        # first run applies
        r1 = subprocess.run([str(SMTH_MODE), "desktop"], env=env, capture_output=True, text=True)
        check(r1.returncode == 0, f"smth-mode first run failed: {r1.stderr}")
        # second run should exit via guard without starting waybar again
        r2 = subprocess.run([str(SMTH_MODE), "desktop"], env=env, capture_output=True, text=True)
        check(r2.returncode == 0, f"smth-mode second run failed: {r2.stderr}")
        count = len([l for l in wlog.read_text().splitlines() if l.strip()]) if wlog.exists() else 0
        check(count == 1, f"sequential runs started waybar {count} times (expected 1)")


def test_smth_mode_concurrent_single_start():
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        home, bindir, wlog = _make_stubs(root)
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["PATH"] = f"{bindir}:{os.environ.get('PATH', '')}"
        # remove any .current to force contention
        (home / ".config" / "smth" / ".current").unlink(missing_ok=True)
        procs = []
        for _ in range(8):
            procs.append(subprocess.Popen([str(SMTH_MODE), "desktop"], env=env,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for p in procs:
            try:
                p.wait(timeout=15)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        count = len([l for l in wlog.read_text().splitlines() if l.strip()]) if wlog.exists() else 0
        check(count == 1, f"concurrent runs started waybar {count} times (expected 1)")


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
        print(f"FAIL phase b5 repairs: {len(failures)} problem(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS phase b5 repairs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
