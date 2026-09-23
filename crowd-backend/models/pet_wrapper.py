"""
PET wrapper for inference-only crowd counting.

This wrapper vendors the official PET architecture under `models.pet_upstream`
and exposes a `predict()` interface for seamless integration.
"""

from types import SimpleNamespace
from typing import Optional, Tuple
import os
import cv2
import numpy as np
import torch
import torch.nn.functional as F
import logging
logger = logging.getLogger(__name__)    
from .pet_upstream.models import build_model as build_pet_model
from .pet_upstream.util.misc import nested_tensor_from_tensor_list


class PETWrapper:
    """Inference wrapper for PET (ICCV 2023)."""

    def __init__(
        self,
        weights_path: str,
        conf_threshold: float = 0.5,
        nms_distance: float = 6.0,
        device: str = "cuda",
    ):
        from config.config import get_settings

        self.settings = get_settings()
        self.device = torch.device(device if torch.cuda.is_available() and device == "cuda" else "cpu")
        self.conf_threshold = float(conf_threshold)
        self.nms_distance = float(nms_distance)

        if not weights_path or not os.path.exists(weights_path):
            logger.warning(f"[WARNING] PET weights not found at '{weights_path}'. PET model will be disabled.")
            self.model = None
            return

        logger.info(f"[PET] Initializing with device: {self.device}")
        self.model = self._build_model()
        self.model.to(self.device)
        self.model.eval()
        self._load_weights(weights_path)

    def _build_model(self) -> torch.nn.Module:
        args = SimpleNamespace(
            # backbone + transformer
            backbone="vgg16_bn",
            position_embedding="sine",
            dec_layers=2,
            dim_feedforward=512,
            hidden_dim=256,
            dropout=0.0,
            nheads=8,
            # matcher/loss placeholders (unused in inference, required by builder)
            set_cost_class=1.0,
            set_cost_point=0.05,
            ce_loss_coef=1.0,
            point_loss_coef=5.0,
            eos_coef=0.5,
            # misc
            device=str(self.device),
        )
        model, _ = build_pet_model(args)
        return model

    def _load_weights(self, weights_path: str) -> None:
        print(f"[PET] Loading weights from: {weights_path}")
        checkpoint = torch.load(weights_path, map_location=self.device, weights_only=True)
        state = checkpoint.get("model", checkpoint) if isinstance(checkpoint, dict) else checkpoint
        msg = self.model.load_state_dict(state, strict=False)
        if getattr(msg, "missing_keys", None):
            logger.info(f"[PET] Missing keys: {len(msg.missing_keys)}")
        if getattr(msg, "unexpected_keys", None):
            logger.info(f"[PET] Unexpected keys: {len(msg.unexpected_keys)}")
        logger.info("[PET] Weights loaded")

    def _resolve_max_height(self, density_regime: Optional[str], max_height_override: Optional[int]) -> int:
        if max_height_override is not None and max_height_override > 0:
            return int(max_height_override)
        if density_regime in ("SPARSE", "LOW"):
            return int(getattr(self.settings, "pet_max_height_sparse", 1280))
        if density_regime == "MEDIUM":
            return int(getattr(self.settings, "pet_max_height_medium", 1024))
        if density_regime == "HIGH":
            return int(getattr(self.settings, "pet_max_height_high", 896))
        return int(getattr(self.settings, "pet_max_height_default", 1024))

    def _apply_nms(
        self,
        points: np.ndarray,
        confidences: np.ndarray,
        nms_distance: float,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Greedy distance-based NMS with vectorized inner distance computation."""
        if len(points) == 0:
            return points, confidences

        order = np.argsort(-confidences)
        pts = points[order].copy()
        conf = confidences[order].copy()

        d2_threshold = float(nms_distance) ** 2
        suppressed = np.zeros(len(pts), dtype=bool)
        keep = []

        for i in range(len(pts)):
            if suppressed[i]:
                continue
            keep.append(i)
            # Vectorized: squared distance from pts[i] to all unsuppressed candidates after i
            remaining = np.nonzero(~suppressed)[0]
            remaining = remaining[remaining > i]
            if len(remaining) == 0:
                break
            diff = pts[remaining] - pts[i]
            d2 = (diff * diff).sum(axis=1)
            suppressed[remaining[d2 < d2_threshold]] = True

        keep_arr = np.array(keep, dtype=np.intp)
        return pts[keep_arr], conf[keep_arr]

    def predict(
        self,
        frame: np.ndarray,
        conf_threshold: Optional[float] = None,
        nms_distance: Optional[float] = None,
        density_regime: Optional[str] = None,
        max_height_override: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray, int, float, float]:
        """
        Predict crowd points.

        Returns:
            points_xy: [N, 2] in (x, y)
            confidences: [N]
            count: int
            avg_confidence: float
            conf_std: float
        """
        if self.model is None:
            return np.empty((0, 2), dtype=np.float32), np.empty((0,), dtype=np.float32), 0, 0.0, 0.0

        h0, w0 = frame.shape[:2]
        max_h = self._resolve_max_height(density_regime, max_height_override)
        ratio = 1.0
        frame_input = frame

        if h0 > max_h:
            ratio = max_h / float(h0)
            frame_input = cv2.resize(frame, (int(w0 * ratio), max_h), interpolation=cv2.INTER_LINEAR)

        # PET preprocessing
        img_rgb = cv2.cvtColor(frame_input, cv2.COLOR_BGR2RGB)
        img_tensor = torch.from_numpy(img_rgb).permute(2, 0, 1).float() / 255.0
        mean = torch.tensor([0.485, 0.456, 0.406], dtype=img_tensor.dtype).view(3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225], dtype=img_tensor.dtype).view(3, 1, 1)
        img_tensor = (img_tensor - mean) / std
        samples = nested_tensor_from_tensor_list([img_tensor]).to(self.device)

        with torch.no_grad():
            outputs = self.model(samples, test=True)
            logits = outputs["pred_logits"][0]  # [N, 2]
            scores = F.softmax(logits, dim=-1)[:, 1]  # [N]
            points_yx_norm = outputs["pred_points"][0]  # [N, 2], normalized (y, x)
            padded_h, padded_w = outputs.get("img_shape", samples.tensors.shape[-2:])

        conf_thr = self.conf_threshold if conf_threshold is None else float(conf_threshold)
        keep = scores >= conf_thr
        scores = scores[keep].detach().cpu().numpy().astype(np.float32)
        points_yx_norm = points_yx_norm[keep].detach().cpu().numpy().astype(np.float32)

        if len(points_yx_norm) == 0:
            return np.empty((0, 2), dtype=np.float32), np.empty((0,), dtype=np.float32), 0, 0.0, 0.0

        # normalized (y,x) -> pixel (x,y)
        ys = points_yx_norm[:, 0] * float(padded_h)
        xs = points_yx_norm[:, 1] * float(padded_w)
        points_xy = np.stack([xs, ys], axis=1).astype(np.float32)

        # clip to resized frame extents
        h1, w1 = frame_input.shape[:2]
        points_xy[:, 0] = np.clip(points_xy[:, 0], 0, w1 - 1)
        points_xy[:, 1] = np.clip(points_xy[:, 1], 0, h1 - 1)

        # map back to original frame size
        # Avoid direct float equality checks; use approximate comparison
        if not np.isclose(ratio, 1.0):
            points_xy /= ratio
            points_xy[:, 0] = np.clip(points_xy[:, 0], 0, w0 - 1)
            points_xy[:, 1] = np.clip(points_xy[:, 1], 0, h0 - 1)

        nms_dist = self.nms_distance if nms_distance is None else float(nms_distance)
        points_xy, scores = self._apply_nms(points_xy, scores, nms_dist)

        count = int(len(points_xy))
        if count > 0:
            avg_conf = float(np.mean(scores))
            conf_std = float(np.std(scores))
        else:
            avg_conf, conf_std = 0.0, 0.0

        if np.random.random() < 0.1:
            logger.info(
                f"[PET] Detected {count} people | conf=[{scores.min():.3f},{scores.max():.3f}] "
                f"avg={avg_conf:.3f}, std={conf_std:.3f}, thr={conf_thr:.2f}, nms={nms_dist:.1f}"
            )

        return points_xy, scores, count, avg_conf, conf_std

