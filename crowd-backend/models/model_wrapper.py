"""
PET model wrapper for crowd counting.

Uses PET (Point-query Efficient Transformer) for density estimation
and YOLO for head detection, with regime-based adaptive fusion.
"""

from __future__ import annotations
import threading
from typing import Dict, List, Optional
import numpy as np
import torch
import logging
logger = logging.getLogger(__name__)
from .pet_wrapper import PETWrapper
from .yolo_wrapper import YOLOWrapper
from utils.count_calibration import calibrate_fused_count
from utils.fusion import compute_fusion
from utils.point_to_density import points_to_density_map


class SharedModelPool:
    """Singleton model pool that shares one PET+YOLO stack across workers."""

    _instance: Optional["SharedModelPool"] = None
    _lock = threading.Lock()

    def __init__(self):
        if SharedModelPool._instance is not None:
            raise RuntimeError("Use SharedModelPool.get_instance() instead")

        self._inference_lock = threading.Lock()
        self._model: Optional[CrowdCountingModelWrapper] = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "SharedModelPool":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance._model = None
                cls._instance._initialized = False
            cls._instance = None

    def initialize(
        self,
        yolo_path: str = "yolov8n.pt",
        device: str = "cuda",
        density_model: str = "pet",
        density_gaussian_sigma: float = 15.0,
        pet_weights_path: Optional[str] = None,
        pet_conf_threshold: float = 0.5,
        pet_nms_distance: float = 6.0,
        **_: object,
    ) -> None:
        """Initialize shared models once. Legacy kwargs are accepted and ignored."""
        with self._inference_lock:
            if self._initialized:
                logger.info("[SharedModelPool] Already initialized, skipping")
                return

            if (density_model or "pet").lower() != "pet":
                logger.info(f"[SharedModelPool] density_model='{density_model}' requested, forcing PET")

            logger.info("[SharedModelPool] Initializing shared models...")
            self._model = CrowdCountingModelWrapper(
                yolo_path=yolo_path,
                device=device,
                density_model="pet",
                density_gaussian_sigma=density_gaussian_sigma,
                pet_weights_path=pet_weights_path,
                pet_conf_threshold=pet_conf_threshold,
                pet_nms_distance=pet_nms_distance,
            )
            self._initialized = True

            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated() / 1024**2
                reserved = torch.cuda.memory_reserved() / 1024**2
                logger.info(
                    "[SharedModelPool] GPU Memory - "
                    f"Allocated: {allocated:.1f}MB, Reserved: {reserved:.1f}MB"
                )

            logger.info("[SharedModelPool] Initialization complete")

    def predict(
        self,
        frame: np.ndarray,
        density_regime: Optional[str] = None,
        generate_density_map: bool = True,
    ) -> Dict:
        if not self._initialized or self._model is None:
            raise RuntimeError("SharedModelPool not initialized. Call initialize() first.")

        with self._inference_lock:
            return self._model.predict(
                frame,
                density_regime=density_regime,
                generate_density_map=generate_density_map,
            )

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def device(self) -> torch.device:
        if self._model is not None:
            return self._model.device
        return torch.device("cpu")

    @property
    def model_info(self) -> Dict:
        if self._model is not None:
            return self._model.model_info
        return {}


