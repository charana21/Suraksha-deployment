#!/usr/bin/env python3
"""
Utility script to ensure required neural network weights are present in data/weights.
Downloads ShanghaiTech Part B (SHB_model.pth) for sparse crowd counting if missing.
"""

import os
import sys
from pathlib import Path

WEIGHTS_DIR = Path(__file__).resolve().parent.parent / "data" / "weights"
SHB_WEIGHTS_PATH = WEIGHTS_DIR / "SHB_model.pth"
SHB_GDRIVE_ID = "10HK42xC6fmOK-5lQfu-pTn6oAHYeRUhv"

def ensure_weights():
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    
    if SHB_WEIGHTS_PATH.exists() and SHB_WEIGHTS_PATH.stat().st_size > 80_000_000:
        print(f"[OK] SHB weights already present: {SHB_WEIGHTS_PATH} ({SHB_WEIGHTS_PATH.stat().st_size:,} bytes)")
        return True

    print(f"[INFO] Downloading SHB_model.pth to {SHB_WEIGHTS_PATH}...")
    try:
        import gdown
        url = f"https://drive.google.com/uc?id={SHB_GDRIVE_ID}"
        output = str(SHB_WEIGHTS_PATH)
        gdown.download(url, output, quiet=False)
    except Exception as e:
        print(f"[ERROR] Failed to download via gdown: {e}")
        return False

    if SHB_WEIGHTS_PATH.exists() and SHB_WEIGHTS_PATH.stat().st_size > 80_000_000:
        print(f"[SUCCESS] Downloaded SHB weights: {SHB_WEIGHTS_PATH.stat().st_size:,} bytes")
        return True
    else:
        print("[ERROR] Downloaded file is incomplete or missing")
        return False

if __name__ == "__main__":
    success = ensure_weights()
    sys.exit(0 if success else 1)
