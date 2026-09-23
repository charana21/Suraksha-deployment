"""
Video processing service
"""
import cv2
import os
import json
import time
import logging
import subprocess
import shutil
from typing import Any, Dict, List, Optional, Tuple
from config.config import get_settings
from services.crowd_analyzer import CrowdAnalyzer
from utils.visualization import visualize_analysis

logger = logging.getLogger(__name__)

# Global job tracking
processing_jobs: Dict[str, Dict[str, Any]] = {}


class VideoProcessor:
    """Process videos with crowd analysis"""

    def __init__(self):
        self.settings = get_settings()
        self.analyzer = None

    @staticmethod
    def _open_capture(video_path: str) -> Tuple[cv2.VideoCapture, float, int, int, int]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise Exception("Cannot open video")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info("[INFO] Processing %dx%d @ %sfps (%d frames)", width, height, fps, total_frames)
        return cap, fps, width, height, total_frames

    def _analyze_and_write_frame(self, frame, frame_num: int, fps: float, out) -> Optional[Dict[str, Any]]:
        try:
            result = self.analyzer.analyze_frame(frame)
            frame_entry = {
                'frameNumber': frame_num,
                'timestamp': frame_num / fps,
                'peopleCount': result['people_count'],
                'densityAvg': result['density_avg'],
                'densityMax': result['density_max'],
                'motionIntensity': result['motion_intensity'],
                'zones': [
                    {
                        'id': z['id'],
                        'name': z['name'],
                        'people_count': z['people_count'],
                        'density_level': z['density_level'],
                        'risk_level': z['risk_level'],
                        'risk_score': z['risk_score']
                    }
                    for z in result['zones'].values()
                ]
            }

            vis_frame = visualize_analysis(
                frame,
                result['detections'],
                result['zones'],
                result['density_map'],
                frame_num
            )
            out.write(vis_frame)
            return frame_entry
        except Exception:
            logger.warning("[WARN] Frame %d error", frame_num, exc_info=True)
            out.write(frame)
            return None

    def _process_frames(
        self, job_id: str, cap: cv2.VideoCapture, out, fps: float, total_frames: int
    ) -> Tuple[int, List[Dict[str, Any]]]:
        frame_num = 0
        frame_analytics: List[Dict[str, Any]] = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_num += 1

            # Update progress (0-80% for processing)
            if total_frames > 0:
                processing_jobs[job_id]["progress"] = min(int((frame_num / total_frames) * 80), 80)

            entry = self._analyze_and_write_frame(frame, frame_num, fps, out)
            if entry is not None:
                frame_analytics.append(entry)

        return frame_num, frame_analytics

    @staticmethod
    def _reencode_with_ffmpeg(temp_path: str, output_path: str) -> None:
        logger.info("[INFO] Converting to browser-compatible format with FFmpeg...")

        if not shutil.which('ffmpeg'):
            logger.error("[ERROR] FFmpeg not found!")
            logger.warning("[WARN] Using non-converted video - may not play in browser")
            shutil.move(temp_path, output_path)
            return

        ffmpeg_cmd = [
            'ffmpeg',
            '-i', temp_path,
            '-c:v', 'libx264',         # H.264 codec
            '-preset', 'medium',        # Good compression
            '-crf', '23',               # High quality
            '-pix_fmt', 'yuv420p',     # Universal color format
            '-movflags', '+faststart',  # Enable streaming
            '-y',                       # Overwrite
            output_path
        ]

        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            logger.error("[ERROR] FFmpeg failed: %s", result.stderr)
            shutil.move(temp_path, output_path)
            return

        logger.info("[SUCCESS] FFmpeg conversion complete")
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info("[INFO] Temporary file removed")

    @staticmethod
    def _verify_output(output_path: str) -> None:
        if not os.path.exists(output_path):
            raise Exception("Output video not created")

        file_size = os.path.getsize(output_path)
        if file_size == 0:
            raise Exception("Output video is empty")

        logger.info("[SUCCESS] Final video: %s bytes", f"{file_size:,}")

    def _save_analytics(
        self, job_id: str, frame_num: int, fps: float, width: int, height: int, frame_analytics: List[Dict[str, Any]]
    ) -> None:
        analytics_path = os.path.join(self.settings.output_dir, f"{job_id}_analytics.json")

        with open(analytics_path, 'w') as f:
            json.dump({
                'metadata': {
                    'jobId': job_id,
                    'totalFrames': frame_num,
                    'fps': fps,
                    'width': width,
                    'height': height
                },
                'frames': frame_analytics
            }, f)

        logger.info("[INFO] Saved analytics: %d frames", len(frame_analytics))

    def process_video_task(self, job_id: str, video_path: str, output_path: str):
        """
        Process video with frame-by-frame analytics
        MUST include FFmpeg conversion for browser compatibility
        """
        try:
            # Initialize analyzer if not done
            if self.analyzer is None:
                self.analyzer = CrowdAnalyzer()

            processing_jobs[job_id]['status'] = 'processing'
            processing_jobs[job_id]['progress'] = 5

            cap, fps, width, height, total_frames = self._open_capture(video_path)

            # ==========================================
            # STEP 1: Process with OpenCV (TEMPORARY)
            # ==========================================
            temp_path = output_path.replace('.mp4', '_temp.mp4')

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(temp_path, fourcc, fps, (width, height))

            if not out.isOpened():
                cap.release()
                raise Exception("Cannot create video writer")

            frame_num, frame_analytics = self._process_frames(job_id, cap, out, fps, total_frames)

            cap.release()
            out.release()
            logger.info("[INFO] OpenCV processing complete: %d frames", frame_num)

            # ==========================================
            # STEP 2: FFmpeg Re-encode (CRITICAL!)
            # ==========================================
            processing_jobs[job_id]["progress"] = 85
            self._reencode_with_ffmpeg(temp_path, output_path)

            # ==========================================
            # STEP 3: Verify and Save Analytics
            # ==========================================
            processing_jobs[job_id]["progress"] = 95
            self._verify_output(output_path)
            self._save_analytics(job_id, frame_num, fps, width, height, frame_analytics)

            processing_jobs[job_id].update({
                'status': 'complete',
                'progress': 100,
                'result': {
                    'analyticsUrl': f'/api/analytics/{job_id}',
                    'frameCount': frame_num,
                    'processingTime': time.time()
                }
            })

            logger.info("[SUCCESS] Job %s complete!", job_id)

        except Exception as e:
            logger.exception("[ERROR] Job %s failed", job_id)
            processing_jobs[job_id].update({
                'status': 'error',
                'error': str(e)
            })