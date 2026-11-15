#!/usr/bin/env python3
"""Enforce SMTH image and optional runtime performance budgets."""
import json, pathlib, sys
MAX_ISO = 450 * 1024 * 1024
LIMITS = {"idle_ram_mb": 350, "boot_seconds_ssd": 12, "boot_seconds_usb": 20,
          "start_menu_ms": 150, "settings_ms": 500, "cold_app_ms": 700, "idle_cpu_percent": 3}

def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: check_budgets.py ISO [runtime-metrics.json]")
    iso = pathlib.Path(sys.argv[1])
    size = iso.stat().st_size
    print(f"ISO size: {size / 1024 / 1024:.1f} MiB (limit 450 MiB)")
    if size > MAX_ISO:
        raise SystemExit("FAIL: ISO exceeds 450 MiB budget")
    if len(sys.argv) > 2:
        metrics = json.loads(pathlib.Path(sys.argv[2]).read_text())
        failed = []
        for key, limit in LIMITS.items():
            if key not in metrics:
                failed.append(f"missing metric: {key}")
            elif metrics[key] > limit:
                failed.append(f"{key}={metrics[key]} exceeds {limit}")
        if failed:
            raise SystemExit("FAIL runtime budgets:\n" + "\n".join(failed))
    else:
        print("Runtime budgets: UNMEASURED (provide runtime-metrics.json to enforce them)")
    print("PASS image size budget")

if __name__ == "__main__":
    main()
