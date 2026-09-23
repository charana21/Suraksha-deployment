"""
Unified Fusion Module for Crowd Counting
=========================================
Centralized fusion logic to ensure consistency across all implementations:
- models/model_wrapper.py
- services/crowd_analyzer.py
- services/gpu_worker.py
- test_model_accuracy.py

This module implements regime-based adaptive fusion that:
1. Detects density regime (SPARSE/LOW/MEDIUM/HIGH) using multiple indicators
2. Applies regime-specific fusion weights
3. Handles edge cases like PET hallucinations
"""

from typing import Tuple, Dict, Optional
import numpy as np
from utils.count_calibration import calibrate_fused_count

def _get_density_regime_thresholds(settings: Optional[object]) -> Dict[str, float]:
    if settings:
        return {
            "sparse_max": getattr(settings, 'density_regime_sparse_max', 15),
            "low_max": getattr(settings, 'density_regime_low_max', 50),
            "medium_max": getattr(settings, 'density_regime_medium_max', 120),
            "occ_low_max": getattr(settings, 'yolo_occupancy_low_max', 0.05),
            "occ_medium_max": getattr(settings, 'yolo_occupancy_medium_max', 0.15),
            "occ_high_max": getattr(settings, 'yolo_occupancy_high_max', 0.30),
        }
    return {
        "sparse_max": 15, "low_max": 50, "medium_max": 120,
        "occ_low_max": 0.05, "occ_medium_max": 0.15, "occ_high_max": 0.30,
    }


def _score_count_indicator(yolo_count: int, pet_count: int, t: Dict[str, float], scores: Dict[str, float]) -> None:
    # Indicator 1: Count-based (weight: 2.0)
    count_based = max(yolo_count, pet_count)
    if count_based > t["medium_max"]:
        scores["HIGH"] += 2.0
    elif count_based > t["low_max"]:
        scores["MEDIUM"] += 2.0
    elif count_based > t["sparse_max"]:
        scores["LOW"] += 2.0
    else:
        scores["SPARSE"] += 2.0


def _score_occupancy_indicator(yolo_occupancy: float, t: Dict[str, float], scores: Dict[str, float]) -> None:
    # Indicator 2: Occupancy-based (weight: 1.5)
    # High occupancy = dense crowd even if YOLO count is low (due to occlusion)
    if yolo_occupancy > t["occ_high_max"]:
        scores["HIGH"] += 1.5
    elif yolo_occupancy > t["occ_medium_max"]:
        scores["MEDIUM"] += 1.5
    elif yolo_occupancy > t["occ_low_max"]:
        scores["LOW"] += 1.5
    else:
        scores["SPARSE"] += 1.5


def _score_confidence_indicator(yolo_count: int, yolo_avg_conf: float, scores: Dict[str, float]) -> None:
    # Indicator 3: YOLO confidence-based (weight: 1.0)
    # Low average confidence when YOLO detects something = occlusion = dense
    if yolo_count <= 5:  # Only consider when YOLO sees some people
        return
    if yolo_avg_conf < 0.25:
        # Very low confidence = heavy occlusion = HIGH
        scores["HIGH"] += 1.0
    elif yolo_avg_conf < 0.35:
        scores["MEDIUM"] += 0.5
        scores["HIGH"] += 0.5
    elif yolo_avg_conf < 0.45:
        scores["MEDIUM"] += 1.0


def _score_ratio_indicator(yolo_count: int, pet_count: int, scores: Dict[str, float]) -> None:
    # Indicator 4: PET to YOLO ratio (weight: 0.5)
    # High ratio suggests YOLO is missing people (dense crowd)
    if yolo_count <= 0:
        return
    ratio = pet_count / yolo_count
    if ratio > 3.0:
        scores["HIGH"] += 0.5
    elif ratio > 2.0:
        scores["MEDIUM"] += 0.5


