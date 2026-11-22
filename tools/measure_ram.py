#!/usr/bin/env python3
"""Collect the SMTH runtime baseline: per-process memory, idle CPU and startup.

This is the reproducible measurement that the performance work is judged
against. It runs on a booted image (live ISO, VM or installed system), reads
only /proc, needs no root, and writes nothing unless asked.

Why PSS as well as RSS: the GTK4/Python helpers and labwc share large library
mappings, so summing RSS double-counts them. PSS splits each shared page
between the processes that map it, which makes the session total meaningful.
RSS is still reported because it is what a user sees in most tools.

Usage on the image:
  python3 tools/measure_ram.py                      # 10 s idle window, table
  python3 tools/measure_ram.py --seconds 30 --json baseline.json
  python3 tools/measure_ram.py --compare baseline.json   # before/after deltas
  python3 tools/measure_ram.py --markdown report.md

Processes watched by default are the SMTH session (compositor, taskbar, Rust
supervisor, GTK helpers, native helpers) plus the system daemons the image
enables, so a regression in any of them is visible.
"""
import argparse
import json
import os
import pathlib
import re
import sys
import time

DEFAULT_WATCH = {
    "labwc", "waybar", "swaybg", "swayidle", "fuzzel", "wvkbd-mobintl",
    "smthd", "smth-moded", "smth-glance", "smth-home", "smth-notifd",
    "Xwayland", "pipewire", "wireplumber", "pipewire-pulse",
    "NetworkManager", "bluetoothd", "power-profiles-daemon", "udisksd",
    "dbus-daemon", "dbus-broker", "nft", "systemd-journald", "systemd-udevd",
}
SMTH_PATHS = ("/usr/local/lib/smth/", "/usr/local/bin/smth", "/usr/bin/smth")


def read_text(path):
    try:
        return pathlib.Path(path).read_text(errors="replace")
    except OSError:
        return ""


def hz():
    return os.sysconf("SC_CLK_TCK")


def proc_cmdline(pid):
    raw = read_text(f"/proc/{pid}/cmdline")
    return [part for part in raw.split("\0") if part]


def display_name(pid, cmdline):
    if not cmdline:
        return read_text(f"/proc/{pid}/comm").strip() or f"pid{pid}"
    argv0 = os.path.basename(cmdline[0])
    if argv0.startswith("python"):
        for part in cmdline[1:]:
            if part.endswith(".py"):
                return f"python3 {os.path.basename(part)}"
    return argv0


def stat_fields(pid):
    """Fields of /proc/pid/stat after the (possibly spaced) comm field."""
    text = read_text(f"/proc/{pid}/stat")
    if not text:
        return None
    return text[text.rfind(")") + 2:].split()


def memory(pid):
    """RSS/threads from status, PSS/private/swap from smaps_rollup."""
    result = {"rss_kib": 0, "vm_size_kib": 0, "threads": 0, "pss_kib": 0, "private_kib": 0,
              "swap_kib": 0, "pss_source": "smaps_rollup"}
    for line in read_text(f"/proc/{pid}/status").splitlines():
        if line.startswith("VmRSS:"):
            result["rss_kib"] = int(line.split()[1])
        elif line.startswith("VmSize:"):
            result["vm_size_kib"] = int(line.split()[1])
        elif line.startswith("Threads:"):
            result["threads"] = int(line.split()[1])
    rollup = read_text(f"/proc/{pid}/smaps_rollup")
    for line in rollup.splitlines():
        key, _, rest = line.partition(":")
        if key in ("Pss", "Private_Clean", "Private_Dirty", "Swap"):
            value = int(rest.split()[0])
            if key == "Pss":
                result["pss_kib"] += value
            elif key == "Swap":
                result["swap_kib"] += value
            else:
                result["private_kib"] += value
    if result["pss_kib"] == 0:
        # smaps_rollup is owner/root-only; without it PSS cannot be split,
        # so the report says so instead of passing RSS off as PSS.
        result["pss_kib"] = result["rss_kib"]
        result["pss_source"] = "rss_fallback"
    return result


def system_memory():
    info = {}
    for line in read_text("/proc/meminfo").splitlines():
        key, _, rest = line.partition(":")
        if rest:
            info[key] = int(rest.split()[0])
    total = info.get("MemTotal", 0)
    available = info.get("MemAvailable", 0)
    return {
        "mem_total_kib": total,
        "mem_available_kib": available,
        "mem_used_kib": total - available,
        "mem_used_percent": round((total - available) * 100 / total, 1) if total else 0.0,
        "swap_total_kib": info.get("SwapTotal", 0),
        "swap_free_kib": info.get("SwapFree", 0),
    }


