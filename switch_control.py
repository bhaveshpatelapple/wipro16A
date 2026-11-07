"""
switch_control.py — local control of the Wipro Wi-Fi switch (Tuya protocol)
via TinyTuya. Reads device keys from tinytuya.json (produced once by the
TinyTuya setup wizard); after that all commands stay on the LAN.

CLI:
    python switch_control.py status
    python switch_control.py on
    python switch_control.py off
"""

import json
import pathlib
import sys

import tinytuya

BASE = pathlib.Path(__file__).resolve().parent
# The wizard writes credentials to tinytuya.json, device keys to devices.json
# and (optionally) polled statuses incl. IPs to snapshot.json. Accept all.
FILES = ("devices.json", "tinytuya.json", "snapshot.json")

_device = None  # cached live connection


def _load_snapshot():
    records = {}

    def iter_devices(obj):
        if isinstance(obj, list):
            yield from (d for d in obj if isinstance(d, dict))
        elif isinstance(obj, dict):
            for k in ("data", "devices"):
                sub = obj.get(k)
                if isinstance(sub, list):
                    yield from (d for d in sub if isinstance(d, dict))

    for fname in FILES:
        path = BASE / fname
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for d in iter_devices(data):
            rid = d.get("id") or d.get("device_id") or d.get("gwId")
            if not rid:
                continue
            rec = records.setdefault(rid, {})
            rec.setdefault("id", rid)
            for field in ("key", "name", "ver", "ip"):
                val = d.get(field)
                if val and rec.get(field) != val:
                    rec[field] = val
    return list(records.values())


def _pick_device(name_contains="wipro"):
    devs = _load_snapshot() or []
    if not devs:
        return None
    needle = (name_contains or "").strip().lower()
    if needle:
        for dev in devs:
            if needle in (dev.get("name") or "").lower():
                return dev
    for dev in devs:
        name = (dev.get("name") or "").lower()
        if any(hint in name for hint in ("switch", "plug", "socket")):
            return dev
    return devs[0]


def _resolve_ip(pref_ip):
    """Best-effort LAN lookup of the device's current IP."""
    try:
        found = tinytuya.deviceScan()
    except Exception:
        return None
    if pref_ip:
        return pref_ip
    for info in found.values():
        if info.get("ip"):
            return info["ip"]
    return None


def device_ready():
    return _pick_device() is not None


def device_id():
    rec = _pick_device()
    return rec.get("id") if rec else None


def find_device(name_contains="wipro", pref_ip=None):
    rec = _pick_device(name_contains)
    if not rec:
        return None
    dev_id = rec.get("id") or rec.get("device_id")
    key = rec.get("key")
    if not dev_id or not key:
        return None
    ip = pref_ip or _resolve_ip(pref_ip)
    version = rec.get("ver") or "3.5"
    return tinytuya.Device(dev_id, address=ip, local_key=key, version=version)


def turn(on, name_contains="wipro", pref_ip=None):
    global _device
    try:
        if _device is None:
            _device = find_device(name_contains, pref_ip)
        if _device is None:
            return "no-device (tinytuya.json missing or unusable)"
        res = _device.set_status(True if on else False)  # DP1 = relay on 1-gang switches
        if isinstance(res, dict) and res.get("Error"):
            _device = None  # force reconnect next time
            return f"error: {res['Error']}"
        return "commanded ON" if on else "commanded OFF"
    except Exception as exc:
        _device = None
        return f"error: {exc.__class__.__name__}: {exc}"


def state(name_contains="wipro", pref_ip=None):
    try:
        global _device
        if _device is None:
            _device = find_device(name_contains, pref_ip)
        if _device is None:
            return None
        st = _device.status()
        dps = st.get("dps", {}) if isinstance(st, dict) else {}
        one = dps.get("1")
        if one is None:
            return None
        return "on" if one in (True, "1", "on", 1) else "off"
    except Exception:
        _device = None
        return None


if __name__ == "__main__":
    if not device_ready():
        print("tinytuya.json not found/usable - run: python -m tinytuya wizard")
        sys.exit(2)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "on":
        print(turn(True))
    elif cmd == "off":
        print(turn(False))
    else:
        print("switch state:", state() or "unknown")