def compute_density_regime(
    yolo_count: int,
    pet_count: int,
    yolo_occupancy: float,
    yolo_avg_conf: float,
    settings: Optional[object] = None
) -> str:
    """
    Determine density regime using multiple indicators.

    Indicators:
    1. Count-based: max(yolo_count, pet_count)
    2. Occupancy-based: YOLO bbox coverage of frame
    3. YOLO confidence: Low avg confidence suggests occlusion (dense crowd)

    Args:
        yolo_count: Number of YOLO detections
        pet_count: Number of PET point predictions
        yolo_occupancy: Fraction of frame covered by YOLO bboxes (0-1)
        yolo_avg_conf: Average confidence of YOLO detections (0-1)
        settings: Config settings object (optional, uses defaults if None)

    Returns:
        str: "SPARSE", "LOW", "MEDIUM", or "HIGH"
    """
    thresholds = _get_density_regime_thresholds(settings)

    # Regime scoring system (each indicator votes)
    regime_scores = {"SPARSE": 0.0, "LOW": 0.0, "MEDIUM": 0.0, "HIGH": 0.0}

    _score_count_indicator(yolo_count, pet_count, thresholds, regime_scores)
    _score_occupancy_indicator(yolo_occupancy, thresholds, regime_scores)
    _score_confidence_indicator(yolo_count, yolo_avg_conf, regime_scores)
    _score_ratio_indicator(yolo_count, pet_count, regime_scores)

    # Return highest scoring regime
    return max(regime_scores, key=regime_scores.get)


def detect_hallucination(
    pet_avg_conf: float,
    pet_conf_std: float,
    pet_count: int,
    yolo_count: int,
    settings: Optional[object] = None
) -> bool:
    """
    Detect if PET is likely hallucinating.

    Hallucination patterns:
    1. Low confidence std + low mean confidence = uniform weak predictions
    2. Very high PET count with very low YOLO count and low confidence

    Args:
        pet_avg_conf: Average PET confidence
        pet_conf_std: Standard deviation of PET confidences
        pet_count: PET prediction count
        yolo_count: YOLO detection count
        settings: Config settings object

    Returns:
        bool: True if hallucination is likely
    """
    if settings:
        std_thresh = getattr(settings, 'pet_hallucination_conf_std_threshold', 0.05)
        mean_thresh = getattr(settings, 'pet_hallucination_mean_conf_threshold', 0.55)
    else:
        std_thresh, mean_thresh = 0.05, 0.55

    # Pattern 1: Low std + low mean (uniform weak predictions)
    if pet_conf_std < std_thresh and pet_avg_conf < mean_thresh and pet_avg_conf > 0:
        # Additional check: PET sees significantly more than YOLO
        if pet_count > max(yolo_count * 2, 20):
            return True

    # Pattern 2: Extreme ratio with very low confidence
    if yolo_count > 0 and pet_count > yolo_count * 5 and pet_avg_conf < 0.45:
        return True

    return False


def _get_fusion_weights(settings: Optional[object]) -> Tuple[float, float, float, float]:
    # PET is often more accurate, so defaults favor PET across all regimes
    if settings:
        return (
            getattr(settings, 'fusion_weight_sparse', 0.5),
            getattr(settings, 'fusion_weight_low', 0.6),
            getattr(settings, 'fusion_weight_medium', 0.75),
            getattr(settings, 'fusion_weight_high', 0.95),
        )
    return 0.5, 0.6, 0.75, 0.95


def _sparse_zero_yolo_guard(
    yolo_count: int,
    pet_count: int,
    pet_avg_conf: float,
    pet_conf_std: float,
    yolo_occupancy: float,
    regime: str,
    settings: Optional[object],
) -> Optional[Tuple[int, str, str]]:
    """Sparse guard for YOLO=0 frames.

    In low-crowd scenes, PET can produce small phantom counts even with plausible confidence.
    If YOLO sees nothing and occupancy is near-zero, aggressively suppress small PET-only counts.
    Returns None if the guard does not apply.
    """
    if settings:
        sparse_zero_max = getattr(settings, 'pet_sparse_zero_yolo_max_count', 15)
        sparse_zero_conf = getattr(settings, 'pet_sparse_zero_yolo_conf_threshold', 0.82)
        sparse_zero_min_std = getattr(settings, 'pet_sparse_zero_yolo_min_std', 0.10)
    else:
        sparse_zero_max = 15
        sparse_zero_conf = 0.82
        sparse_zero_min_std = 0.10

    if not (yolo_count == 0 and yolo_occupancy < 0.01 and pet_count <= sparse_zero_max):
        return None

    if pet_count == 0:
        return 0, "SPARSE_ZERO_YOLO -> 0", regime

    # Keep a single confident point as one person; suppress weak multi-point noise.
    if pet_count == 1 and pet_avg_conf >= sparse_zero_conf:
        return 1, f"SPARSE_ZERO_YOLO_SINGLE (conf={pet_avg_conf:.2f}) -> 1", regime

    if pet_avg_conf >= sparse_zero_conf and pet_conf_std >= sparse_zero_min_std and pet_count <= 3:
        return 1, f"SPARSE_ZERO_YOLO_STRICT (conf={pet_avg_conf:.2f}, std={pet_conf_std:.2f}) -> 1", regime

    return 0, f"SPARSE_ZERO_YOLO_SUPPRESS (conf={pet_avg_conf:.2f}, std={pet_conf_std:.2f}) -> 0", regime