def uptime():
    text = read_text("/proc/uptime").split()
    return float(text[0]) if text else 0.0


def collect(names, cpu_before, elapsed):
    processes = []
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        cmdline = proc_cmdline(pid)
        if not cmdline:
            continue
        comm = read_text(f"/proc/{pid}/comm").strip()
        is_smth = any(path in part for part in cmdline for path in SMTH_PATHS)
        if comm not in names and display_name(pid, cmdline) not in names and not is_smth:
            continue
        fields = stat_fields(pid)
        if fields is None or len(fields) < 20:
            continue
        mem = memory(pid)
        ticks = int(fields[11]) + int(fields[12])
        before = cpu_before.get(pid, ticks)
        cpu_percent = (ticks - before) / (hz() * elapsed) * 100.0 if elapsed > 0 else 0.0
        start_ticks = int(fields[19])
        processes.append({
            "pid": pid,
            "name": display_name(pid, cmdline),
            "cmdline": " ".join(cmdline)[:200],
            "rss_kib": mem["rss_kib"],
            "pss_kib": mem["pss_kib"],
            "private_kib": mem["private_kib"],
            "swap_kib": mem["swap_kib"],
            "threads": mem["threads"],
            "pss_source": mem["pss_source"],
            "cpu_percent": round(max(0.0, cpu_percent), 2),
            "age_seconds": round(max(0.0, uptime() - start_ticks / hz()), 1),
        })
    processes.sort(key=lambda item: item["pss_kib"], reverse=True)
    return processes


def cpu_ticks():
    read = {"total": 0, "idle": 0, "process": {}}
    line = read_text("/proc/stat").splitlines()[0].split()
    values = [int(v) for v in line[1:]]
    read["total"] = sum(values)
    read["idle"] = values[3] + (values[4] if len(values) > 4 else 0)
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        fields = stat_fields(entry.name)
        if fields and len(fields) > 12:
            read["process"][int(entry.name)] = int(fields[11]) + int(fields[12])
    return read


def sample(names, seconds):
    before = cpu_ticks()
    time.sleep(seconds)
    after = cpu_ticks()
    elapsed = max(0.001, seconds)
    total_delta = after["total"] - before["total"]
    idle_delta = after["idle"] - before["idle"]
    processes = collect(names, before["process"], elapsed)
    report = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sample_seconds": seconds,
        "system": system_memory(),
        "cpu": {
            "idle_percent": round(idle_delta * 100.0 / total_delta, 1) if total_delta else None,
            "busy_percent": round((total_delta - idle_delta) * 100.0 / total_delta, 1) if total_delta else None,
            "load": read_text("/proc/loadavg").split()[:3],
            "cpu_count": os.cpu_count(),
        },
        "uptime_seconds": round(uptime(), 1),
        "processes": processes,
        "totals": {
            "processes": len(processes),
            "rss_kib": sum(p["rss_kib"] for p in processes),
            "pss_kib": sum(p["pss_kib"] for p in processes),
            "private_kib": sum(p["private_kib"] for p in processes),
            "cpu_percent": round(sum(p["cpu_percent"] for p in processes), 2),
        },
    }
    return report


def mib(kib):
    return f"{kib / 1024.0:.1f}"


def print_table(report):
    system = report["system"]
    total = system["mem_total_kib"]
    print(f"SMTH runtime baseline — {report['captured_at']} "
          f"(window {report['sample_seconds']}s, {report['cpu']['cpu_count']} CPUs)")
    print(f"system : used {mib(system['mem_used_kib'])} / {mib(total)} MiB "
          f"({system['mem_used_percent']}%), available {mib(system['mem_available_kib'])} MiB, "
          f"swap {mib(system['swap_total_kib'] - system['swap_free_kib'])} / {mib(system['swap_total_kib'])} MiB used")
    print(f"cpu    : idle {report['cpu']['idle_percent']}%  busy {report['cpu']['busy_percent']}%  "
          f"load {' '.join(report['cpu']['load'])}  uptime {report['uptime_seconds']:.0f}s")
    print()
    print(f"{'process':32s} {'pid':>7s} {'RSS MiB':>8s} {'PSS MiB':>8s} {'priv MiB':>9s} "
          f"{'thr':>4s} {'cpu %':>6s} {'age s':>8s}")
    for process in report["processes"]:
        print(f"{process['name'][:32]:32s} {process['pid']:7d} {mib(process['rss_kib']):>8s} "
              f"{mib(process['pss_kib']):>8s} {mib(process['private_kib']):>9s} "
              f"{process['threads']:4d} {process['cpu_percent']:6.2f} {process['age_seconds']:8.1f}")
    totals = report["totals"]
    print(f"{'TOTAL (PSS sums shared pages once)':32s} {'':>7s} {mib(totals['rss_kib']):>8s} "
          f"{mib(totals['pss_kib']):>8s} {'':>9s} {'':>4s} {totals['cpu_percent']:6.2f}")
    fallback = [p["name"] for p in report["processes"] if p.get("pss_source") == "rss_fallback"]
    if fallback:
        print(f"note   : PSS unavailable for {len(fallback)} process(es) not owned by this user "
              f"({', '.join(fallback[:4])}{', ...' if len(fallback) > 4 else ''}); their RSS is used")
    print("note   : run this as the session user so every SMTH process reports PSS")


