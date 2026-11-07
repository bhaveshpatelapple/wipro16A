"""wiring_check.py — one-shot: is the charger actually drawing power through the plug?

Combines the plug's live energy metering DPs into a plain-English verdict.
Physical logic:
    relay OFF                  -> laptop can never charge through the plug
    relay ON + current ~0 mA   -> nothing drawing -> charger not wired to plug (or absent)
    relay ON + current >200 mA -> charger IS connected and drawing main power
"""
import json
import os

import tinytuya

BASE = os.path.dirname(os.path.abspath(__file__))

records = json.load(open(os.path.join(BASE, "devices.json"), encoding="utf-8"))
rec = records[0]

dev = tinytuya.Device(
    rec["id"], address=None, local_key=rec["key"], version=rec.get("ver", "3.5")
)
st = dev.status()
dps = st.get("dps", {})

relay = dps.get("1")
rms = dps.get("18")   # current (mA in most Tuya metering plugs)
pwr = dps.get("19")   # power draw
vol = dps.get("20")   # voltage x0.1
e22 = dps.get("22")
other = {k: v for k, v in dps.items() if k not in ("1", "18", "19", "20", "22")}

print(f"relay(1)    = {relay}")
print(f"current(18) = {rms} mA")
print(f"power(19)   = {pwr}")
print(f"voltage(20) = {vol}  (x0.1 -> {round((vol or 0) / 10, 1)} V)")
print(f"dp22        = {e22}")
print(f"other dps   = {json.dumps(other)}")

if relay is False:
    verdict = "relay OFF -> plug cannot feed the laptop at all"
elif rms in (None, 0):
    verdict = "relay ON but ~0 current -> NOTHING drawing through the plug (charger not wired to it / not plugged in)"
elif rms >= 200:
    verdict = f"relay ON and {rms} mA flowing -> charger IS connected and drawing power"
else:
    verdict = f"relay ON, only {rms} mA -> idle/standby-level draw only"
print("VERDICT:", verdict)