def _pet_dense_scene_guard(
    yolo_occupancy: float,
    pet_count: int,
    regime: str,
    settings: Optional[object],
) -> Optional[Tuple[int, str, str]]:
    """PET dense-scene fusion guard.

    For very dense scenes PET-only often outperforms blended fusion.
    Returns None if the guard does not apply.
    """
    pet_guard_enabled = False
    density_model = ""
    if settings:
        pet_guard_enabled = bool(getattr(settings, 'fusion_pet_guard_enabled', True))
        density_model = str(getattr(settings, 'density_model', '')).lower()

    if not (pet_guard_enabled and density_model == "pet"):
        return None

    min_count = int(getattr(settings, 'fusion_pet_guard_min_count', 220))
    min_occupancy = float(getattr(settings, 'fusion_pet_guard_min_occupancy', 0.18))
    dense_scene = (
        pet_count >= min_count or
        (regime == "HIGH" and yolo_occupancy >= min_occupancy)
    )
    if not dense_scene:
        return None

    final = max(0, int(pet_count))
    rule = (
        f"PET_GUARD_DENSE (regime={regime}, count={pet_count}, occ={yolo_occupancy:.2f}, "
        f"min_count={min_count}, min_occ={min_occupancy:.2f}) -> PET_ONLY"
    )

    if bool(getattr(settings, 'fusion_pet_guard_skip_calibration', True)):
        return final, f"{rule} | CAL_SKIP", regime

    calibrated, multiplier, calib_bin = calibrate_fused_count(
        raw_count=final,
        pet_count=pet_count,
        settings=settings
    )
    if calibrated != final:
        rule = f"{rule} | CAL[{calib_bin}] x{multiplier:.2f}"
    return calibrated, rule, regime


def _fuse_high_regime(
    yolo_count: int, pet_count: int, pet_avg_conf: float, pet_conf_std: float,
    is_hallucination: bool, w_high: float,
) -> Tuple[int, str]:
    if is_hallucination:
        # Hallucination in HIGH regime - use YOLO with multiplier
        # (YOLO likely undercounting due to occlusion)
        final = int(yolo_count * 1.5) if yolo_count > 10 else max(yolo_count, int(pet_count * 0.3))
        rule = f"HIGH_HALLUCINATION (conf={pet_avg_conf:.2f}, std={pet_conf_std:.2f}) -> YOLO*1.5"
    elif pet_avg_conf >= 0.5:
        # High confidence in HIGH regime - full PET trust
        final = pet_count
        rule = f"HIGH_CONFIDENT (conf={pet_avg_conf:.2f}) -> 100% PET"
    elif pet_avg_conf >= 0.35:
        # Moderate confidence in HIGH regime - 90% PET
        weight = w_high
        final = int((1 - weight) * yolo_count + weight * pet_count)
        rule = f"HIGH (conf={pet_avg_conf:.2f}) -> {int(weight*100)}% PET"
    else:
        # Low confidence in HIGH regime but not hallucination
        # Still trust PET more but with caution
        weight = 0.7
        final = int((1 - weight) * yolo_count + weight * pet_count)
        rule = f"HIGH_LOW_CONF (conf={pet_avg_conf:.2f}) -> 70% PET"
    return final, rule


