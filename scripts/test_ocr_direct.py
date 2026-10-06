import sys
import os
from pathlib import Path
import io

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.perception.ocr.local_ocr import LocalOCRProvider
from PIL import Image, ImageDraw

print("A. Creating 640x360 Image")
img = Image.new("RGB", (640, 360), (255, 255, 255))
d = ImageDraw.Draw(img)
for i, line in enumerate(["VisionPilot", "Snapdragon", "Benchmark", "Local OCR"]):
    d.text((20, 20 + i*40), line, fill=(0, 0, 0))
buf = io.BytesIO()
img.save(buf, format="PNG")
b = buf.getvalue()

print("B. Instantiating LocalOCRProvider")
ocr = LocalOCRProvider()
print("C. Calling recognize")
res = ocr.recognize(b)
print("D. Finished recognize, count:", len(res))
