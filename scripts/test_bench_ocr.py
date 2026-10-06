import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.perception.perception_engine import perception_engine
from PIL import Image, ImageDraw
import io

print("Using perception_engine.ocr_provider:")
ocr = perception_engine.ocr_provider
img = Image.new("RGB", (640, 360), (255, 255, 255))
d = ImageDraw.Draw(img)
d.text((20, 20), "VisionPilot Snapdragon Benchmark", fill=(0, 0, 0))
buf = io.BytesIO()
img.save(buf, format="PNG")
res = ocr.recognize(buf.getvalue())
print("Recognized regions:", len(res))
for r in res:
    print(" -", r.text)