def _fuse_medium_regime(
    yolo_count: int, pet_count: int, pet_avg_conf: float, is_hallucination: bool, w_medium: float,
) -> Tuple[int, str]:
    if is_hallucination:
        # Hallucination in MEDIUM regime - still give PET some weight
        final = int(0.5 * yolo_count + 0.5 * pet_count)
        rule = "MEDIUM_HALLUCINATION -> 50/50"
    elif pet_avg_conf >= 0.45:
        # Good confidence - use config weight (75% PET)
        weight = w_medium
        final = int((1 - weight) * yolo_count + weight * pet_count)
        rule = f"MEDIUM_CONFIDENT (conf={pet_avg_conf:.2f}) -> {int(weight*100)}% PET"
    else:
        # Lower confidence but still favor PET (use slightly reduced weight)
        weight = 0.6  # Still favor PET
        final = int((1 - weight) * yolo_count + weight * pet_count)
        rule = f"MEDIUM_LOW_CONF (conf={pet_avg_conf:.2f}) -> {int(weight*100)}% PET"
    return final, rule


def _fuse_low_regime(
    yolo_count: int, pet_count: int, pet_avg_conf: float, is_hallucination: bool, w_low: float,
) -> Tuple[int, str]:
    if is_hallucination:
        # Hallucination in LOW regime - balanced approach
        final = int(0.6 * yolo_count + 0.4 * pet_count)
        rule = "LOW_HALLUCINATION -> 60% YOLO"
    elif pet_avg_conf >= 0.5:
        # Good confidence - use config weight (60% PET)
        weight = w_low
        final = int((1 - weight) * yolo_count + weight * pet_count)
        rule = f"LOW_CONFIDENT (conf={pet_avg_conf:.2f}) -> {int(weight*100)}% PET"
    else:
        # Lower confidence but still trust PET (use config weight)
        weight = w_low
        final = int((1 - weight) * yolo_count + weight * pet_count)
        rule = f"LOW (conf={pet_avg_conf:.2f}) -> {int(weight*100)}% PET"
    return final, rule


def _fuse_sparse_regime(
    yolo_count: int, pet_count: int, pet_avg_conf: float, is_hallucination: bool, w_sparse: float,
) -> Tuple[int, str]:
    if is_hallucination:
        # Hallucination in SPARSE - still give PET some weight
        final = int(0.7 * yolo_count + 0.3 * pet_count)
        rule = "SPARSE_HALLUCINATION -> 70% YOLO"
        return final, rule

    if 0 < yolo_count <= 2:
        # Anchor to YOLO for very low-population scenes.
        # This prevents single-person scenes from jumping to 3-10 due to PET phantom points.
        if pet_avg_conf < 0.78:
            final = yolo_count
            rule = f"SPARSE_YOLO_ANCHOR (conf={pet_avg_conf:.2f}) -> YOLO"
        else:
            weight = min(w_sparse, 0.3)
            final = int((1 - weight) * yolo_count + weight * pet_count)
            rule = f"SPARSE_YOLO_ANCHOR_CONF (conf={pet_avg_conf:.2f}) -> {int((1-weight)*100)}% YOLO"

        # Hard cap for sparse scenes when PET is much larger than YOLO.
        if pet_count > yolo_count * 3:
            max_allowed = max(yolo_count + 2, yolo_count * 3)
            final = min(final, max_allowed)
            rule = f"{rule}, CAP<={max_allowed}"
        return final, rule

    if pet_count < 5 and yolo_count < 5:
        # Both see very few - use weighted average (50/50)
        weight = w_sparse
        final = int((1 - weight) * yolo_count + weight * pet_count)
        # Ensure at least one if either model detected something
        if final == 0 and (yolo_count > 0 or pet_count > 0):
            final = max(yolo_count, pet_count)
        rule = f"SPARSE_FEW -> {int(weight*100)}% PET"
        return final, rule

    # Use config weight (50% PET)
    weight = w_sparse
    final = int((1 - weight) * yolo_count + weight * pet_count)
    rule = f"SPARSE (conf={pet_avg_conf:.2f}) -> {int(weight*100)}% PET"
    return final, rule


def _apply_regime_fusion(
    regime: str, yolo_count: int, pet_count: int, pet_avg_conf: float, pet_conf_std: float,
    is_hallucination: bool, weights: Tuple[float, float, float, float],
) -> Tuple[int, str]:
    w_sparse, w_low, w_medium, w_high = weights
    if regime == "HIGH":
        return _fuse_high_regime(yolo_count, pet_count, pet_avg_conf, pet_conf_std, is_hallucination, w_high)
    if regime == "MEDIUM":
        return _fuse_medium_regime(yolo_count, pet_count, pet_avg_conf, is_hallucination, w_medium)
    if regime == "LOW":
        return _fuse_low_regime(yolo_count, pet_count, pet_avg_conf, is_hallucination, w_low)
    return _fuse_sparse_regime(yolo_count, pet_count, pet_avg_conf, is_hallucination, w_sparse)