def markdown(report):
    system = report["system"]
    lines = [
        f"Captured {report['captured_at']} over {report['sample_seconds']} s, "
        f"{report['cpu']['cpu_count']} CPUs, uptime {report['uptime_seconds']:.0f} s.",
        "",
        f"- System used: **{mib(system['mem_used_kib'])} MiB / {mib(system['mem_total_kib'])} MiB** "
        f"({system['mem_used_percent']}%), available {mib(system['mem_available_kib'])} MiB",
        f"- Idle CPU: {report['cpu']['idle_percent']}% idle, {report['cpu']['busy_percent']}% busy",
        f"- Session total (sum of PSS): **{mib(report['totals']['pss_kib'])} MiB** "
        f"across {report['totals']['processes']} processes",
        "",
        "| Process | PID | RSS MiB | PSS MiB | Private MiB | Threads | CPU % | Age s |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for process in report["processes"]:
        lines.append(
            f"| `{process['name']}` | {process['pid']} | {mib(process['rss_kib'])} | "
            f"{mib(process['pss_kib'])} | {mib(process['private_kib'])} | {process['threads']} | "
            f"{process['cpu_percent']:.2f} | {process['age_seconds']:.1f} |")
    return "\n".join(lines) + "\n"


def compare(report, baseline):
    print("\nComparison against baseline")
    old = baseline.get("totals", {})
    new = report["totals"]
    for key in ("rss_kib", "pss_kib", "private_kib"):
        delta = new.get(key, 0) - old.get(key, 0)
        print(f"  {key:12s}: {mib(old.get(key, 0)):>8s} -> {mib(new.get(key, 0)):>8s} MiB "
              f"({delta / 1024.0:+.1f} MiB)")
    old_sys = baseline.get("system", {})
    print(f"  system used : {mib(old_sys.get('mem_used_kib', 0)):>8s} -> "
          f"{mib(report['system']['mem_used_kib']):>8s} MiB "
          f"({(report['system']['mem_used_kib'] - old_sys.get('mem_used_kib', 0)) / 1024.0:+.1f} MiB)")
    old_processes = {p["name"]: p for p in baseline.get("processes", [])}
    new_processes = {p["name"]: p for p in report["processes"]}
    for name in sorted(set(old_processes) | set(new_processes)):
        was = old_processes.get(name, {}).get("pss_kib")
        now = new_processes.get(name, {}).get("pss_kib")
        if was is None:
            print(f"  + {name}: {mib(now)} MiB PSS (not in baseline)")
        elif now is None:
            print(f"  - {name}: was {mib(was)} MiB PSS (gone)")
        elif abs(now - was) >= 1024:
            print(f"  ~ {name}: {mib(was)} -> {mib(now)} MiB PSS ({(now - was) / 1024.0:+.1f})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seconds", type=float, default=10.0, help="idle CPU sampling window")
    parser.add_argument("--watch", default="", help="extra process names, comma separated")
    parser.add_argument("--json", type=pathlib.Path, help="write the full measurement here")
    parser.add_argument("--markdown", type=pathlib.Path, help="write a Markdown table here")
    parser.add_argument("--compare", type=pathlib.Path, help="compare against an earlier --json file")
    args = parser.parse_args()

    names = set(DEFAULT_WATCH)
    names.update(item.strip() for item in args.watch.split(",") if item.strip())
    report = sample(names, args.seconds)
    print_table(report)

    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(report))
        print(f"\nwrote {args.markdown}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.json}")
    if args.compare:
        compare(report, json.loads(args.compare.read_text()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
