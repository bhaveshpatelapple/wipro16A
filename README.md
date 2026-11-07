# wipro16A — AlDente-style battery guard for Windows, driven by a Wipro 16A Wi-Fi smart plug

Wipro 16A smart plug automation — keep your laptop battery in its healthy 40–80% band.

Keep a laptop battery parked inside the healthy **40–80%** band by using a
Wipro (Tuya-based) Wi-Fi smart plug as an external "charge limiter": when the
battery reaches **80%** the plug cuts mains to the charger; when it drains to
**40%** the plug restores power. The plug both powers the charger and
energizes it again on schedule.

Everything is controlled **locally from the PC over the LAN** using
[TinyTuya](https://github.com/jasonacox/tinytuya) — no Tuya cloud, no Smart
Life app, and no macOS-only charge-controller patching (this is the AlDente
idea, built for Windows with hardware instead of drivers).

```
battery_guard.py  ──reads──>  Windows battery (GetSystemPowerStatus)
      │
      ├─ battery >= 80%  →  plug OFF   (charger cut, battery coasts)
      └─ battery <= 40%  →  plug ON    (charger restored, tops up to 80%)
                switches served by switch_control.py over TinyTuya (protocol 3.5)
```

## Repo contents (committed, safe files)

| File | Role |
|---|---|
| `battery_guard.py` | The product script — continuous guard loop, one-shot `status` / `on` / `off`, CSV logging |
| `switch_control.py` | TinyTuya local driver: loads device keys, auto-discovers the plug on the LAN, sends relay commands |
| `wiring_check.py` | One-shot diagnostic: is the charger actually drawing current through the plug (reads the plug's energy DPs: current mA, power, voltage) |
| `fetch_devices.py` | One-time cloud bootstrap: fetches the device's **local key** from the Tuya cloud and writes the runtime config files |
| `config.json.example` | Thresholds template — copy to `config.json` and fill in |

## Runtime files (also committed in the repo)

These hold secrets or personal data. **They are committed here by the owner's
explicit choice** — if you fork or reuse this project, replace them with your
own and rotate anything you find in commit history:

| File | Contains | How it's created |
|---|---|---|
| `config.json` | Your thresholds + device ID | copy of `config.json.example` |
| `tinytuya.json` | Tuya Client ID + Access Secret | written by `fetch_devices.py` |
| `api_secret.txt` | The Access Secret (one line) | you paste it from the Tuya IoT portal |
| `devices.json`, `snapshot.json` | Device ID, **local key**, protocol version | written by `fetch_devices.py` |
| `battery_log.csv` | Timestamped guard decisions | grows while the guard runs |

## One-time setup

1. **Hardware + app**: put the plug on Wi-Fi and pair it with *any* Tuya
   public app (**Smart Life** or **Tuya Smart**) — the plug is Tuya under the
   hood even though it's sold under the Wipro brand. The charger goes into
   the plug; the plug goes into the wall.

2. **Tuya IoT portal**: create a (free) project at
   [iot.tuya.com](https://iot.tuya.com), choose your data center region
   (India (`in`) for Wipro India devices), then link the Smart Life account
   that owns the plug (portal → project → *Devices → Link App Account*, scan
   the QR with the app). Grant the project API access (IoT Core + device
   management/query permissions). Note the project's **Access ID/Client ID**
   and **Access Secret**. The **Device ID** (`virtual-id`)
   is listed on the Devices tab.

3. **Store the secret**: save the Access Secret as `api_secret.txt`
   (single line) next to these scripts.

4. **Bootstrap the local key** (one cloud call, everything after is local):

   ```powershell
   python fetch_devices.py --api-key YOUR_CLIENT_ID --device-id YOUR_DEVICE_ID --region in
   ```

   This writes `tinytuya.json`, `devices.json`, `snapshot.json`.

5. **Configure**: copy `config.json.example` to `config.json` and set
   `device_id` (same virtual ID) and a lowercase substring of your plug's
   app-display name for `device_name_contains`.

6. **Test** (close the Smart Life app first — Tuya devices accept only one
   TCP connection at a time on port 6668):

   ```powershell
   python battery_guard.py status     # battery % + switch state
   python switch_control.py off       # relay clicks off
   python switch_control.py on        # relay back on
   python wiring_check.py             # verify real current flows (e.g. 850 mA = charging)
   ```

## Daily use

```powershell
python battery_guard.py guard          # the guard loop (Ctrl+C to stop)
python battery_guard.py guard --dry-run
python battery_guard.py status
python battery_guard.py on | off
```

Loop behaviour (hysteresis — no flapping between 40% and 80%):

| Battery | Action |
|---|---|
| climbs to ≥ 80% | plug **OFF** — mains cut |
| drains to ≤ 40% | plug **ON** — mains restored |
| in between | hold current state |

Every decision is printed and appended to `battery_log.csv`
(`timestamp, battery_pct, source, action, detail`).

### Start at login (optional)

```powershell
schtasks /create /tn "BatteryGuard" /tr "python C:\path\to\battery_guard.py guard" /sc onlogon
```

## Troubleshooting

- **`state: unknown` / error 914** — usually a stale local key or wrong
  protocol version. These plugs speak Tuya **protocol 3.5**, which TinyTuya
  1.20+ handles natively (`version='3.5'`). If the plug was recently
  re-paired in an app, its local key changed: re-run `fetch_devices.py`.
- **LED on but no charging** — run `wiring_check.py`: relay ON with ~0 mA
  means the charger lost power; 800+ mA with power ≈ your charger's wattage
  means it's wired and charging.
- **App conflicts** — keep Smart Life closed while scripts run, and leave
  `device_ip: null` so the driver auto-disdiscovers the plug each time.

## Security notes

- The **local key** in `devices.json` is the actual encryption key for LAN
  control — treat it like a password. Same for the Tuya **Access Secret**
  (it enables cloud API calls on the project).
- ⚠️ **In this repository these credential files are committed publicly by
  the owner's explicit choice** — do not reuse them. If you build on this
  project, use your own app/portal account and rotate everything you'd
  otherwise take from commit history.
- If you re-pair the plug, rerun `fetch_devices.py`; the old key becomes
  invalid automatically once stored nowhere else.

## Requirements

- Windows (uses `GetSystemPowerStatus` via `ctypes` for battery state)
- Python 3.9+
- `pip install tinytuya`
- A Tuya-based energy-metering smart plug (Wipro 16A confirmed; other Tuya
  plugs with DP1=switch should work too)
