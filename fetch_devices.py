"""
fetch_devices.py — one-time cloud bootstrap (wizard-free): pulls the device
list — including each device's local key — from the Tuya cloud using a Tuya
IoT Platform project's Client ID + Access Secret, then writes the same
tinytuya.json / devices.json / snapshot.json files the TinyTuya setup wizard
would have produced. One cloud call only; after this, all control stays on
the LAN (no cloud dependency at runtime).

Re-run it any time the local key changes (i.e. after re-pairing the plug to a
different app account) — the fresh key is fetched from the cloud again.

Credential resolution (first match wins):
  CLI:  --api-key / --device-id / --region
  Env:  TUYA_API_KEY / TUYA_DEVICE_ID / TUYA_REGION / TUYA_API_SECRET
  Files (from a previous run): tinytuya.json (client id etc.) +/or
         api_secret.txt (Access Secret, one line, no spaces)

Get the values: Tuya IoT Platform (iot.tuya.com) -> your project -> overview
shows "Access ID/Client ID" and "Access Secret/Client Secret"; the device ID
is visible in the IoT platform Devices list (e.g. from the linked Smart Life
app account).

Run:  python fetch_devices.py
"""

import argparse
import json
import os

import tinytuya

HERE = os.path.dirname(os.path.abspath(__file__))


def _first(*vals):
    for v in vals:
        if v:
            return v
    return None


def main():
    ap = argparse.ArgumentParser(description="Bootstrap TinyTuya config from the Tuya cloud")
    ap.add_argument("--api-key", help="Tuya IoT Client ID (Access ID)")
    ap.add_argument("--device-id", help="Device virtual ID of the plug")
    ap.add_argument("--region", help="Data center region: us / eu / in / cn")
    args = ap.parse_args()

    cfg = {}
    cfg_path = os.path.join(HERE, "tinytuya.json")
    if os.path.exists(cfg_path):
        try:
            cfg = json.load(open(cfg_path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cfg = {}

    api_key = _first(args.api_key, os.environ.get("TUYA_API_KEY"), cfg.get("apiKey"))
    device_id = _first(args.device_id, os.environ.get("TUYA_DEVICE_ID"), cfg.get("apiDeviceID"))
    region = (_first(args.region, os.environ.get("TUYA_REGION"), cfg.get("device_region"),
                     cfg.get("apiRegion")) or "in").lower()

    secret = _first(os.environ.get("TUYA_API_SECRET"), cfg.get("apiSecret"))
    secret_path = os.path.join(HERE, "api_secret.txt")
    if not secret and os.path.exists(secret_path):
        secret = open(secret_path, encoding="utf-8").read().strip()

    missing = [n for n, v in (("api-key", api_key), ("device-id", device_id),
                              ("api-secret", secret)) if not v]
    if missing:
        ap.error("missing credentials: %s — pass CLI args, env vars, or store "
                 "api_secret.txt / tinytuya.json" % ", ".join(missing))

    cloud = tinytuya.Cloud(apiRegion=region, apiKey=api_key, apiSecret=secret,
                           apiDeviceID=device_id)

    # Wizard-style config (what TinyTuya stores after its setup wizard)
    config = {
        "apiKey": api_key,
        "apiSecret": secret,
        "device_region": region,
        "apiDeviceID": device_id,
    }
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print("wrote tinytuya.json")

    devs = cloud.getdevices(verbose=False)
    if not isinstance(devs, list) or not devs:
        print("getdevices() returned no usable list:", type(devs).__name__)
        raise SystemExit(1)

    # Local protocol truth wins: deviceScan reports the real protocol (e.g. 3.5)
    try:
        scan = tinytuya.deviceScan()
    except Exception:
        scan = {}

    slim = []
    for d in devs:
        rec = {
            "id": d.get("id"),
            "name": d.get("name"),
            "key": d.get("key") or d.get("local_key"),
            "status": None,
            "ver": d.get("ver") or d.get("local_version") or "3.3",
        }
        local = scan.get(rec["id"], {}) if isinstance(scan, dict) else {}
        if local.get("version"):
            rec["ver"] = local["version"]
        slim.append(rec)
    with open(os.path.join(HERE, "devices.json"), "w", encoding="utf-8") as f:
        json.dump(slim, f, indent=2)
    print(f"wrote devices.json ({len(slim)} devices)")

    for d in slim:
        if d.get("name"):
            print(f"LOCAL KEY FOUND for '{d['name']}': len={len(d['key'] or '')} ver={d['ver']}")

    # snapshot.json in wizard shape (switch_control merges it: key/name/ver)
    try:
        snap = json.load(open(os.path.join(HERE, "snapshot.json"), encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        snap = {"data": []}
    snap.setdefault("data", [])
    for rec in slim:
        if not any(x.get("id") == rec["id"] for x in snap["data"]):
            rec2 = {k: v for k, v in rec.items() if k != "status"}
            snap["data"].append(rec2)
    with open(os.path.join(HERE, "snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2)
    print("wrote snapshot.json (merged)")


if __name__ == "__main__":
    main()
