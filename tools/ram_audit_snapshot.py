#!/usr/bin/env python3
"""Take one whole-machine memory snapshot for the live RAM audit.

Unlike tools/measure_ram.py this does not use a watch list: it walks every
process so the totals can be compared with /proc/meminfo and nothing that is
actually resident can hide. Run it as root on the image so smaps_rollup is
readable for every process (PSS, private and swap are owner-only).

Output is a single JSON document on stdout:

    python3 ram_audit_snapshot.py --phase idle_120 > /run/audit/idle_120.json

Processes are grouped by what they are (Python helper, GTK4 client, Rust
supervisor, native C helper, session/service) so the report can answer "which
component costs what" without double-counting shared library pages: every
group total is a sum of PSS, and the all-process PSS sum counts each shared
page once.
"""
import argparse
import json
import os
import pathlib
import sys
import time

SMTH_LIB = "/usr/local/lib/smth"
RUST_BINS = {"smthd", "smth-ahian", "smthctl-core"}
NATIVE_BINS = {"smth-glance", "smth-moded"}
SESSION_BINS = {
    "labwc", "waybar", "swaybg", "swayidle", "fuzzel", "wvkbd-mobintl",
    "Xwayland", "smth-home", "smth-notifd", "smth-moded",
}
SERVICE_BINS = {
    "systemd", "systemd-journald", "systemd-udevd", "systemd-logind",
    "dbus-daemon", "dbus-broker", "NetworkManager", "bluetoothd",
    "power-profiles-daemon", "udisksd", "pipewire", "wireplumber",
    "pipewire-pulse", "nft", "cron", "rsyslogd", "wpa_supplicant",
}


def read(path):
    try:
        return pathlib.Path(path).read_text(errors="replace")
    except OSError:
        return ""


def mib(kib):
    return round(kib / 1024.0, 1)


def meminfo():
    info = {}
    for line in read("/proc/meminfo").splitlines():
        key, _, rest = line.partition(":")
        if rest:
            info[key] = int(rest.split()[0])
    return info


def uptime():
    parts = read("/proc/uptime").split()
    return float(parts[0]) if parts else 0.0


def cmdline(pid):
    return [p for p in read(f"/proc/{pid}/cmdline").split("\0") if p]


def rollup(pid):
    """PSS, private and swap for one process; RSS fallback if unreadable."""
    out = {"pss_kib": 0, "private_kib": 0, "swap_kib": 0, "source": "smaps_rollup"}
    text = read(f"/proc/{pid}/smaps_rollup")
    if text:
        for line in text.splitlines():
            key, _, rest = line.partition(":")
            if key in ("Pss", "Private_Clean", "Private_Dirty", "Swap"):
                try:
                    value = int(rest.split()[0])
                except (IndexError, ValueError):
                    continue
                if key == "Pss":
                    out["pss_kib"] += value
                elif key == "Swap":
                    out["swap_kib"] += value
                else:
                    out["private_kib"] += value
    return out


def status(pid):
    out = {"rss_kib": 0, "vm_size_kib": 0, "threads": 0, "uid": None}
    for line in read(f"/proc/{pid}/status").splitlines():
        key, _, rest = line.partition(":")
        try:
            if key == "VmRSS":
                out["rss_kib"] = int(rest.split()[0])
            elif key == "VmSize":
                out["vm_size_kib"] = int(rest.split()[0])
            elif key == "Threads":
                out["threads"] = int(rest.split()[0])
            elif key == "Uid":
                out["uid"] = int(rest.split()[0])
        except (IndexError, ValueError):
            continue
    return out


def maps_has(pid, needle):
    for line in read(f"/proc/{pid}/maps").splitlines():
        if needle in line:
            return True
    return False


def user_name(uid):
    if uid is None:
        return "?"
    try:
        import pwd
        return pwd.getpwuid(uid).pw_name
    except (KeyError, ImportError):
        return str(uid)


