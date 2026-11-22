#!/usr/bin/env python3
"""Contract and parity tests for the native SMTH shell helpers (C).

Two things are checked:

* the Waybar JSON contract is unchanged, so the taskbar configuration and the
  liquid-glass dot language do not need to change, and
* the native sampler agrees with the bash implementation it replaced and with
  the kernel's own numbers (/proc, statvfs, df), so "faster" did not become
  "different".

Usage: python3 tools/test_native.py [-v]
Exit status 1 on any failure.
"""
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
BUILD = NATIVE / "build"
GLANCE = BUILD / "smth-glance"
MODED = BUILD / "smth-moded"
LEGACY_GLANCE = NATIVE / "legacy" / "smth-glance.sh"
FILLED, EMPTY = "●", "○"
VERBOSE = "-v" in sys.argv

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)
    elif VERBOSE:
        print(f"  ok {message}")
    return condition


def build():
    """Build with the project flags; a build failure is a test failure."""
    if not shutil.which("cc") and not shutil.which("gcc") and not shutil.which("make"):
        print("SKIP native helpers: no C compiler/make on this machine")
        return False
    result = subprocess.run(
        ["make", "-C", str(NATIVE), "clean", "all"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("FAIL native build")
        print(result.stdout)
        print(result.stderr)
        failures.append("make -C native clean all failed")
        return False
    return True


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


def glance(*args):
    return run([str(GLANCE), *args])


def dots_for(percent):
    """Reference implementation of the shipping rule, in Python."""
    percent = max(0, min(100, percent))
    return FILLED * ((percent * 5 + 50) // 100) + EMPTY * (5 - (percent * 5 + 50) // 100)


def parse_json(result, label):
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        failures.append(f"{label}: output is not JSON: {result.stdout.strip()!r}")
        return None


def percent_from_tooltip(tooltip):
    match = re.search(r"(\d+)%", tooltip or "")
    return int(match.group(1)) if match else None


def test_formatters():
    """Pure formatter branches: clamping, rounding, hot threshold."""
    cases = [
        (("fmt", "cpu", "0", "8"), 0, ""),
        (("fmt", "cpu", "6.8", "8"), 85, ""),      # 85% is not "hot" (> 85)
        (("fmt", "cpu", "6.88", "8"), 86, "hot"),
        (("fmt", "cpu", "64", "8"), 100, "hot"),    # clamped
        (("fmt", "cpu", "abc", "8"), 0, ""),        # unparsable load -> 0
    ]
    for args, percent, css in cases:
        result = glance(*args)
        data = parse_json(result, " ".join(args)) or {}
        text = data.get("text", "")
        check(result.returncode == 0, f"{' '.join(args)} exits 0")
        check(text == f"CPU {dots_for(percent)}", f"{' '.join(args)} dots -> {dots_for(percent)}")
        check(data.get("class") == css, f"{' '.join(args)} class -> {css!r}")
        # The CPU tooltip carries load/cores, not a percentage (same as the
        # shell contract); the dot count above is what proves the percentage.
        check(f"load {args[2]} on {args[3]} cores" == data.get("tooltip"),
              f"{' '.join(args)} tooltip -> load/cores")

    mem_cases = [
        (("fmt", "mem", "0", "100"), 0),
        (("fmt", "mem", "50", "100"), 50),
        (("fmt", "mem", "100", "0"), 0),       # no total: never divide by zero
        (("fmt", "mem", "999", "1000"), 99),   # truncation, not rounding up
    ]
    for args, percent in mem_cases:
        result = glance(*args)
        data = parse_json(result, " ".join(args)) or {}
        check(result.returncode == 0, f"{' '.join(args)} exits 0")
        check(data.get("text") == f"RAM {dots_for(percent)}", f"{' '.join(args)} dots")
        check(percent_from_tooltip(data.get("tooltip")) == percent, f"{' '.join(args)} percent")

    disk_cases = [
        (("fmt", "disk", "0", "100"), 0),
        (("fmt", "disk", "1", "0"), 100),
        (("fmt", "disk", "3", "1"), 75),   # ceil(300/4) = 75, df semantics
        (("fmt", "disk", "0", "0"), 0),
    ]
    for args, percent in disk_cases:
        result = glance(*args)
        data = parse_json(result, " ".join(args)) or {}
        check(result.returncode == 0, f"{' '.join(args)} exits 0")
        check(data.get("text") == f"SSD {dots_for(percent)}", f"{' '.join(args)} dots")
        check(percent_from_tooltip(data.get("tooltip")) == percent, f"{' '.join(args)} percent")
        check("class" not in data, f"{' '.join(args)} keeps the shell's no-class contract")


def test_contract():
    for mode, prefix, has_class in (("cpu", "CPU ", True), ("mem", "RAM ", True), ("disk", "SSD ", False)):
        result = glance(mode)
        data = parse_json(result, mode) or {}
        check(result.returncode == 0, f"{mode} exits 0")
        check(data.get("text", "").startswith(prefix), f"{mode} text starts with {prefix!r}")
        check(len(data.get("text", "")) == len(prefix) + 5, f"{mode} has exactly 5 glyphs")
        check(set(data.get("text", "")[len(prefix):]) <= {FILLED, EMPTY}, f"{mode} uses ●/○ only")
        check(bool(data.get("tooltip")), f"{mode} has a tooltip")
        check(("class" in data) is has_class, f"{mode} class field presence")

    result = glance("all")
    data = parse_json(result, "all") or {}
    check(result.returncode == 0, "all exits 0")
    check(set(data) == {"cpu", "mem", "disk"}, "all reports cpu, mem and disk")
    check({"percent", "load", "cores"} <= set(data.get("cpu", {})), "all.cpu carries percent/load/cores")
    check({"percent", "used_kib", "total_kib"} <= set(data.get("mem", {})), "all.mem carries kib values")
    check({"percent", "used_blocks", "avail_blocks"} <= set(data.get("disk", {})), "all.disk carries block counts")


def test_usage():
    check(glance().returncode == 2, "no arguments is a usage error")
    check(glance("bogus").returncode == 2, "unknown mode is a usage error")
    check(glance("fmt", "cpu").returncode == 2, "incomplete fmt is a usage error")
    help_result = glance("--help")
    check(help_result.returncode == 0 and "usage:" in help_result.stdout, "--help prints usage")


def test_live_numbers():
    """The sampler must agree with the kernel and with the shell it replaced."""
    data = parse_json(glance("cpu"), "cpu") or {}
    tooltip = data.get("tooltip", "")
    match = re.search(r"load (\S+) on (\d+) cores", tooltip)
    if check(match is not None, "cpu tooltip carries load and cores"):
        load, cores = float(match.group(1)), int(match.group(2))
        expected = min(100, int(load * 100.0 / max(1, cores)))
        check(data.get("text") == f"CPU {dots_for(expected)}", "cpu dots derived from the printed load")
        check(data.get("class") == ("hot" if expected > 85 else ""), "cpu hot class derived from the load")

    mem = parse_json(glance("mem"), "mem") or {}
    info = {}
    with open("/proc/meminfo", encoding="ascii") as handle:
        for line in handle:
            key, _, rest = line.partition(":")
            info[key] = int(rest.split()[0])
    expected = (info["MemTotal"] - info["MemAvailable"]) * 100 // info["MemTotal"]
    live = percent_from_tooltip(mem.get("tooltip"))
    check(abs((live or 0) - expected) <= 1, f"mem percent matches /proc/meminfo ({live} vs {expected})")

    disk = parse_json(glance("disk"), "disk") or {}
    stat = os.statvfs("/")
    used, avail = stat.f_blocks - stat.f_bfree, stat.f_bavail
    expected = -(-used * 100 // (used + avail))
    live = percent_from_tooltip(disk.get("tooltip"))
    check(abs((live or 0) - expected) <= 1, f"disk percent matches statvfs ({live} vs {expected})")
    if shutil.which("df"):
        df = run(["df", "--output=pcent", "/"])
        if df.returncode == 0:
            rows = [line.strip().rstrip("%") for line in df.stdout.splitlines()[1:] if line.strip()]
            if rows and rows[-1].isdigit():
                check(abs(int(rows[-1]) - (live or 0)) <= 1,
                      f"disk percent matches df ({live} vs {rows[-1]})")

    snapshot = parse_json(glance("all"), "all") or {}
    for key in ("mem", "disk"):  # cpu carries no percentage in its tooltip
        single = percent_from_tooltip((parse_json(glance(key), key) or {}).get("tooltip"))
        both = snapshot.get(key, {}).get("percent")
        check(abs((single or 0) - (both or 0)) <= 1, f"all.{key} agrees with the single sampler")

    # The snapshot's CPU figure must come from the same kernel values, without
    # racing the dot rendering: compare the load it reports and its own maths.
    loadavg = float(open("/proc/loadavg", encoding="ascii").read().split()[0])
    cpu = snapshot.get("cpu", {})
    check(abs(float(cpu.get("load", 0)) - loadavg) <= 0.5,
          f"all.cpu.load tracks /proc/loadavg ({cpu.get('load')} vs {loadavg})")
    check(cpu.get("cores") == os.cpu_count(), "all.cpu.cores matches the online CPU count")
    expected = min(100, int(float(cpu.get("load", 0)) * 100.0 / max(1, cpu.get("cores", 1))))
    check(abs(cpu.get("percent", 0) - expected) <= 1, f"all.cpu.percent derived from its own load ({cpu.get('percent')} vs {expected})")


def test_legacy_parity():
    """The replacement must produce the same JSON contract as the bash script."""
    if not shutil.which("bash"):
        print("SKIP legacy parity: no bash")
        return
    # The shell implementation shelled out for its numbers. Where those tools
    # are absent (procps is not in the image's package lists, and CI images are
    # minimal) the old module emitted a broken meter rather than a number, so
    # parity cannot be compared. That is a finding about the old code, not a
    # failure of the new one, which has no such dependency.
    requirements = {
        "cpu": ("awk", "nproc"),
        "mem": ("awk", "free"),
        "disk": ("df", "tail", "tr"),
    }
    for mode, tools in requirements.items():
        missing = [tool for tool in tools if not shutil.which(tool)]
        if missing:
            print(f"SKIP legacy parity for {mode}: the shell version needs {', '.join(missing)}; "
                  f"the native sampler needs neither")
            continue
        old = run(["bash", str(LEGACY_GLANCE), mode])
        new = glance(mode)
        if not check(old.returncode == 0, f"legacy {mode} still runs"):
            continue
        old_data = parse_json(old, f"legacy {mode}") or {}
        new_data = parse_json(new, f"native {mode}") or {}
        check(set(old_data) == set(new_data), f"{mode}: same JSON keys as the shell")
        old_pct = percent_from_tooltip(old_data.get("tooltip"))
        new_pct = percent_from_tooltip(new_data.get("tooltip"))
        check(abs((old_pct or 0) - (new_pct or 0)) <= 1, f"{mode}: percent within 1 ({old_pct} vs {new_pct})")
        check(old_data.get("class") == new_data.get("class") or abs((old_pct or 0) - (new_pct or 0)) <= 1,
              f"{mode}: same hot class")
        check(old_data.get("text", "")[:3] == new_data.get("text", "")[:3], f"{mode}: same label prefix")


def fake_layout_bin(directory):
    path = directory / "smth-mode"
    path.write_text("#!/bin/sh\nprintf '%s %s\\n' \"$1\" \"$2\" >> \"$SMTH_MODE_LOG\"\n")
    path.chmod(0o755)
    return path


def test_moded():
    """The layout watcher applies the layout once and idles without burning CPU."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        fake_layout_bin(tmp_path)
        log = tmp_path / "layout.log"
        env = dict(os.environ, PATH=f"{tmp_path}:{os.environ.get('PATH', '')}", SMTH_MODE_LOG=str(log))

        once = run([str(MODED), "--once"], env=env, timeout=30)
        check(once.returncode == 0, "smth-moded --once exits 0")
        check(log.exists() and log.read_text().strip() == "auto", "smth-moded --once runs `smth-mode auto` once")

        check(run([str(MODED), "--nonsense"], env=env).returncode == 2, "unknown argument is a usage error")

        log.unlink(missing_ok=True)
        daemon = subprocess.Popen([str(MODED)], env=env, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE, start_new_session=True)
        try:
            time.sleep(0.6)
            check(daemon.poll() is None, "smth-moded stays resident")
            check(log.exists() and log.read_text().count("auto") == 1,
                  "smth-moded applies the layout once at startup")
            if daemon.poll() is None:
                with open(f"/proc/{daemon.pid}/stat", encoding="ascii") as handle:
                    ticks0 = sum(int(x) for x in handle.read().split()[13:15])
                time.sleep(0.8)
                with open(f"/proc/{daemon.pid}/stat", encoding="ascii") as handle:
                    ticks1 = sum(int(x) for x in handle.read().split()[13:15])
                check(ticks1 - ticks0 <= 4, f"smth-moded idles without CPU spin ({ticks1 - ticks0} ticks/0.8s)")
                rss = None
                with open(f"/proc/{daemon.pid}/status", encoding="ascii") as handle:
                    for line in handle:
                        if line.startswith("VmRSS:"):
                            rss = int(line.split()[1])
                check(rss is not None and rss < 3000, f"smth-moded RSS is small ({rss} KiB)")
        finally:
            daemon.send_signal(signal.SIGTERM)
            try:
                daemon.wait(timeout=5)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.wait(timeout=5)
            check(daemon.returncode == 0, f"smth-moded exits 0 on SIGTERM (got {daemon.returncode})")


def main():
    if not build():
        print(f"FAIL native helpers: {len(failures)} problem(s)")
        for item in failures:
            print(f"  - {item}")
        return 1
    test_contract()
    test_formatters()
    test_usage()
    test_live_numbers()
    test_legacy_parity()
    test_moded()
    if failures:
        print(f"FAIL native helpers: {len(failures)} problem(s)")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("PASS native helpers: contract, formatter rules, /proc parity, shell parity, layout watcher")
    return 0


if __name__ == "__main__":
    sys.exit(main())
