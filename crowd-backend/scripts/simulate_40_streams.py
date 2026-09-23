"""
Simulate 40 RTSP CCTV Camera Streams using MediaMTX and FFmpeg
"""
import os
import sys
import time
import subprocess
import signal
from pathlib import Path

VIDEO_PATH = Path(__file__).parent.parent / "videos" / "test.mp4"
RTSP_BASE_URL = os.getenv("RTSP_SERVER_URL", "rtsp://localhost:8554")
NUM_STREAMS = 40

processes = []

def cleanup(sig=None, frame=None):
    print("\n[STOPPING] Terminating all 40 RTSP publisher processes...")
    for p in processes:
        try:
            p.terminate()
        except Exception:
            pass
    print("[DONE] All streams stopped.")
    sys.exit(0)

def main():
    if not VIDEO_PATH.exists():
        print(f"[ERROR] Video file not found at: {VIDEO_PATH}")
        sys.exit(1)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print(f"==================================================")
    print(f" LAUNCHING {NUM_STREAMS} SIMULATED RTSP STREAMS")
    print(f" Source Video : {VIDEO_PATH}")
    print(f" Target Server: {RTSP_BASE_URL}")
    print(f"==================================================")

    for i in range(1, NUM_STREAMS + 1):
        stream_name = f"cam_{i:02d}"
        target_rtsp = f"{RTSP_BASE_URL}/{stream_name}"

        cmd = [
            "ffmpeg",
            "-re",
            "-stream_loop", "-1",
            "-i", str(VIDEO_PATH),
            "-c:v", "copy",
            "-an",
            "-f", "rtsp",
            target_rtsp
        ]

        try:
            p = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            processes.append(p)
            print(f"[{i:02d}/{NUM_STREAMS}] Publishing live stream -> {target_rtsp}")
        except FileNotFoundError:
            print("[ERROR] FFmpeg not found!")
            sys.exit(1)

        time.sleep(0.1)

    print("\n[ACTIVE] All 40 streams are running live.")
    print("Press Ctrl+C to stop all streams.")
    
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
