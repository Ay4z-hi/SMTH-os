#!/usr/bin/env python3
"""Enforce SMTH image and optional runtime performance budgets.

The ISO size policy (see docs/architecture/iso-budget.md) is no longer a single
hard 450 MiB limit:

  * 450 MiB is the PREFERRED target.
  * 700-900 MiB is acceptable when necessary.
  * 900 MiB is the MAXIMUM acceptable size.
  * Staying below 1 GiB is a further aspiration, but anything above 900 MiB
    already fails this gate.

An ISO above 450 MiB therefore no longer fails automatically: it prints a
warning and passes, up to 900 MiB. Only sizes above 900 MiB fail.
"""
import json, pathlib, sys
PREFERRED_ISO_MIB = 450
MAX_ACCEPTABLE_ISO_MIB = 900
LIMITS = {"idle_ram_mb": 350, "boot_seconds_ssd": 12, "boot_seconds_usb": 20,
          "start_menu_ms": 150, "settings_ms": 500, "cold_app_ms": 700, "idle_cpu_percent": 3}

def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: check_budgets.py ISO [runtime-metrics.json]")
    iso = pathlib.Path(sys.argv[1])
    size = iso.stat().st_size
    size_mib = size / 1024 / 1024
    print(f"ISO size: {size_mib:.1f} MiB (preferred target {PREFERRED_ISO_MIB} MiB, "
          f"maximum acceptable {MAX_ACCEPTABLE_ISO_MIB} MiB)")
    if size_mib > MAX_ACCEPTABLE_ISO_MIB:
        raise SystemExit(f"FAIL: ISO {size_mib:.1f} MiB exceeds the maximum acceptable "
                         f"size of {MAX_ACCEPTABLE_ISO_MIB} MiB")
    if size_mib > PREFERRED_ISO_MIB:
        print(f"WARNING: ISO {size_mib:.1f} MiB is above the preferred target of "
              f"{PREFERRED_ISO_MIB} MiB but within the acceptable range "
              f"(<= {MAX_ACCEPTABLE_ISO_MIB} MiB).")
    else:
        print(f"OK: ISO is within the preferred target of {PREFERRED_ISO_MIB} MiB.")
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
