# Simple Guide: Testing 40 RTSP Streams on Virtual GPU (vGPU)

A step-by-step walkthrough for simulating 40 live camera streams, feeding them into your analytics pipeline, and checking how the GPU handles the load.

---

## What This Does (In Plain Terms)

1. You take one sample video and turn it into **40 fake live camera streams**.
2. Your backend picks up all 40 streams and runs **AI detection (YOLOv8)** on them.
3. The system counts people, checks crowd density, tracks motion, and flags risk levels.
4. You watch the GPU to make sure it's handling all 40 streams smoothly.

---

## How It All Connects

```
Sample Video  →  RTSP Server (40 streams)  →  Backend Worker Pool
                                                     ↓
                                          GPU (YOLOv8 Detection)
                                                     ↓
                              People Count · Density · Motion · Risk Alerts
                                                     ↓
                                        Saved to Database + Live API
```

---

## Step 1 — Add a Sample Video

Put one CCTV or crowd video (MP4, ideally 1080p) into the `videos` folder:

```
crowd-backend/
 └── videos/
      └── test.mp4
```

💡 *Any footage of a crowd or station platform works well for testing.*

---

## Step 2 — Start the RTSP Server

This server will host all 40 fake camera streams.

```bash
docker-compose up -d rtsp-server
```

Confirm it's running:
```bash
docker ps | grep rtsp-server
```

---

## Step 3 — Create the 40 Simulated Streams

Pick whichever script matches your system:

**Windows or Linux (Python):**
```bash
python scripts/simulate_40_streams.py
```

**Linux/macOS/Git Bash:**
```bash
chmod +x scripts/simulate_40_streams.sh
./scripts/simulate_40_streams.sh
```

✅ **You'll know it worked when you see:**
```
[01/40] Publishing live stream -> rtsp://localhost:8554/cam_01
...
[40/40] Publishing live stream -> rtsp://localhost:8554/cam_40
[ACTIVE] All 40 streams are running live.
```

🎥 *Optional: preview one stream to double-check:*
```bash
ffplay rtsp://localhost:8554/cam_01
```

---

## Step 4 — Register the 40 Cameras in the Database

This tells your backend that 40 cameras now exist.

```bash
python scripts/seed_40_simulated_cameras.py
```

✅ **Expected result:**
```
SEEDING 40 SIMULATED RTSP CAMERAS
[01/40] Configured cam_sim_01 -> rtsp://rtsp-server:8554/cam_01
...
[40/40] Configured cam_sim_40 -> rtsp://rtsp-server:8554/cam_40
SUMMARY: Created: 40 | Updated: 0 | Total: 40
```

---

## Step 5 — Start the Backend & Let It Process Everything

```bash
python main.py
```
*(or, using Docker)*
```bash
docker-compose up -d crowdanalytics-backend
```

### What happens automatically:
| Component | Job |
|---|---|
| **RTSP Worker Pool** | Connects to all 40 camera streams |
| **GPU Batching** | Groups frames together for efficient GPU processing |
| **YOLOv8 on vGPU** | Detects people/objects in each frame |
| **Analytics Engine** | Counts people, measures density, tracks motion, raises alerts |

---

## Step 6 — Check Health Stats, Processed Frames & GPU Performance

While `python main.py` is running, query the **`/api/health`** endpoint or terminal metrics:

### 1. Live Health Endpoint (`GET http://localhost:8000/api/health`)
This endpoint provides real-time system metrics:
* **`total_frames`**: Total frames processed across streams.
* **`batches_processed`**: Total GPU inference batches completed.
* **`latency_ms`**: Average GPU inference latency (in ms).
* **`streams`**: Total active vs configured streams (e.g. `40 / 40`).
* **`gpu_status`**: VRAM memory used / total GB and GPU memory %.

Query via curl:
```bash
curl -X GET "http://localhost:8000/api/health"
```

---

## Alternative Setup: Single RTSP Stream vs 40 Streams

Both approaches work great:
1. **Multi-Stream Approach (40 URLs)**: Use `python scripts/simulate_40_streams.py` to publish `cam_01` to `cam_40`.
2. **Single RTSP Stream Approach**: Publish 1 stream (`rtsp://localhost:8554/mystream`) and assign this URL to all 40 camera entries in MongoDB.

---

## Quick Checklist

| # | Step | What to Run / Endpoint |
|---|---|---|
| 1 | Add a test video | Place file in `videos/test.mp4` |
| 2 | Start RTSP server | `tools/mediamtx.exe` (or `docker-compose up -d rtsp-server`) |
| 3 | Create streams | `python scripts/simulate_40_streams.py` |
| 4 | Register cameras in DB | `python scripts/seed_40_simulated_cameras.py` |
| 5 | Start the backend | `python main.py` |
| 6 | Check Health & Frame Stats | `GET http://localhost:8000/api/health` |

