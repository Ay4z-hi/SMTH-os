#!/usr/bin/env python3
"""A/B benchmark: the bash taskbar chain versus the native SMTH helpers.

Measures, for the real shipped commands:

* per-invocation wall time and CPU time (RUSAGE_CHILDREN),
* peak RSS of the child process tree (RUSAGE_CHILDREN),
* execve/fork count per invocation (via strace, when available),
* resident memory of the layout watcher: the legacy bash + udevadm + subshell
  pipeline against the single native daemon.

The numbers are measurements on the machine that runs this tool. They are not
transferable to a different kernel, CPU or page size, so the tool prints the
host it measured. Nothing is written unless --json is passed.

Usage:
  python3 tools/bench_native.py [--runs 50] [--json PATH] [--quick]
"""
import argparse
import json
import os
import pathlib
import platform
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
BUILD = NATIVE / "build"
GLANCE = BUILD / "smth-glance"
MODED = BUILD / "smth-moded"
ONE_SHOT = BUILD / "one_shot"
LEGACY_GLANCE = NATIVE / "legacy" / "smth-glance.sh"
LEGACY_MODED = NATIVE / "legacy" / "smth-moded.sh"


def build():
    result = subprocess.run(["make", "-C", str(NATIVE), "all", "bench-tool"], capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        raise SystemExit("make -C native all failed")


def run_once(argv):
    """One invocation measured by native/bench/one_shot (a 16 KiB C parent).

    A forked child inherits its parent's high-water RSS, so measuring from
    CPython (~11 MiB resident) would report 11 MiB for a 1 MiB binary. one_shot
    forks from a tiny process and reports wait4's exact figures.
    """
    result = subprocess.run([str(ONE_SHOT), "--", *argv], capture_output=True, text=True)
    wall, cpu, rss, status = result.stdout.split()
    if int(status) not in (0, 127):  # 127 = command missing in the sandbox PATH
        raise SystemExit(f"one_shot: {argv} exited {status}: {result.stderr.strip()}")
    return float(wall), float(cpu), int(rss), int(status)


def measure(command, runs):
    """Median wall/CPU per run plus the largest peak RSS any run reached."""
    walls, cpus, rss = [], [], []
    for _ in range(runs):
        wall, cpu, peak, _ = run_once(command)
        walls.append(wall)
        cpus.append(cpu)
        rss.append(peak)
    return {
        "wall_ms": round(statistics.median(walls), 3),
        "cpu_ms": round(statistics.median(cpus), 3),
        "peak_rss_kib": max(rss),
        "runs": runs,
    }


def exec_count(command):
    """execve calls per invocation, including children (strace -f)."""
    if not shutil.which("strace"):
        return None
    with tempfile.NamedTemporaryFile("r", suffix=".strace", delete=True) as handle:
        result = subprocess.run(
            ["strace", "-f", "-e", "trace=execve", "-o", handle.name, *command],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return None
        handle.seek(0)
        text = handle.read()
    if not text:
        return None
    return sum(1 for line in text.splitlines() if "execve(" in line and "= -1" not in line)


def process_group_pss(pgid):
    """Sum PSS/RSS for every live process in a process group."""
    pids, pss, rss = [], 0, 0
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
        except OSError:
            continue
        # comm may contain spaces/parentheses; fields after the last ')'.
        fields = stat[stat.rfind(")") + 2:].split()
        if len(fields) < 3 or int(fields[2]) != pgid:
            continue
        pid = int(entry.name)
        pids.append(pid)
        rollup = entry / "smaps_rollup"
        try:
            for line in rollup.read_text().splitlines():
                if line.startswith("Pss:"):
                    pss += int(line.split()[1])
                elif line.startswith("Rss:"):
                    rss += int(line.split()[1])
        except OSError:
            status = entry / "status"
            try:
                for line in status.read_text().splitlines():
                    if line.startswith("VmRSS:"):
                        value = int(line.split()[1])
                        pss += value
                        rss += value
            except OSError:
                continue
    return {"pids": len(pids), "pss_kib": pss, "rss_kib": rss}


def resident_daemon(command, env=None, settle=1.5, samples=3):
    """Spawn a watcher, let it settle, and sample its process group."""
    results = []
    for _ in range(samples):
        proc = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=env, start_new_session=True)
        try:
            time.sleep(settle)
            results.append(process_group_pss(proc.pid))
        finally:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)
    return {
        "pids": round(statistics.median([r["pids"] for r in results])),
        "pss_kib": round(statistics.median([r["pss_kib"] for r in results])),
        "rss_kib": round(statistics.median([r["rss_kib"] for r in results])),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=40)
    parser.add_argument("--json", type=pathlib.Path)
    parser.add_argument("--quick", action="store_true", help="fewer runs, for CI smoke checks")
    args = parser.parse_args()
    runs = 8 if args.quick else args.runs

    build()
    floor = measure(["true"], 5)
    report = {
        "launcher_floor_kib": floor["peak_rss_kib"],
        "host": {
            "machine": platform.machine(),
            "kernel": platform.release(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "page_size": os.sysconf("SC_PAGE_SIZE"),
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "glance": {},
        "watcher": {},
    }

    print(f"one-shot RSS floor (native/bench/one_shot around /bin/true): "
          f"{floor['peak_rss_kib'] / 1024:.1f} MiB\n")

    for mode in ("cpu", "mem", "disk"):
        legacy = ["bash", str(LEGACY_GLANCE), mode]
        native = [str(GLANCE), mode]
        old = measure(legacy, runs)
        new = measure(native, runs)
        old["execve"] = exec_count(legacy)
        new["execve"] = exec_count(native)
        report["glance"][mode] = {"legacy": old, "native": new}
        print(f"\n=== smth-glance {mode} ({runs} runs, median) ===")
        print(f"  legacy : wall {old['wall_ms']:.2f} ms  cpu {old['cpu_ms']:.2f} ms  "
              f"peak RSS {old['peak_rss_kib'] / 1024:.1f} MiB  execve {old['execve']}")
        print(f"  native : wall {new['wall_ms']:.2f} ms  cpu {new['cpu_ms']:.2f} ms  "
              f"peak RSS {new['peak_rss_kib'] / 1024:.1f} MiB  execve {new['execve']}")
        if old["wall_ms"] > 0:
            print(f"  change : wall {100 * (new['wall_ms'] - old['wall_ms']) / old['wall_ms']:+.1f}%  "
                  f"CPU {100 * (new['cpu_ms'] - old['cpu_ms']) / old['cpu_ms']:+.1f}%")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)
        fake = tmp_path / "smth-mode"
        fake.write_text("#!/bin/sh\nexit 0\n")
        fake.chmod(0o755)
        env = dict(os.environ, PATH=f"{tmp_path}:{os.environ.get('PATH', '')}")
        legacy_watcher = resident_daemon(["bash", str(LEGACY_MODED)], env=env)
        native_watcher = resident_daemon([str(MODED)], env=env)

    report["watcher"] = {"legacy": legacy_watcher, "native": native_watcher}
    print("\n=== layout watcher (resident, median of 3) ===")
    print(f"  legacy bash + udevadm + subshell : {legacy_watcher['pids']} processes, "
          f"PSS {legacy_watcher['pss_kib'] / 1024:.1f} MiB, RSS {legacy_watcher['rss_kib'] / 1024:.1f} MiB")
    print(f"  native smth-moded                : {native_watcher['pids']} processes, "
          f"PSS {native_watcher['pss_kib'] / 1024:.1f} MiB, RSS {native_watcher['rss_kib'] / 1024:.1f} MiB")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
