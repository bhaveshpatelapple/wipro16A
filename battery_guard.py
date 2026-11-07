"""
battery_guard.py — AlDente-style battery care for Windows, using a Wipro
Wi-Fi switch as the mains "valve" on the laptop charger.

Idea inspired by AlDente (https://github.com/bhaveshpatelapple/
AlDente-Battery_Care_and_Monitoring): lithium batteries age least parked
between ~40% and ~80%. Instead of patching the charge controller like
AlDente does on macOS, we cut mains to the charger at HIGH and restore it
at LOW — the switch is the "charge limiter".

Usage:
    python battery_guard.py guard             # continuous loop (the product)
    python battery_guard.py guard --dry-run   # log decisions, don't touch switch
    python battery_guard.py status            # battery + switch state
    python battery_guard.py on | off          # manual switch control
"""

import argparse
import csv
import ctypes
import datetime as dt
import json
import pathlib
import sys
import time

import switch_control

BASE = pathlib.Path(__file__).resolve().parent
CONFIG = BASE / "config.json"
LOG = BASE / "battery_log.csv"


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),        # 0 = on battery, 1 = charging socket live
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),  # 0..100, 255 = unknown
        ("Reserved1", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def read_battery():
    sp = SYSTEM_POWER_STATUS()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sp)):
        return None, "unknown"
    pct = None if sp.BatteryLifePercent == 255 else sp.BatteryLifePercent
    return pct, ("mains" if sp.ACLineStatus == 1 else "battery")


def load_config():
    with open(CONFIG, "r", encoding="utf-8") as fh:
        return json.load(fh)


def log_event(action, msg, pct=None, src=None, to_csv=True):
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = [f"[{stamp}]", action,
             f"battery={pct}%" if pct is not None else "battery=?",
             src, msg]
    print(" | ".join(p for p in parts if p), flush=True)
    if not to_csv:
        return
    fresh = not LOG.exists()
    with LOG.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if fresh:
            writer.writerow(["timestamp", "battery_pct", "source", "action", "detail"])
        writer.writerow([
            dt.datetime.now().isoformat(timespec="seconds"),
            "" if pct is None else pct,
            src, action, msg,
        ])


def decide(cfg, pct, src):
    """Pick this tick's action, or None. Hysteresis = the two thresholds."""
    if pct is None:
        return None
    high = int(cfg.get("high_percent", 80))
    low = int(cfg.get("low_percent", 60))
    if src == "mains" and pct >= high:
        return ("off", f"charge limit hit ({pct}% >= {high}%)")
    if src == "battery" and pct <= low:
        return ("on", f"reserve hit ({pct}% <= {low}%)")
    return None


def guard_once(cfg, dry_run):
    pct, src = read_battery()
    if pct is None:
        log_event("skip", "battery status unavailable", to_csv=False)
        return
    act = decide(cfg, pct, src)
    if act is None:
        log_event("hold", "inside healthy band", pct=pct, src=src, to_csv=False)
        return
    goal, why = act
    if dry_run:
        log_event("dry-run", why, pct=pct, src=src, to_csv=False)
        return
    outcome = switch_control.turn(goal == "on",
                                  cfg.get("device_name_contains", "wipro"),
                                  cfg.get("device_ip"))
    log_event("switch-" + goal, why + " -> " + outcome, pct=pct, src=src)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["guard", "status", "on", "off"],
                        nargs="?", default="status")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    to_csv = bool(cfg.get("log_to_csv", True))

    if args.command == "status":
        pct, src = read_battery()
        ready = switch_control.device_ready()
        sw = switch_control.state(cfg.get("device_name_contains", "wipro"),
                                  cfg.get("device_ip")) if ready else None
        print(f"battery: {'?' if pct is None else str(pct) + '%'} on {src}"
              + f" | switch: {sw or 'unknown'}"
              + ("" if ready else " | tinytuya.json missing (wizard pending)"))
        return 0

    if args.command in ("on", "off"):
        if not switch_control.device_ready():
            print("tinytuya.json missing - finish the TinyTuya wizard first")
            return 2
        print(switch_control.turn(args.command == "on",
                                  cfg.get("device_name_contains", "wipro"),
                                  cfg.get("device_ip")))
        return 0

    period = int(cfg.get("period_seconds", 60))
    print("guard loop: cut mains at >="
          f" {cfg.get('high_percent', 80)}%, restore at <="
          f" {cfg.get('low_percent', 60)}%, every {period}s"
          + (" [dry run]" if args.dry_run else ""))
    if not switch_control.device_ready() and not args.dry_run:
        print("note: switch not armed yet (tinytuya.json pending); "
              "monitoring only until the wizard finishes")
    while True:
        try:
            guard_once(cfg, args.dry_run)
        except KeyboardInterrupt:
            print("guard stopped", flush=True)
            return 0
        except Exception as exc:
            log_event("error", f"{exc.__class__.__name__}: {exc}", to_csv=False)
        time.sleep(period)
    return 0


if __name__ == "__main__":
    sys.exit(main())
