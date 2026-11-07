import base64, sys
open("qr.png", "wb").write(base64.b64decode(open("qr.b64").read()))
try:
    from PIL import Image
except ImportError:
    sys.exit("NEED_PILLOW")
import zxingcpp
results = zxingcpp.read_bars(Image.open("qr.png"))
for r in results:
    print("FORMAT:", r.format)
    print("TEXT:", r.text)