def compute_fusion(
    yolo_count: int,
    pet_count: int,
    pet_avg_conf: float,
    yolo_occupancy: float = 0.0,
    yolo_avg_conf: float = 0.5,
    pet_conf_std: float = 0.1,
    settings: Optional[object] = None
) -> Tuple[int, str, str]:
    """
    Compute final crowd count using regime-based adaptive fusion.

    Args:
        yolo_count: Number of YOLO head detections
        pet_count: Number of PET point predictions
        pet_avg_conf: Average confidence of PET predictions
        yolo_occupancy: Fraction of frame covered by YOLO bboxes
        yolo_avg_conf: Average confidence of YOLO detections
        pet_conf_std: Standard deviation of PET confidences
        settings: Config settings object

    Returns:
        Tuple of (final_count, fusion_rule, density_regime)
    """
    weights = _get_fusion_weights(settings)

    # Step 1: Determine density regime
    regime = compute_density_regime(
        yolo_count, pet_count, yolo_occupancy, yolo_avg_conf, settings
    )

    # Step 2: Check for PET hallucination
    is_hallucination = detect_hallucination(
        pet_avg_conf, pet_conf_std, pet_count, yolo_count, settings
    )

    # Step 2b: Sparse guard for YOLO=0 frames
    sparse_zero_result = _sparse_zero_yolo_guard(
        yolo_count, pet_count, pet_avg_conf, pet_conf_std, yolo_occupancy, regime, settings
    )
    if sparse_zero_result is not None:
        return sparse_zero_result

    # Step 2c: PET dense-scene fusion guard
    pet_guard_result = _pet_dense_scene_guard(yolo_occupancy, pet_count, regime, settings)
    if pet_guard_result is not None:
        return pet_guard_result

    # Step 3: Apply regime-specific fusion
    final, rule = _apply_regime_fusion(
        regime, yolo_count, pet_count, pet_avg_conf, pet_conf_std, is_hallucination, weights
    )

    # Ensure non-negative before calibration
    final = max(0, final)

    # Step 4: Post-fusion calibration for systematic undercount correction
    calibrated, multiplier, calib_bin = calibrate_fused_count(
        raw_count=final,
        pet_count=pet_count,
        settings=settings
    )
    if calibrated != final:
        rule = f"{rule} | CAL[{calib_bin}] x{multiplier:.2f}"

    return calibrated, rule, regime


def compute_yolo_metrics(detections: list, frame_height: int, frame_width: int) -> Dict:
    """
    Compute YOLO metrics from detections.

    Args:
        detections: List of detection dicts with 'bbox' and 'confidence' keys
        frame_height: Frame height in pixels
        frame_width: Frame width in pixels

    Returns:
        Dict with 'count', 'avg_confidence', 'occupancy_ratio'
    """
    count = len(detections)

    if count == 0:
        return {
            'count': 0,
            'avg_confidence': 0.0,
            'occupancy_ratio': 0.0
        }

    frame_area = frame_height * frame_width

    total_bbox_area = 0.0
    total_confidence = 0.0

    for det in detections:
        bbox = det.get('bbox', [0, 0, 0, 0])
        x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
        total_bbox_area += (x2 - x1) * (y2 - y1)
        total_confidence += det.get('confidence', 0.5)

    return {
        'count': count,
        'avg_confidence': total_confidence / count,
        'occupancy_ratio': total_bbox_area / frame_area if frame_area > 0 else 0.0
    }


def compute_pet_metrics(confidences: np.ndarray) -> Dict:
    """
    Compute PET metrics from confidence array.

    Args:
        confidences: numpy array of confidence scores

    Returns:
        Dict with 'count', 'avg_confidence', 'conf_std'
    """
    if len(confidences) == 0:
        return {
            'count': 0,
            'avg_confidence': 0.0,
            'conf_std': 0.0
        }

    return {
        'count': len(confidences),
        'avg_confidence': float(np.mean(confidences)),
        'conf_std': float(np.std(confidences))
    }
