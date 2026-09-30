"""
Main crowd analysis service

Supports three modes:
1. Standalone mode: Each CrowdAnalyzer creates its own models (legacy)
2. Shared pool mode: Uses SharedModelPool for 95% GPU memory reduction
3. Batched inference mode: Uses BatchedInferenceService for production-grade performance
"""
import cv2
import numpy as np
import time
from typing import Dict, List, Tuple,Optional
from collections import deque
from models.model_wrapper import CrowdCountingModelWrapper, SharedModelPool
from utils.image_processing import FrameEnhancer, TemporalSmoother
from utils.perspective import CalibrationManager
from config.config import get_settings


class CrowdAnalyzer:
    """Complete crowd analysis with risk assessment"""

    def __init__(
        self,
        model_wrapper: CrowdCountingModelWrapper = None,
        use_shared_pool: bool = False,
        use_batched_inference: bool = None  # None = auto-detect from settings
    ):
        """
        Initialize CrowdAnalyzer.

        Args:
            model_wrapper: Optional pre-initialized model wrapper (legacy)
            use_shared_pool: If True, use SharedModelPool instead of creating new models.
                            This reduces GPU memory from N×150MB to just 150MB total.
            use_batched_inference: If True, use BatchedInferenceService for production-grade
                                  batching. If None, auto-detects from settings.use_batched_inference.
        """
        self.settings = get_settings()
        self.use_shared_pool = use_shared_pool

        # Auto-detect batched inference from settings if not specified
        if use_batched_inference is None:
            use_batched_inference = self.settings.use_batched_inference
        self.use_batched_inference = use_batched_inference

        # Batched inference service reference (lazy init)
        self._batched_service = None

        # Load model (only if not using batched inference)
        if use_batched_inference:
            # Batched inference mode - service handles model access
            self.model = None
            print("[INFO] CrowdAnalyzer using BatchedInferenceService (production mode)")
        elif use_shared_pool:
            # Use shared model pool (memory-efficient for multiple streams)
            self.model = SharedModelPool.get_instance()
            if not self.model.is_initialized:
                print("[INFO] SharedModelPool not initialized, initializing now...")
                self.model.initialize(
                    yolo_path=self.settings.yolo_model_path,
                    device=self.settings.device,
                    density_model=self.settings.density_model,
                    density_gaussian_sigma=self.settings.density_gaussian_sigma,
                    pet_weights_path=self.settings.pet_weights_path,
                    pet_conf_threshold=self.settings.pet_conf_threshold,
                    pet_nms_distance=self.settings.pet_nms_distance
                )
            print("[INFO] CrowdAnalyzer using SharedModelPool (memory-efficient mode)")
        elif model_wrapper is None:
            # Legacy: create dedicated models for this analyzer
            print("[INFO] Initializing CrowdAnalyzer with dedicated models...")
            self.model = CrowdCountingModelWrapper(
                yolo_path=self.settings.yolo_model_path,
                device=self.settings.device,
                density_model=self.settings.density_model,
                density_gaussian_sigma=self.settings.density_gaussian_sigma,
                pet_weights_path=self.settings.pet_weights_path,
                pet_conf_threshold=self.settings.pet_conf_threshold,
                pet_nms_distance=self.settings.pet_nms_distance
            )
        else:
            self.model = model_wrapper

        # Components
        self.enhancer = FrameEnhancer()
        self.smoothers = {}  # Temporal smoother for full-frame zone

        # Perspective calibration manager (for FOB lane-based analysis)
        self._calibration_manager = None  # Lazy init

        # Motion tracking
        self.prev_gray = None
        self.flow_history = deque(maxlen=15)

        # Frame counter
        self.frame_count = 0
        self._last_frame_count = 0  # Track previous frame count for regime estimation

        # Pixel-based density: cached YOLO head bbox sizes per camera
        self._cached_head_sizes = {}  # {camera_id: median_head_bbox_px²}
        self._ema_density = {}  # {camera_id: EMA-smoothed density}

        # PET skip interval: per-camera frame counters + cached PET results
        self._pet_frame_counters = {}   # {camera_id: int}
        self._cached_pet_results = {}   # {camera_id: dict} — last full PET inference result

        # Cache for optical flow (computed every N frames for performance)
        self._cached_flow = None
        self._cached_flow_mag = 0.0
        self._cached_divergence = None

        # ROI mask cache for optical flow (eliminates train/background interference)
        self._flow_roi_mask = None
        self._flow_roi_mask_key = None

        # Meters-per-pixel conversion cache (for real-world motion speed)
        self._meters_per_pixel = None
        self._meters_per_pixel_key = None
        self._last_flow_time = None
        self._zone_roi_contour = None
        self._zone_roi_contour_key = None
        self._zone_roi_mask = None
        self._zone_roi_mask_key = None

        # DIS Optical Flow (10x faster than Farneback on CPU, drops CPU spikes)
        try:
            self._dis_flow = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
        except Exception:
            self._dis_flow = None

    def _get_flow_roi_mask(
        self,
        flow_shape: Tuple[int, int],
        camera_config: Optional[Dict]
    ) -> Optional[np.ndarray]:
        """Get cached ROI mask at optical flow resolution.

        Returns None if no ROI is configured (caller skips masking).
        """
        from utils.perspective import create_roi_mask, get_roi_signature

        roi_data = camera_config.get('roi') if camera_config else None
        if not roi_data or not roi_data.get('points'):
            return None

        roi_pts = roi_data['points']
        flow_h, flow_w = flow_shape
        roi_fw = int(roi_data.get('frame_width') or flow_w)
        roi_fh = int(roi_data.get('frame_height') or flow_h)
        roi_sig = get_roi_signature(roi_pts)

        cache_key = (
            flow_shape, roi_fw, roi_fh, roi_sig
        )

        if (
            self.settings.roi_cache_enabled
            and self._flow_roi_mask is not None
            and self._flow_roi_mask_key == cache_key
        ):
            return self._flow_roi_mask

        mask = create_roi_mask(flow_shape, roi_pts, roi_fw, roi_fh)
        if self.settings.roi_cache_enabled:
            self._flow_roi_mask = mask
            self._flow_roi_mask_key = cache_key
        return mask

    def _resolve_area_m2(
        self,
        camera_config: Optional[Dict],
        frame_w: int,
        frame_h: int,
        camera_id: Optional[str] = None
    ) -> float:
        """Resolve visible area in m² from pixel-mode head scale, DB calibration, or JSON fallback."""
        if self.settings.density_mode == "pixel":
            head_size_px = self._cached_head_sizes.get(camera_id or "_default")
            if head_size_px and head_size_px > 0:
                px_per_m2 = head_size_px / self.settings.pixel_head_reference_m2
                return (frame_w * frame_h) / px_per_m2
            return 150.0  # cold-start fallback for motion

        if camera_config and camera_config.get('area_m2'):
            return camera_config['area_m2']

        calibration = self._get_calibration_manager().get_calibration(camera_id or "_default_fob")
        return calibration.visible_area_m2

    @staticmethod
    def _resolve_roi_pixel_area(
        camera_config: Optional[Dict],
        frame_w: int,
        frame_h: int
    ) -> Tuple[Optional[List], float, Optional[Tuple]]:
        """Resolve ROI points (scaled to frame) and pixel area, plus a cache-key fragment."""
        from utils.perspective import get_roi_signature

        roi_data = camera_config.get('roi') if camera_config else None
        if not (roi_data and roi_data.get('points')):
            return None, float(frame_w * frame_h), (None,)

        roi_pts = roi_data['points']
        roi_fw = roi_data.get('frame_width', frame_w)
        roi_fh = roi_data.get('frame_height', frame_h)
        roi_sig = get_roi_signature(roi_pts)

        scale_x = frame_w / roi_fw if roi_fw else 1.0
        scale_y = frame_h / roi_fh if roi_fh else 1.0
        scaled_pts = np.array(
            [[p[0] * scale_x, p[1] * scale_y] for p in roi_pts],
            dtype=np.float32,
        )
        roi_pixel_area = float(cv2.contourArea(scaled_pts))
        return roi_pts, roi_pixel_area, (roi_fw, roi_fh, roi_sig)

    def _get_meters_per_pixel(
        self,
        camera_config: Optional[Dict],
        frame_w: int,
        frame_h: int,
        camera_id: Optional[str] = None
    ) -> Optional[float]:
        """Compute cached uniform meters-per-pixel from area_m2 and ROI pixel area.

        Uses sqrt(area_m2 / roi_pixel_area) — uniform approximation without
        perspective projection.  Still far more meaningful than arbitrary units.

        Returns None only when area_m2 is unavailable.
        """
        import math

        area_m2 = self._resolve_area_m2(camera_config, frame_w, frame_h, camera_id)
        if area_m2 <= 0:
            return None

        roi_pts, roi_pixel_area, roi_key_part = self._resolve_roi_pixel_area(camera_config, frame_w, frame_h)
        cache_key = (area_m2, frame_w, frame_h) + roi_key_part

        if (
            self.settings.roi_cache_enabled
            and self._meters_per_pixel is not None
            and self._meters_per_pixel_key == cache_key
        ):
            return self._meters_per_pixel

        if roi_pixel_area <= 0:
            return None

        m_per_px = math.sqrt(area_m2 / roi_pixel_area)

        if self.settings.roi_cache_enabled:
            self._meters_per_pixel = m_per_px
            self._meters_per_pixel_key = cache_key
        return m_per_px

    @staticmethod
    def _pet_spatial_metrics(
        density_map: Optional[np.ndarray],
        final_count: int,
        roi_area_px: float
    ) -> float:
        """Crowded fraction: % of ROI pixels exceeding 30% of peak normalized density."""
        if density_map is None or density_map.size == 0:
            return 0.0

        dmap_sum = float(np.sum(density_map))
        if dmap_sum <= 0:
            return 0.0

        normalized = density_map * (final_count / dmap_sum)
        peak_ppx = float(np.max(normalized))
        if peak_ppx <= 0:
            return 0.0

        high_thresh = peak_ppx * 0.3
        high_density_pixels = float(np.count_nonzero(normalized > high_thresh))
        return high_density_pixels / roi_area_px

    def _update_cached_head_size(
        self,
        cam_key: str,
        detections: List[Dict],
        head_count: int,
        yolo_avg_confidence: float
    ) -> None:
        """Refresh cached median YOLO head bbox area when detections are reliable."""
        reliable = (
            self.settings.pixel_head_min_detections <= head_count <= self.settings.pixel_head_max_detections
            and yolo_avg_confidence >= self.settings.pixel_head_min_confidence
        )
        if not reliable:
            return

        bbox_areas = [
            (d['bbox'][2] - d['bbox'][0]) * (d['bbox'][3] - d['bbox'][1])
            for d in detections
        ]
        new_median = float(np.median(bbox_areas))
        prev = self._cached_head_sizes.get(cam_key)
        if prev is not None:
            self._cached_head_sizes[cam_key] = 0.1 * new_median + 0.9 * prev
        else:
            self._cached_head_sizes[cam_key] = new_median

    def _estimate_pixel_density(
        self,
        density_map: Optional[np.ndarray],
        detections: List[Dict],
        head_count: int,
        final_count: int,
        roi_contour: Optional[np.ndarray],
        h: int,
        w: int,
        camera_id: Optional[str],
        yolo_avg_confidence: float
    ) -> float:
        """PET-driven pixel density with optional YOLO head calibration.

        Layer 1 (PET — primary, always available):
          Normalize PET density map so sum = final_count, then extract
          spatial metrics: peak density, crowded fraction.

        Layer 2 (YOLO — calibrator, cached from sparse periods):
          Median head bbox area → pixels_per_m² → converts pixel density
          to real people/m².  Cached per camera for dense-crowd periods
          when YOLO detection quality drops.

        Returns density on the same 0-5+ scale as people/m² so existing
        risk thresholds and alert logic work unchanged.
        """
        if final_count == 0:
            return 0.0

        # --- ROI pixel area (tracks excluded if ROI set) ---
        if roi_contour is not None:
            roi_area_px = max(float(cv2.contourArea(roi_contour)), 1.0)
        else:
            roi_area_px = float(h * w)

        # --- Layer 1: PET density map spatial metrics ---
        crowded_fraction = self._pet_spatial_metrics(density_map, final_count, roi_area_px)

        # --- Layer 2: YOLO head scale calibration ---
        cam_key = camera_id or "_default"
        self._update_cached_head_size(cam_key, detections, head_count, yolo_avg_confidence)
        head_size_px = self._cached_head_sizes.get(cam_key)

        # --- Combine layers ---
        if head_size_px and head_size_px > 0:
            # YOLO scale available → real people/m²
            px_per_m2 = head_size_px / self.settings.pixel_head_reference_m2

            # Average density (count-based — stable and physically correct)
            avg_density = (final_count / roi_area_px) * px_per_m2
        else:
            # No YOLO scale (cold start or dense crowd without prior cache)
            # Count-based signal is reliable; spatial concentration is secondary
            # to prevent PET hotspots from inflating density in moderate crowds
            count_signal = min(final_count / 50.0, 5.0)
            spatial_signal = min(crowded_fraction * 8.0, count_signal * 1.5)
            avg_density = 0.7 * count_signal + 0.3 * spatial_signal

        return max(min(avg_density, 9.0), 0.0)

    def _get_zone_roi_contour(
        self,
        frame_shape: Tuple[int, int],
        camera_config: Optional[Dict]
    ) -> Optional[np.ndarray]:
        """Get cached ROI contour for current frame resolution."""
        from utils.perspective import build_roi_contour, get_roi_signature

        roi_data = camera_config.get('roi') if camera_config else None
        if not roi_data or not roi_data.get('points'):
            return None

        frame_h, frame_w = frame_shape
        roi_pts = roi_data['points']
        roi_fw = roi_data.get('frame_width', frame_w)
        roi_fh = roi_data.get('frame_height', frame_h)
        roi_sig = get_roi_signature(roi_pts)

        cache_key = (frame_w, frame_h, roi_fw, roi_fh, roi_sig)
        if (
            self.settings.roi_cache_enabled
            and self._zone_roi_contour is not None
            and self._zone_roi_contour_key == cache_key
        ):
            return self._zone_roi_contour

        contour = build_roi_contour(
            roi_points=roi_pts,
            frame_w=roi_fw,
            frame_h=roi_fh,
            actual_w=frame_w,
            actual_h=frame_h,
        )
        if self.settings.roi_cache_enabled:
            self._zone_roi_contour = contour
            self._zone_roi_contour_key = cache_key
        return contour

    def _get_zone_density_roi_mask(
        self,
        map_shape: Tuple[int, int],
        camera_config: Optional[Dict]
    ) -> Optional[np.ndarray]:
        """Get cached ROI mask for density-map resolution."""
        from utils.perspective import create_roi_mask, get_roi_signature

        roi_data = camera_config.get('roi') if camera_config else None
        if not roi_data or not roi_data.get('points'):
            return None

        map_h, map_w = map_shape[:2]
        roi_pts = roi_data['points']
        roi_fw = int(roi_data.get('frame_width') or map_w)
        roi_fh = int(roi_data.get('frame_height') or map_h)
        roi_sig = get_roi_signature(roi_pts)

        cache_key = (map_w, map_h, roi_fw, roi_fh, roi_sig)
        if (
            self.settings.roi_cache_enabled
            and self._zone_roi_mask is not None
            and self._zone_roi_mask_key == cache_key
        ):
            return self._zone_roi_mask

        mask = create_roi_mask((map_h, map_w), roi_pts, roi_fw, roi_fh)
        if self.settings.roi_cache_enabled:
            self._zone_roi_mask = mask
            self._zone_roi_mask_key = cache_key
        return mask

    @staticmethod
    def _count_pet_points_in_roi(pet_points: Optional[np.ndarray], roi_contour: Optional[np.ndarray]) -> Optional[int]:
        """Count PET points inside ROI contour."""
        if pet_points is None or roi_contour is None:
            return None
        if len(pet_points) == 0:
            return 0

        count = 0
        for pt in pet_points:
            x, y = float(pt[0]), float(pt[1])
            if cv2.pointPolygonTest(roi_contour, (x, y), False) >= 0:
                count += 1
        return count

    def _get_batched_service(self):
        """Get the batched inference service (lazy initialization)."""
        if self._batched_service is None:
            from services.batched_inference import BatchedInferenceService
            self._batched_service = BatchedInferenceService.get_instance()
        return self._batched_service

    def _estimate_regime_from_context(self, previous_count: int, frame_size: Tuple[int, int]) -> Optional[str]:
        """
        Estimate density regime from previous frame for PET resolution selection.

        This enables adaptive PET resolution before running the full analysis.

        For first frame, returns None (uses default resolution).
        For subsequent frames, uses simple count-based heuristic from previous frame.

        Args:
            previous_count: People count from previous frame
            frame_size: Tuple of (height, width) - currently unused, reserved for future

        Returns:
            Density regime string: "SPARSE", "LOW", "MEDIUM", "HIGH", or None for first frame
        """
        if previous_count == 0:
            return None  # First frame - no history yet

        # Simple count-based regime classification (matches fusion thresholds in config)
        if previous_count < self.settings.density_regime_sparse_max:  # < 15
            return "SPARSE"
        elif previous_count < self.settings.density_regime_low_max:  # 15-50
            return "LOW"
        elif previous_count < self.settings.density_regime_medium_max:  # 50-120
            return "MEDIUM"
        else:  # > 120
            return "HIGH"

    def _prepare_inference_frame(self, frame: np.ndarray, frame_enhanced: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
        """Resize frame for inference (PET keeps full resolution; others cap at MAX_SIZE)."""
        h, w = frame.shape[:2]
        if self.settings.density_model == "pet":
            return frame_enhanced, (h, w)

        MAX_SIZE = 768
        if max(h, w) > MAX_SIZE:
            scale = MAX_SIZE / max(h, w)
            new_h, new_w = int(h * scale), int(w * scale)
            frame_inference = cv2.resize(frame_enhanced, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        else:
            frame_inference = frame_enhanced
        return frame_inference, (h, w)

    def _should_skip_pet(self, cam_key: str, estimated_regime: Optional[str]) -> Tuple[bool, int]:
        """Determine PET skip-interval status for this frame. Returns (skip_pet, pet_counter)."""
        pet_counter = self._pet_frame_counters.get(cam_key, 0) + 1
        self._pet_frame_counters[cam_key] = pet_counter

        skip_pet = False
        if self.settings.pet_inference_interval > 1:
            if pet_counter % self.settings.pet_inference_interval != 1:
                skip_pet = True
            if estimated_regime == "SPARSE":
                skip_pet = True
        return skip_pet, pet_counter

    def _run_inference(
        self,
        camera_id: Optional[str],
        frame_inference: np.ndarray,
        original_size: Tuple[int, int],
        estimated_regime: Optional[str],
        needs_density_map: bool,
        skip_pet: bool,
    ) -> Dict:
        if self.use_batched_inference and camera_id:
            service = self._get_batched_service()
            return service.predict_sync(
                camera_id=camera_id,
                frame=frame_inference,
                original_size=original_size,
                timeout_ms=self.settings.inference_timeout_ms,
                density_regime=estimated_regime,
                needs_density_map=needs_density_map,
                skip_pet=skip_pet,
            )
        if self.model is not None:
            return self.model.predict(
                frame_inference,
                density_regime=estimated_regime,
                generate_density_map=needs_density_map,
            )
        raise RuntimeError(
            "No inference method available. Either set camera_id for batched inference, "
            "or initialize with use_shared_pool=True or a model_wrapper."
        )

    def _apply_cached_pet_result(self, result: Dict, cam_key: str, pet_counter: int) -> None:
        """Merge cached PET data into a YOLO-only (PET-skipped) result."""
        cached = self._cached_pet_results.get(cam_key)
        if not cached:
            return
        result["density_count"] = cached.get("density_count", 0)
        result["final_count"] = cached.get("final_count", result["head_count"])
        result["density_map"] = cached.get("density_map")
        result["pet_points"] = cached.get("pet_points")
        result["pet_avg_confidence"] = cached.get("pet_avg_confidence", 0.0)
        result["pet_conf_std"] = cached.get("pet_conf_std", 0.0)
        result["density_regime"] = cached.get("density_regime", "UNKNOWN")
        result["fusion_rule"] = cached.get("fusion_rule", "CACHED") + f"(cached@{pet_counter})"
        result["pet_refinement"] = cached.get("pet_refinement", {"mode": "cached"})

    def _blend_and_cache_fresh_pet_result(self, result: Dict, cam_key: str) -> None:
        """Blend a fresh PET count with the previous one to dampen sudden jumps, then cache it."""
        prev_cached = self._cached_pet_results.get(cam_key)
        fresh_count = result.get("final_count", 0)
        if prev_cached and prev_cached.get("final_count", 0) > 0:
            prev_count = prev_cached["final_count"]
            if abs(fresh_count - prev_count) > max(5, prev_count * 0.3):
                result["final_count"] = int(0.6 * fresh_count + 0.4 * prev_count)

        self._cached_pet_results[cam_key] = {
            "density_count": result.get("density_count", 0),
            "final_count": result.get("final_count", 0),
            "density_map": result.get("density_map"),
            "pet_points": result.get("pet_points"),
            "pet_avg_confidence": result.get("pet_avg_confidence", 0.0),
            "pet_conf_std": result.get("pet_conf_std", 0.0),
            "density_regime": result.get("density_regime"),
            "fusion_rule": result.get("fusion_rule", ""),
            "pet_refinement": result.get("pet_refinement"),
        }

    def _get_flow_for_frame(
        self,
        frame: np.ndarray,
        camera_config: Optional[Dict],
        capture_timestamp: Optional[float],
    ) -> Tuple[np.ndarray, float, np.ndarray]:
        """Run optical flow every 5 frames (perf); reuse cached values otherwise."""
        if self.frame_count % 5 == 0:
            flow, flow_mag, divergence = self._analyze_optical_flow(
                frame, camera_config=camera_config, capture_timestamp=capture_timestamp
            )
            self._cached_flow = flow
            self._cached_flow_mag = flow_mag
            self._cached_divergence = divergence
        else:
            flow = self._cached_flow if self._cached_flow is not None else np.zeros((1, 1, 2))
            flow_mag = self._cached_flow_mag
            divergence = self._cached_divergence if self._cached_divergence is not None else np.zeros((1, 1))
        return flow, flow_mag, divergence

    def analyze_frame(
        self,
        frame: np.ndarray,
        enhance: bool = True,
        camera_id: Optional[str] = None,
        camera_config: Optional[Dict] = None,
        needs_density_map: Optional[bool] = None,
        capture_timestamp: Optional[float] = None,
    ) -> Dict:
        """
        Analyze single frame

        Args:
            frame: BGR image (numpy array)
            enhance: Whether to enhance frame (disabled for performance)
            camera_id: Camera identifier (required for batched inference mode)

        Returns comprehensive analysis results including timing metrics
        """
        total_start = time.perf_counter()
        self.frame_count += 1

        # Initialize timing dict
        timing_ms = {
            'total': 0.0,
            'model_inference': 0.0,
            'optical_flow': 0.0,
            'zone_analysis': 0.0
        }

        # Adaptive frame enhancement based on brightness
        # Only enhances low-light frames, saving cost on well-lit frames
        if self.settings.adaptive_enhancement_enabled:
            frame_enhanced, was_enhanced, brightness = FrameEnhancer.adaptive_enhance(
                frame,
                brightness_threshold=self.settings.brightness_threshold_for_enhancement
            )
            if was_enhanced:
                # Log enhancement for monitoring
                timing_ms['frame_enhancement'] = brightness
        else:
            frame_enhanced = frame

        # PET accuracy path keeps full resolution; others resize for inference.
        frame_inference, original_size = self._prepare_inference_frame(frame, frame_enhanced)
        h, w = original_size

        # Estimate density regime from previous frame for adaptive PET resolution
        estimated_regime = self._estimate_regime_from_context(
            previous_count=self._last_frame_count,
            frame_size=(h, w)
        )

        # Generate density map only if required for visualization/alerts,
        # or if explicitly enabled in configuration.
        # Alert images have an on-demand density-map builder in rtsp_worker,
        # so we only need density maps here for continuous heatmap saving/display.
        if needs_density_map is None:
            needs_density_map = (
                self.settings.enable_density_map_generation
                or self.settings.save_heatmaps
            )

        # Determine if this frame needs PET inference (skip interval optimization)
        cam_key = camera_id or "_default"
        skip_pet, pet_counter = self._should_skip_pet(cam_key, estimated_regime)

        # Get predictions from model (YOLO + PET, or YOLO-only if skip_pet)
        inference_start = time.perf_counter()
        result = self._run_inference(
            camera_id, frame_inference, original_size, estimated_regime, needs_density_map, skip_pet
        )

        timing_ms['model_inference'] = (time.perf_counter() - inference_start) * 1000
        if 'model_inference_ms' in result:
            timing_ms['model_only'] = float(result.get('model_inference_ms', 0.0))
        if 'inference_latency_ms' in result:
            timing_ms['inference_end_to_end'] = float(result.get('inference_latency_ms', 0.0))

        # PET skip interval: cache or merge PET results
        if result.get("pet_skipped"):
            self._apply_cached_pet_result(result, cam_key, pet_counter)
        else:
            self._blend_and_cache_fresh_pet_result(result, cam_key)

        # Optical flow analysis - run every 5 frames for performance (saves 200ms per frame)
        # Stampede patterns develop over seconds, so 300ms intervals are acceptable
        optical_flow_start = time.perf_counter()
        flow, flow_mag, divergence = self._get_flow_for_frame(frame, camera_config, capture_timestamp)
        timing_ms['optical_flow'] = (time.perf_counter() - optical_flow_start) * 1000

        # Zone analysis (includes risk calculation)
        zone_start = time.perf_counter()
        # Get fusion metrics from model result (with defaults for backward compatibility)
        pet_avg_conf = result.get('pet_avg_confidence', 0.0)
        pet_conf_std = result.get('pet_conf_std', 0.1)
        yolo_occupancy = result.get('yolo_occupancy', 0.0)
        yolo_avg_conf = result.get('yolo_avg_confidence', 0.5)
        pet_count = result.get('density_count', None)
        zones = self._analyze_zones(
            frame,
            result['detections'],
            result.get('density_map'),
            flow,
            flow_mag,
            divergence,
            pet_avg_conf,
            pet_conf_std,
            yolo_occupancy,
            yolo_avg_conf,
            pet_count=pet_count,
            pet_points=result.get('pet_points'),
            camera_id=camera_id,
            camera_config=camera_config,
            timing_ms=timing_ms,
        )
        timing_ms['zone_analysis'] = (time.perf_counter() - zone_start) * 1000

        # Global metrics
        total_people = sum(z['people_count'] for z in zones.values())
        avg_density = sum(z['density_estimate'] for z in zones.values()) / len(zones)
        max_density = max(z['density_estimate'] for z in zones.values())

        # Update last frame count for next frame's regime estimation
        self._last_frame_count = total_people

        # Calculate total time
        timing_ms['total'] = (time.perf_counter() - total_start) * 1000

        return {
            'frame_number': self.frame_count,
            'people_count': total_people,
            'head_detections': result['head_count'],
            'density_count': result.get('density_count', 0),
            'fusion_rule': result.get('fusion_rule', 'unknown'),
            'density_regime': result.get('density_regime', 'unknown'),
            'pet_refinement': result.get('pet_refinement', {'mode': self.settings.density_model}),
            'density_avg': float(avg_density),
            'density_max': float(max_density),
            'motion_intensity': float(flow_mag),
            'zones': zones,
            'density_map': result.get('density_map'),
            'pet_points': result.get('pet_points'),
            'detections': result['detections'],
            'timing_ms': timing_ms  # New: timing metrics for performance monitoring
        }
    
    def _analyze_optical_flow(
        self, frame: np.ndarray, camera_config: Optional[Dict] = None,
        capture_timestamp: Optional[float] = None,
    ) -> Tuple[np.ndarray, float, np.ndarray]:
        """Calculate optical flow, masked to ROI if configured.

        Computes Farneback flow on full downsampled frame, then zeros out
        flow vectors outside the ROI polygon. This eliminates interference
        from trains, lighting changes, and background movement outside the
        monitored area.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Downsample for performance
        scale = 0.5
        h, w = gray.shape
        small_h, small_w = int(h * scale), int(w * scale)
        small_gray = cv2.resize(gray, (small_w, small_h))

        if self.prev_gray is None or self.prev_gray.shape != small_gray.shape:
            self.prev_gray = small_gray.copy()
            return np.zeros((small_h, small_w, 2)), 0.0, np.zeros((small_h, small_w))

        # Calculate flow on full frame (masking inputs would create boundary artifacts)
        # DIS Optical Flow is ~10x faster than Farneback on CPU
        if self._dis_flow is not None:
            flow = self._dis_flow.calc(self.prev_gray, small_gray, None)
        else:
            flow = cv2.calcOpticalFlowFarneback(
                self.prev_gray, small_gray, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2,
                flags=0
            )

        # ROI masking: zero out flow vectors outside the ROI polygon.
        # This ensures trains, wind, lighting changes outside the monitored
        # area do not affect motion metrics, turbulence, or compression detection.
        roi_mask = self._get_flow_roi_mask((small_h, small_w), camera_config)
        if roi_mask is not None:
            flow = flow * roi_mask[:, :, np.newaxis]

        # Calculate magnitude
        magnitude = np.sqrt(flow[:, :, 0] ** 2 + flow[:, :, 1] ** 2)

        # Filter out noise - only consider significant motion
        # Outside-ROI pixels have magnitude=0 after masking, naturally excluded
        significant_motion = magnitude[magnitude > 0.5]
        if len(significant_motion) > 0:
            avg_pixel_disp = float(np.mean(significant_motion))
        else:
            avg_pixel_disp = 0.0

        # === Convert pixel displacement to real-world speed (m/s) ===
        # avg_pixel_disp is at 50% resolution → upscale ×2 for full-res pixels.
        # Multiply by meters_per_pixel, divide by elapsed seconds between flow frames.
        # Use capture_timestamp (actual frame time from RTSP worker) when available;
        # fall back to time.time() for non-RTSP callers (tests, direct API).
        now = capture_timestamp if capture_timestamp is not None else time.time()
        h_full, w_full = frame.shape[:2]
        m_per_px = self._get_meters_per_pixel(camera_config, w_full, h_full)

        if m_per_px is not None and self._last_flow_time is not None:
            elapsed = now - self._last_flow_time
            if elapsed > 0:
                avg_speed_m_s = (avg_pixel_disp * 2.0 * m_per_px) / elapsed
            else:
                avg_speed_m_s = 0.0
        else:
            # First flow frame or no calibration — return 0
            avg_speed_m_s = 0.0

        self._last_flow_time = now

        # Calculate divergence
        flow_x_grad = cv2.Sobel(flow[:, :, 0], cv2.CV_32F, 1, 0, ksize=3)
        flow_y_grad = cv2.Sobel(flow[:, :, 1], cv2.CV_32F, 0, 1, ksize=3)
        divergence = flow_x_grad + flow_y_grad

        # Mask divergence to ROI (prevents Sobel boundary artifacts at ROI edge)
        if roi_mask is not None:
            divergence = divergence * roi_mask

        self.prev_gray = small_gray.copy()
        self.flow_history.append(avg_speed_m_s)

        return flow, avg_speed_m_s, divergence

    def _compute_turbulence(self, flow: np.ndarray) -> float:
        """
        Compute motion entropy/turbulence from optical flow.

        Returns 0-1:
        - 0 = uniform direction (orderly flow)
        - 1 = chaotic/counter-flow (dangerous)

        Uses circular statistics to measure directional spread.
        """
        if flow is None or flow.size == 0:
            return 0.0

        vx = flow[:, :, 0].flatten()
        vy = flow[:, :, 1].flatten()

        # Filter significant motion only (ignore noise)
        magnitudes = np.sqrt(vx**2 + vy**2)
        mask = magnitudes > 0.5

        if np.sum(mask) < 10:
            return 0.0

        vx, vy = vx[mask], vy[mask]

        # Compute circular mean using complex number approach
        angles = np.arctan2(vy, vx)
        mean_vector = np.mean(np.exp(1j * angles))

        # Turbulence = 1 - |mean_vector|
        # Uniform direction → |mean_vector| ≈ 1 → turbulence ≈ 0
        # Chaotic/counter-flow → |mean_vector| ≈ 0 → turbulence ≈ 1
        turbulence = 1.0 - np.abs(mean_vector)

        return float(turbulence)

    def _detect_counter_flow(self, flow: np.ndarray) -> Tuple[bool, float]:
        """
        Detect counter-flow (people moving opposite directions).

        Critical for FOB cameras where bidirectional traffic is dangerous.

        Returns:
            (is_counter_flow, severity)
            - is_counter_flow: True if significant opposing traffic
            - severity: 0-1 where 1 = perfectly balanced opposing flows
        """
        if flow is None or flow.size == 0:
            return False, 0.0

        # Use horizontal flow component (assumes corridor runs left-right)
        # For vertical corridors, would use vy instead
        vx = flow[:, :, 0]

        # Count pixels with significant positive vs negative flow
        positive_flow = np.sum(vx > 1.0)  # Moving right
        negative_flow = np.sum(vx < -1.0)  # Moving left

        total_flow = positive_flow + negative_flow
        if total_flow < 100:
            return False, 0.0

        # Counter-flow ratio: how balanced are the two directions?
        # 0.5 = perfectly balanced (worst case)
        # 0 or 1 = all one direction (safe)
        ratio = min(positive_flow, negative_flow) / total_flow

        is_counter_flow = ratio > 0.25  # 25%+ in opposite direction
        severity = ratio * 2  # Scale to 0-1 (0.5 → 1.0)

        return is_counter_flow, min(severity, 1.0)

    def _get_calibration_manager(self) -> CalibrationManager:
        """Get calibration manager (lazy initialization)."""
        if self._calibration_manager is None:
            self._calibration_manager = CalibrationManager()
        return self._calibration_manager

    def _analyze_density_hotspots(
        self,
        density_map: np.ndarray,
        area_m2: float = 150.0,
        grid_size: int = 4
    ) -> Tuple[float, Tuple[int, int], List[float]]:
        """
        Analyze PET density map for local hotspots.

        Uses uniform cell areas (no perspective correction).
        Each cell gets area_m2 / (grid_size * grid_size).

        Args:
            density_map: PET density map (sum ~ people count * density_scale).
                         Should already be ROI-masked if applicable.
            area_m2: Total visible area in square meters
            grid_size: Number of cells per dimension (4x4 = 16 cells)

        Returns:
            (max_local_density_per_m2, hotspot_cell_coords, all_cell_densities)
        """
        if density_map is None or density_map.size == 0:
            return 0.0, (0, 0), []

        h, w = density_map.shape[:2]
        cell_h = max(1, h // grid_size)
        cell_w = max(1, w // grid_size)

        # Uniform area per cell (no perspective correction)
        cell_area_m2 = area_m2 / (grid_size * grid_size)

        max_density = 0.0
        hotspot = (0, 0)
        all_densities = []

        for row in range(grid_size):
            for col in range(grid_size):
                y1 = row * cell_h
                y2 = min((row + 1) * cell_h, h)
                x1 = col * cell_w
                x2 = min((col + 1) * cell_w, w)
                cell = density_map[y1:y2, x1:x2]

                cell_count = np.sum(cell) / self.settings.density_scale

                local_density = cell_count / cell_area_m2 if cell_area_m2 > 0 else 0
                all_densities.append(local_density)

                if local_density > max_density:
                    max_density = local_density
                    hotspot = (row, col)

        return float(max_density), hotspot, all_densities

    def _apply_zone_roi_filter(
        self,
        detections: List[Dict],
        density: Optional[np.ndarray],
        h: int,
        w: int,
        camera_config: Optional[Dict],
    ) -> Tuple[List[Dict], Optional[np.ndarray], Optional[np.ndarray]]:
        """Filter YOLO detections by foot point and mask PET density map to ROI.

        Returns (filtered_detections, filtered_density, roi_contour).
        """
        from utils.perspective import foot_point_in_roi

        roi_data = camera_config.get("roi") if camera_config else None
        if not (roi_data and roi_data.get("points")):
            return detections, density, None

        roi_contour = self._get_zone_roi_contour((h, w), camera_config)
        if roi_contour is not None:
            detections = [d for d in detections if foot_point_in_roi(d["bbox"], roi_contour)]

        if density is not None and density.size > 0:
            roi_mask = self._get_zone_density_roi_mask(density.shape, camera_config)
            if roi_mask is not None:
                density = density * roi_mask

        return detections, density, roi_contour

    def _resolve_density_count(
        self,
        density: Optional[np.ndarray],
        roi_contour: Optional[np.ndarray],
        pet_points: Optional[np.ndarray],
        pet_count: Optional[int],
    ) -> int:
        """PET density count (for fusion), preferring ROI-filtered PET points."""
        if roi_contour is not None:
            in_roi = self._count_pet_points_in_roi(pet_points, roi_contour)
            if in_roi is not None:
                return in_roi
        if pet_count is not None:
            return int(pet_count)
        if density is not None and density.size > 0:
            return int(np.sum(density) / self.settings.density_scale)
        return 0

    def _compute_zone_density(
        self,
        density: Optional[np.ndarray],
        detections: List[Dict],
        head_count: int,
        final_count: int,
        roi_contour: Optional[np.ndarray],
        h: int,
        w: int,
        camera_id: Optional[str],
        yolo_avg_confidence: float,
        camera_config: Optional[Dict],
    ) -> float:
        """Compute density via pixel-mode estimation or area-based calibration, then EMA-smooth it."""
        if self.settings.density_mode == "pixel":
            avg_density = self._estimate_pixel_density(
                density, detections, head_count, final_count,
                roi_contour, h, w, camera_id, yolo_avg_confidence
            )
        else:
            # Area-based density (calibrated physical measurements)
            # Priority: camera_config.area_m2 (DB) → CalibrationManager (JSON) → default 150 m²
            if camera_config and camera_config.get('area_m2'):
                area_m2 = camera_config['area_m2']
            else:
                calibration = self._get_calibration_manager().get_calibration(camera_id or "_default_fob")
                area_m2 = calibration.visible_area_m2
            avg_density = final_count / area_m2 if area_m2 > 0 else 0.0

        # EMA smooth density to prevent alert flapping
        ema_key = camera_id or "_default"
        prev_density = self._ema_density.get(ema_key)
        if prev_density is not None:
            ema_alpha = 0.3 if abs(avg_density - prev_density) > 0.5 else 0.1
            avg_density = ema_alpha * avg_density + (1 - ema_alpha) * prev_density
        self._ema_density[ema_key] = avg_density
        return avg_density

    def _classify_density_level(self, avg_density: float) -> str:
        if avg_density < self.settings.density_threshold_moderate:
            return "LOW"
        if avg_density < self.settings.density_threshold_high:
            return "MODERATE"
        if avg_density < self.settings.density_threshold_critical:
            return "HIGH"
        return "CRITICAL"

    def _classify_motion_level(self, flow_magnitude: float) -> str:
        if flow_magnitude < self.settings.motion_threshold_slow:
            return "STATIC"
        if flow_magnitude < self.settings.motion_threshold_normal:
            return "SLOW"
        if flow_magnitude < self.settings.motion_threshold_fast:
            return "NORMAL"
        if flow_magnitude < self.settings.motion_threshold_running:
            return "FAST"
        return "RUNNING"

    def _analyze_zones(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        density: Optional[np.ndarray],
        flow: np.ndarray,
        flow_magnitude: float,
        divergence: np.ndarray = None,
        pet_avg_confidence: float = 0.0,
        pet_conf_std: float = 0.1,
        yolo_occupancy: float = 0.0,
        yolo_avg_confidence: float = 0.5,
        pet_count: Optional[int] = None,
        pet_points: Optional[np.ndarray] = None,
        camera_id: Optional[str] = None,
        camera_config: Optional[Dict] = None,
        timing_ms: Optional[Dict[str, float]] = None
    ) -> Dict[str, Dict]:
        """Analyze full frame as a single zone using regime-based fusion and real spatial density.

        Args:
            camera_config: Optional calibration from DB: { area_m2: float, roi: { points, frame_width, frame_height } }
        """
        from utils.fusion import compute_fusion

        h, w = frame.shape[:2]

        # Single full-frame zone
        zone_id = "full_frame"
        x1, y1, x2, y2 = 0, 0, w, h

        # Initialize smoother for the single zone
        if zone_id not in self.smoothers:
            self.smoothers[zone_id] = TemporalSmoother(alpha=0.3)

        smoother = self.smoothers[zone_id]

        # === ROI FILTERING (before fusion) ===
        roi_start = time.perf_counter()
        detections, density, roi_contour = self._apply_zone_roi_filter(detections, density, h, w, camera_config)
        if timing_ms is not None:
            timing_ms["roi_filtering"] = (time.perf_counter() - roi_start) * 1000

        # Count detections (after ROI filtering)
        head_count = len(detections)

        # PET density count (for fusion) — from masked density map
        density_count = self._resolve_density_count(density, roi_contour, pet_points, pet_count)

        # === REGIME-BASED FUSION ===
        # Uses unified fusion module for consistency across all implementations
        raw_count, fusion_rule, density_regime = compute_fusion(
            yolo_count=head_count,
            pet_count=density_count,
            pet_avg_conf=pet_avg_confidence,
            yolo_occupancy=yolo_occupancy,
            yolo_avg_conf=yolo_avg_confidence,
            pet_conf_std=pet_conf_std,
            settings=self.settings
        )

        # Debug logging (1% of frames to reduce log overhead).
        if np.random.random() < 0.01:
            print(f"[FUSION] {fusion_rule} | YOLO={head_count}, PET={density_count}, Regime={density_regime}")

        final_count = smoother.smooth_count(raw_count)

        # === DENSITY CALCULATION ===
        avg_density = self._compute_zone_density(
            density, detections, head_count, final_count, roi_contour,
            h, w, camera_id, yolo_avg_confidence, camera_config
        )

        # Risk assessment
        risk_score, risk_level, risk_factors = self._calculate_risk(
            people_count=final_count,
            density=avg_density,
            motion=flow_magnitude,
            divergence_map=divergence,
            flow=flow
        )

        density_level = self._classify_density_level(avg_density)
        motion_level = self._classify_motion_level(flow_magnitude)

        results = {
            zone_id: {
                'id': zone_id,
                'name': "Full Frame",
                'coords': (x1, y1, x2, y2),
                'people_count': final_count,
                'head_detections': head_count,
                'density_estimate': avg_density,
                'density_level': density_level,
                'avg_motion': flow_magnitude,
                'motion_level': motion_level,
                'risk_score': risk_score,
                'risk_level': risk_level,
                'risk_factors': risk_factors,
                'density_regime': density_regime,
                'fusion_rule': fusion_rule
            }
        }

        return results
    
    def _density_risk_score(self, density: float, risk_factors: List[str]) -> float:
        """DENSITY COMPONENT (people per m²) — unified configurable thresholds."""
        if density > self.settings.density_threshold_critical:
            risk_factors.append(f"CRITICAL density: {density:.1f}")
            return 80
        if density > self.settings.density_threshold_high:
            risk_factors.append(f"High density: {density:.1f}")
            return 50
        if density > self.settings.density_threshold_moderate:
            risk_factors.append(f"Elevated density: {density:.1f}")
            return 25
        return density * 15  # Linear scaling below moderate threshold

    @staticmethod
    def _motion_weight(people_count: int) -> float:
        """Scale motion's contribution by crowd size — motion barely matters below 15 people."""
        if people_count < 15:
            return 0.2
        if people_count < 30:
            return 0.5
        return 1.0

    def _motion_risk_score(self, density: float, motion: float, motion_weight: float) -> float:
        """Motion component - crowd speed in m/s.

        Typical values: 0-0.1 = static, 0.1-0.5 = shuffling, 0.5-1.3 = walking, 1.3-2.5 = fast, 2.5+ = running.
        Motion multiplier boosted when density is high (genuine danger).
        At m/s scale: motion=2.5 (fast) with multiplier=1 -> 2.5*8=20 (full score).
        Normal walking (1.3 m/s) -> 10.4 (not alarming by itself).
        """
        motion_multiplier = 1.5 if density > self.settings.density_threshold_high else 1.0
        return min(motion * 8 * motion_multiplier * motion_weight, 25)

    def _kinetic_energy_score(
        self, density: float, motion: float, motion_weight: float, risk_factors: List[str]
    ) -> float:
        """KE = density x speed^2 — fast movement in dense crowds is exponentially dangerous.

        Units: people/m^2 x (m/s)^2 = people*m^2/s^2 per m^2 — physically meaningful.
        - 2/m^2 walking (1.3 m/s) -> KE=3.4 (manageable)
        - 3/m^2 fast (2.5 m/s)   -> KE=18.8 (dangerous, crosses 15 threshold)
        - 4/m^2 running (3.0 m/s) -> KE=36 (critical, crosses 30 threshold)
        """
        kinetic_energy = density * (motion ** 2)

        if kinetic_energy > 30:
            ke_score = 25
            risk_factors.append(f"CRITICAL kinetic energy: {kinetic_energy:.1f}")
        elif kinetic_energy > 15:
            ke_score = 18
            risk_factors.append(f"High kinetic energy: {kinetic_energy:.1f}")
        elif kinetic_energy > 8:
            ke_score = 10
            risk_factors.append(f"Elevated kinetic energy: {kinetic_energy:.1f}")
        else:
            ke_score = kinetic_energy * 1.0  # Linear scaling for low KE

        return ke_score * motion_weight

    def _acceleration_risk_score(self, people_count: int, risk_factors: List[str]) -> float:
        """Flag sudden crowd acceleration — only with actual crowds (>=15 people)."""
        if len(self.flow_history) < 5:
            return 0
        recent = list(self.flow_history)[-5:]
        acceleration = (recent[-1] - recent[0]) / len(recent)
        if acceleration > self.settings.acceleration_threshold and people_count >= 15:
            risk_factors.append("Sudden crowd acceleration")
            return 15
        return 0

    def _compression_risk_score(
        self,
        density: float,
        people_count: int,
        divergence_map: Optional[np.ndarray],
        risk_factors: List[str],
    ) -> Tuple[float, bool]:
        """Detect crowd convergence (compression). Only checked for moderate+ density AND 30+ people
        — small groups with noisy optical flow should never trigger compression.
        """
        if not (divergence_map is not None and divergence_map.size > 0
                and density > self.settings.density_threshold_moderate
                and people_count >= 30):
            return 0, False

        negative_divergence = divergence_map[divergence_map < 0]
        if len(negative_divergence) == 0:
            return 0, False

        avg_compression = float(np.mean(negative_divergence))
        if avg_compression < self.settings.compression_threshold:
            risk_factors.append(f"Crowd compression detected (div={avg_compression:.2f})")
            return self.settings.compression_weight, True
        return 0, False

    def _turbulence_risk_score(
        self,
        density: float,
        people_count: int,
        motion: float,
        motion_weight: float,
        flow: Optional[np.ndarray],
        risk_factors: List[str],
    ) -> float:
        """TURBULENCE & COUNTER-FLOW DETECTION — critical for FOB cameras where
        bidirectional traffic in narrow corridors is dangerous.
        """
        if not (flow is not None and people_count >= 10 and motion > 0.3):
            return 0

        turbulence = self._compute_turbulence(flow)
        is_counter_flow, counter_flow_severity = self._detect_counter_flow(flow)

        if is_counter_flow and density > self.settings.density_threshold_moderate:
            risk_factors.append(f"COUNTER-FLOW: {counter_flow_severity:.0%} opposing traffic")
            return counter_flow_severity * 20 * motion_weight  # Up to 20 points
        if turbulence > 0.6:
            risk_factors.append(f"Chaotic movement: turbulence={turbulence:.2f}")
            return turbulence * 12 * motion_weight  # Up to 12 points
        if turbulence > 0.4 and density > self.settings.density_threshold_moderate:
            risk_factors.append(f"Mixed flow directions: turbulence={turbulence:.2f}")
            return turbulence * 8 * motion_weight
        return 0

    def _apply_pattern_adjustments(
        self,
        total_score: float,
        density: float,
        motion: float,
        is_compressed: bool,
        risk_factors: List[str],
    ) -> float:
        """Stampede-pattern boost and static-queue adjustments to the raw total score."""
        # Stampede pattern: HIGH density + Fast motion (>2.0 m/s = jogging) + Compression
        if density > self.settings.density_threshold_high and motion > 2.0 and is_compressed:
            risk_factors.append("STAMPEDE RISK: Dense + Fast + Compressed")
            total_score = min(total_score * 1.3, 100)  # 30% boost

        # Static queue adjustment - for moderate density range.
        # Higher density is still dangerous even when static (crush risk).
        if (density > self.settings.density_threshold_moderate and
                density < self.settings.density_threshold_high and
                motion < self.settings.static_queue_motion_threshold):
            if not is_compressed:
                total_score *= self.settings.static_queue_risk_dampening
                risk_factors.append("Static queue detected (low risk)")
            else:
                risk_factors.append("WARNING: Static but compressing (bottleneck)")
        elif density >= self.settings.density_threshold_high and motion < self.settings.static_queue_motion_threshold:
            total_score += 20
            risk_factors.append("Static high-density crowd (crush risk)")

        return total_score

    @staticmethod
    def _apply_count_based_cap(total_score: float, people_count: int) -> float:
        """Count-based risk caps — count is the most reliable signal.

        Prevents false HIGH/CRITICAL when density/motion conversion is off.
        <15 -> max LOW, <30 -> max MEDIUM (can't reach HIGH=55), <80 -> max HIGH (can't reach CRITICAL=80).
        """
        if people_count < 15:
            return min(total_score, 30)
        if people_count < 30:
            return min(total_score, 45)
        if people_count < 80:
            return min(total_score, 70)
        return total_score

    def _classify_risk_level(self, total_score: float) -> str:
        if total_score < self.settings.risk_threshold_medium:
            return "LOW"
        if total_score < self.settings.risk_threshold_high:
            return "MEDIUM"
        if total_score < self.settings.risk_threshold_critical:
            return "HIGH"
        return "CRITICAL"

    def _calculate_risk(
        self,
        people_count: int,
        density: float,
        motion: float,
        divergence_map: np.ndarray = None,
        flow: np.ndarray = None
    ) -> Tuple[float, str, List[str]]:
        """Calculate stampede risk with production-grade metrics.

        Args:
            density: Real spatial density in people per m² (not arbitrary units)
        """
        risk_factors = []

        density_score = self._density_risk_score(density, risk_factors)
        motion_weight = self._motion_weight(people_count)
        motion_score = self._motion_risk_score(density, motion, motion_weight)
        ke_score = self._kinetic_energy_score(density, motion, motion_weight, risk_factors)

        # Fast movement flag: >1.5 m/s (brisk walking) in dense crowd
        if motion > 1.5 and density > self.settings.density_threshold_moderate and people_count >= 15:
            risk_factors.append("Fast movement in dense crowd")

        acceleration_score = self._acceleration_risk_score(people_count, risk_factors)
        compression_score, is_compressed = self._compression_risk_score(
            density, people_count, divergence_map, risk_factors
        )
        turbulence_score = self._turbulence_risk_score(
            density, people_count, motion, motion_weight, flow, risk_factors
        )

        total_score = density_score + motion_score + ke_score + acceleration_score + compression_score + turbulence_score
        total_score = self._apply_pattern_adjustments(total_score, density, motion, is_compressed, risk_factors)
        total_score = self._apply_count_based_cap(total_score, people_count)
        total_score = min(total_score, 100)

        risk_level = self._classify_risk_level(total_score)

        return total_score, risk_level, risk_factors