class CrowdCountingModelWrapper:
    """PET-only crowd counting wrapper with YOLO fusion."""

    def __init__(
        self,
        yolo_path: str = "yolov8n.pt",
        device: str = "cuda",
        density_model: str = "pet",
        density_gaussian_sigma: float = 15.0,
        pet_weights_path: Optional[str] = None,
        pet_conf_threshold: float = 0.5,
        pet_nms_distance: float = 6.0,
        **_: object,
    ) -> None:
        self.settings = None
        use_gpu = True
        try:
            from config.config import get_settings

            self.settings = get_settings()
            use_gpu = bool(getattr(self.settings, "use_gpu", True))
        except Exception:
            self.settings = None

        cuda_available = torch.cuda.is_available()
        if device == "cuda" and use_gpu and cuda_available:
            self.device = torch.device("cuda")
            logger.info(f"[INFO] Using GPU: {torch.cuda.get_device_name(0)}")
        elif device == "cuda" and not cuda_available:
            logger.warning("[WARNING] CUDA requested but not available. Falling back to CPU.")
            logger.warning(
                "[WARNING] Install CUDA PyTorch: "
                "pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118"
            )
            self.device = torch.device("cpu")
        elif device == "cuda" and not use_gpu:
            logger.info("[INFO] GPU available but use_gpu=False in config. Using CPU.")
            self.device = torch.device("cpu")
        else:
            self.device = torch.device("cpu")
            logger.info("[INFO] Using CPU device")

        logger.info(f"[INFO] PyTorch version: {torch.__version__}")
        logger.info(f"[INFO] CUDA available: {cuda_available}")
        if cuda_available:
            logger.info(f"[INFO] CUDA version: {torch.version.cuda}")
            logger.info(f"[INFO] GPU device: {torch.cuda.get_device_name(0)}")
            total_mem_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"[INFO] GPU memory: {total_mem_gb:.2f} GB")
        logger.info(f"[INFO] Using device: {self.device}")

        if (density_model or "pet").lower() != "pet":
            logger.warning(f"[WARNING] density_model='{density_model}' is deprecated. Using PET only.")

        self.density_model_type = "pet"
        self.density_gaussian_sigma = density_gaussian_sigma

        logger.info(f"[INFO] Loading YOLO from {yolo_path}...")
        self.yolo = YOLOWrapper(model_path=yolo_path, device=str(self.device))

        logger.info("[INFO] Loading PET...")
        self.pet = PETWrapper(
            weights_path=pet_weights_path,
            conf_threshold=pet_conf_threshold,
            nms_distance=pet_nms_distance,
            device=str(self.device),
        )

        self.model_info = {
            "yolo_model": yolo_path,
            "device": str(self.device),
            "density_model": "pet",
            "pet_weights": pet_weights_path,
            "gaussian_sigma": density_gaussian_sigma,
        }

    def predict(
        self,
        frame: np.ndarray,
        density_regime: Optional[str] = None,
        generate_density_map: bool = True,
    ) -> Dict:
        """Predict crowd metrics for a single frame."""
        yolo_result = self.yolo.detect_with_metrics(frame)
        detections = yolo_result["detections"]
        head_count = yolo_result["count"]
        yolo_occupancy = yolo_result["occupancy_ratio"]
        yolo_avg_confidence = yolo_result["avg_confidence"]

        density, density_avg_conf, density_conf_std, density_count, refinement_info, pet_points = self._estimate_density(
            frame,
            density_regime=density_regime,
            generate_density_map=generate_density_map,
        )

        settings = self.settings
        if settings is None:
            try:
                from config.config import get_settings

                settings = get_settings()
            except Exception:
                settings = None

        if bool(getattr(settings, "pet_use_adaptive_fusion", True)):
            final_count, fusion_rule, predicted_regime = compute_fusion(
                yolo_count=head_count,
                pet_count=density_count,
                pet_avg_conf=density_avg_conf,
                yolo_occupancy=yolo_occupancy,
                yolo_avg_conf=yolo_avg_confidence,
                pet_conf_std=density_conf_std,
                settings=settings,
            )
        else:
            _, _, predicted_regime = compute_fusion(
                yolo_count=head_count,
                pet_count=density_count,
                pet_avg_conf=density_avg_conf,
                yolo_occupancy=yolo_occupancy,
                yolo_avg_conf=yolo_avg_confidence,
                pet_conf_std=density_conf_std,
                settings=settings,
            )
            final_count = int(density_count)
            fusion_rule = "PET_DIRECT"
            if bool(getattr(settings, "count_calibration_enabled", False)):
                final_count, multiplier, cal_bin = calibrate_fused_count(
                    raw_count=final_count,
                    pet_count=density_count,
                    settings=settings,
                )
                fusion_rule = f"PET_DIRECT | CAL[{cal_bin}] x{multiplier:.2f}"

        return {
            "head_count": head_count,
            "density_count": density_count,
            "final_count": int(final_count),
            "density_map": density,
            "pet_points": pet_points,
            "detections": detections,
            "pet_avg_confidence": density_avg_conf,
            "pet_conf_std": density_conf_std,
            "yolo_occupancy": yolo_occupancy,
            "yolo_avg_confidence": yolo_avg_confidence,
            "fusion_rule": fusion_rule,
            "density_regime": predicted_regime,
            "pet_refinement": refinement_info,
        }

    def predict_batch(
        self,
        frames: List[np.ndarray],
        density_regimes: Optional[List[Optional[str]]] = None,
        generate_density_maps: Optional[List[bool]] = None,
        skip_pets: Optional[List[bool]] = None,
    ) -> List[Dict]:
        """Predict crowd metrics for a batch of frames.

        YOLO runs as a single GPU forward pass.
        PET runs sequentially per frame (PET model is not batchable).
        Frames with skip_pets[i]=True get YOLO-only results (no PET).

        Returns list of result dicts with the same schema as predict().
        """
        n = len(frames)
        if n == 0:
            return []
        if density_regimes is None:
            density_regimes = [None] * n
        if generate_density_maps is None:
            generate_density_maps = [True] * n
        if skip_pets is None:
            skip_pets = [False] * n

        # Phase 1: Batched YOLO (single GPU forward pass for all frames)
        yolo_batch = self.yolo.detect_batch_with_metrics(frames)

        # Resolve settings once for the entire batch
        settings, use_adaptive_fusion, use_calibration = self._resolve_fusion_settings()

        # Phase 2: Sequential PET per frame + fusion (skip PET for flagged frames)
        results = []
        for i, frame in enumerate(frames):
            yr = yolo_batch[i]
            head_count = yr["count"]
            yolo_occupancy = yr["occupancy_ratio"]
            yolo_avg_confidence = yr["avg_confidence"]
            detections = yr["detections"]

            # Skip PET for this frame — return YOLO-only result
            if skip_pets[i]:
                results.append(self._yolo_only_result(
                    head_count, yolo_occupancy, yolo_avg_confidence, detections, density_regimes[i]
                ))
                continue

            density, density_avg_conf, density_conf_std, density_count, refinement_info, pet_points = (
                self._estimate_density_safe(frame, density_regimes[i], generate_density_maps[i])
            )

            # Fusion — identical logic to predict()
            final_count, fusion_rule, predicted_regime = self._fuse_counts(
                head_count, density_count, density_avg_conf, density_conf_std,
                yolo_occupancy, yolo_avg_confidence, settings, use_adaptive_fusion, use_calibration,
            )

            results.append({
                "head_count": head_count,
                "density_count": density_count,
                "final_count": int(final_count),
                "density_map": density,
                "pet_points": pet_points,
                "detections": detections,
                "pet_avg_confidence": density_avg_conf,
                "pet_conf_std": density_conf_std,
                "yolo_occupancy": yolo_occupancy,
                "yolo_avg_confidence": yolo_avg_confidence,
                "fusion_rule": fusion_rule,
                "density_regime": predicted_regime,
                "pet_refinement": refinement_info,
            })

        return results

    def _resolve_fusion_settings(self):
        """Resolve settings and derived fusion flags once per batch."""
        settings = self.settings
        if settings is None:
            try:
                from config.config import get_settings
                settings = get_settings()
            except Exception:
                settings = None

        use_adaptive_fusion = bool(getattr(settings, "pet_use_adaptive_fusion", True))
        use_calibration = bool(getattr(settings, "count_calibration_enabled", False))
        return settings, use_adaptive_fusion, use_calibration

    @staticmethod
    def _yolo_only_result(head_count, yolo_occupancy, yolo_avg_confidence, detections, density_regime) -> Dict:
        """Build a YOLO-only result dict for frames where PET was skipped."""
        return {
            "head_count": head_count,
            "density_count": 0,
            "final_count": head_count,
            "density_map": None,
            "pet_points": np.empty((0, 2), dtype=np.float32),
            "detections": detections,
            "pet_avg_confidence": 0.0,
            "pet_conf_std": 0.0,
            "yolo_occupancy": yolo_occupancy,
            "yolo_avg_confidence": yolo_avg_confidence,
            "fusion_rule": "YOLO_ONLY_PET_SKIPPED",
            "density_regime": density_regime or "UNKNOWN",
            "pet_refinement": {"mode": "pet_skipped"},
            "pet_skipped": True,
        }

    def _estimate_density_safe(self, frame: np.ndarray, density_regime: Optional[str], generate_density_map: bool):
        """Estimate density for one frame, degrading to a PET-error placeholder on failure."""
        try:
            return self._estimate_density(
                frame,
                density_regime=density_regime,
                generate_density_map=generate_density_map,
            )
        except Exception:
            return None, 0.0, 0.0, 0, {"mode": "pet_error"}, np.empty((0, 2), dtype=np.float32)

    @staticmethod
    def _fuse_counts(
        head_count,
        density_count,
        density_avg_conf,
        density_conf_std,
        yolo_occupancy,
        yolo_avg_confidence,
        settings,
        use_adaptive_fusion: bool,
        use_calibration: bool,
    ):
        """Fuse YOLO + PET counts — identical logic to predict()."""
        if use_adaptive_fusion:
            return compute_fusion(
                yolo_count=head_count,
                pet_count=density_count,
                pet_avg_conf=density_avg_conf,
                yolo_occupancy=yolo_occupancy,
                yolo_avg_conf=yolo_avg_confidence,
                pet_conf_std=density_conf_std,
                settings=settings,
            )

        _, _, predicted_regime = compute_fusion(
            yolo_count=head_count,
            pet_count=density_count,
            pet_avg_conf=density_avg_conf,
            yolo_occupancy=yolo_occupancy,
            yolo_avg_conf=yolo_avg_confidence,
            pet_conf_std=density_conf_std,
            settings=settings,
        )
        final_count = int(density_count)
        fusion_rule = "PET_DIRECT"
        if use_calibration:
            final_count, multiplier, cal_bin = calibrate_fused_count(
                raw_count=final_count,
                pet_count=density_count,
                settings=settings,
            )
            fusion_rule = f"PET_DIRECT | CAL[{cal_bin}] x{multiplier:.2f}"
        return final_count, fusion_rule, predicted_regime

    def _estimate_density(
        self,
        frame: np.ndarray,
        density_regime: Optional[str] = None,
        pet_conf_threshold: Optional[float] = None,
        pet_nms_distance: Optional[float] = None,
        generate_density_map: bool = True,
    ):
        """Delegate to PET density estimation."""
        return self._estimate_density_pet(
            frame=frame,
            density_regime=density_regime,
            pet_conf_threshold=pet_conf_threshold,
            pet_nms_distance=pet_nms_distance,
            generate_density_map=generate_density_map,
        )

    def _estimate_density_pet(
        self,
        frame: np.ndarray,
        density_regime: Optional[str] = None,
        pet_conf_threshold: Optional[float] = None,
        pet_nms_distance: Optional[float] = None,
        generate_density_map: bool = True,
    ):
        points, confidences, count, avg_confidence, conf_std = self.pet.predict(
            frame,
            density_regime=density_regime,
            conf_threshold=pet_conf_threshold,
            nms_distance=pet_nms_distance,
        )

        h, w = frame.shape[:2]
        if generate_density_map and len(points) > 0:
            density = points_to_density_map(
                points=points,
                confidences=confidences,
                image_shape=(h, w),
                sigma=self.density_gaussian_sigma,
                method="gaussian",
            )
        elif generate_density_map:
            density = np.zeros((h, w), dtype=np.float32)
        else:
            density = None

        refinement = {"mode": "pet", "far_added": 0, "dense_added": 0}
        return density, float(avg_confidence), float(conf_std), int(count), refinement, points