def classify(comm, argv, gtk4):
    joined = " ".join(argv)
    base = os.path.basename(argv[0]) if argv else comm
    if comm in RUST_BINS or base in RUST_BINS:
        return "rust_core"
    if comm in NATIVE_BINS or base in NATIVE_BINS:
        return "native_c"
    if comm.startswith("python") or "python3" in base:
        return "python_smth" if SMTH_LIB in joined else "python_other"
    if gtk4:
        return "gtk4_client"
    if comm in ("labwc", "waybar", "swaybg", "swayidle", "fuzzel"):
        return "compositor"
    if comm in SESSION_BINS or base in SESSION_BINS:
        return "session"
    if comm in SERVICE_BINS:
        return "service"
    return "other"


def snapshot(phase):
    info = meminfo()
    procs = []
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        argv = cmdline(pid)
        if not argv:
            continue
        comm = read(f"/proc/{pid}/comm").strip() or f"pid{pid}"
        st = status(pid)
        if not st["rss_kib"] and not st["vm_size_kib"]:
            continue
        gtk4 = maps_has(pid, "libgtk-4.so")
        ru = rollup(pid)
        stat = read(f"/proc/{pid}/stat")
        try:
            ppid = int(stat[stat.rfind(")") + 2:].split()[1])
        except (IndexError, ValueError):
            ppid = 0
        procs.append({
            "pid": pid,
            "ppid": ppid,
            "name": comm,
            "cmdline": " ".join(argv)[:180],
            "user": user_name(st["uid"]),
            "rss_kib": st["rss_kib"],
            "pss_kib": ru["pss_kib"] or st["rss_kib"],
            "private_kib": ru["private_kib"],
            "swap_kib": ru["swap_kib"],
            "threads": st["threads"],
            "gtk4": gtk4,
            "group": classify(comm, argv, gtk4),
            "pss_source": "smaps_rollup" if ru["pss_kib"] else "rss_fallback",
        })

    groups = {}
    for proc in procs:
        group = groups.setdefault(proc["group"], {"count": 0, "rss_kib": 0, "pss_kib": 0,
                                                  "private_kib": 0, "swap_kib": 0})
        group["count"] += 1
        for key in ("rss_kib", "pss_kib", "private_kib", "swap_kib"):
            group[key] += proc[key]
    for group in groups.values():
        for key in ("rss_kib", "pss_kib", "private_kib", "swap_kib"):
            group[key] = mib(group[key])

    gtk4_total = sum(p["pss_kib"] for p in procs if p["gtk4"])
    python_total = sum(p["pss_kib"] for p in procs if p["group"] == "python_smth")
    total = info.get("MemTotal", 0)
    available = info.get("MemAvailable", 0)
    return {
        "phase": phase,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "uptime_seconds": round(uptime(), 1),
        "arch": os.uname().machine,
        "system": {
            "mem_total_mib": mib(total),
            "mem_available_mib": mib(available),
            "mem_used_mib": mib(total - available),
            "mem_used_percent": round((total - available) * 100.0 / total, 1) if total else 0.0,
            "mem_free_mib": mib(info.get("MemFree", 0)),
            "buffers_mib": mib(info.get("Buffers", 0)),
            "cached_mib": mib(info.get("Cached", 0)),
            "anon_mib": mib(info.get("AnonPages", 0)),
            "slab_mib": mib(info.get("Slab", 0) + info.get("SReclaimable", 0)),
            "swap_total_mib": mib(info.get("SwapTotal", 0)),
            "swap_used_mib": mib(info.get("SwapTotal", 0) - info.get("SwapFree", 0)),
            "load": read("/proc/loadavg").split()[:3],
            "cpu_count": os.cpu_count(),
        },
        "groups": groups,
        "gtk4_pss_mib": mib(gtk4_total),
        "python_helpers_pss_mib": mib(python_total),
        "process_count": len(procs),
        "all_process_rss_mib": mib(sum(p["rss_kib"] for p in procs)),
        "all_process_pss_mib": mib(sum(p["pss_kib"] for p in procs)),
        "processes": sorted(procs, key=lambda p: p["pss_kib"], reverse=True),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", default="manual")
    args = parser.parse_args()
    json.dump(snapshot(args.phase), sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
