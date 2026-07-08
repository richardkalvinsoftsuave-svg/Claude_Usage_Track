"""Test script to run OCR on all files in uploads directory."""
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from app.extraction.ocr_extractor import extract_usage

uploads_dir = Path("uploads")
images = list(uploads_dir.glob("*.png")) + list(uploads_dir.glob("*.jpg")) + list(uploads_dir.glob("*.jpeg"))

for img in sorted(images, key=lambda p: p.stat().st_mtime):
    print(f"\n==========================================")
    print(f"FILE: {img.name} (size: {img.stat().st_size} bytes)")
    try:
        res = extract_usage(img)
        print("Raw text:")
        print(res.get("raw_text"))
        print("\nExtracted fields:")
        print(res["extracted"].model_dump())
    except Exception as e:
        print(f"ERROR: {e}")
