import json

import tinytuya

DEV_ID = "d7c4c7fcb6f697a8f9ky6g"

scan = tinytuya.deviceScan()
info = scan.get(DEV_ID, {})
print("scan ip:", info.get("ip"), "| scan ver:", info.get("version"))

rec = json.load(open("devices.json"))[0]
key = rec["key"]
print("file key len:", len(key), "head/tail:", key[:2], key[-2:])

dev = tinytuya.Device(DEV_ID, address=info.get("ip"), local_key=key, version="3.4")
print("version in use:", dev.version)

res = dev.status()
print("status:")
print(json.dumps(res, indent=1)[:900])
