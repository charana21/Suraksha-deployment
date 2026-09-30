"""
Count calibration utilities for systematic undercount correction.

This module provides a lightweight, configurable post-fusion correction layer
that can be reused in runtime, testing, and notebook evaluation paths.
"""

from typing import Optional, Tuple


def _cfg(settings: Optional[object], name: str, default):
    """Read a setting safely with fallback."""
    if settings is None:
        return default
    return getattr(settings, name, default)


def get_count_calibration_multiplier(
    anchor_count: int,
    settings: Optional[object] = None
) -> Tuple[float, str]:
    """
    Select multiplier from piecewise bins with linear interpolation at boundaries.

    Uses a transition zone (±10 counts) around each boundary to prevent
    step-function jumps (e.g., count 49→50 used to jump from 1.12x to 1.28x,
    creating a 9-person spike from +1 raw count).
    """
    bin1_max = int(_cfg(settings, "count_calibration_bin1_max", 50))
    bin2_max = int(_cfg(settings, "count_calibration_bin2_max", 200))
    bin3_max = int(_cfg(settings, "count_calibration_bin3_max", 500))

    scale_bin1 = float(_cfg(settings, "count_calibration_scale_bin1", 1.12))
    scale_bin2 = float(_cfg(settings, "count_calibration_scale_bin2", 1.28))
    scale_bin3 = float(_cfg(settings, "count_calibration_scale_bin3", 1.09))
    scale_bin4 = float(_cfg(settings, "count_calibration_scale_bin4", 1.19))

    # Transition zone half-width (interpolate over ±10 counts around boundary)
    tz = 10

    def _lerp(count, boundary, scale_lo, scale_hi):
        """Linear interpolation in transition zone around boundary."""
        lo = boundary - tz
        hi = boundary + tz
        if count <= lo:
            return scale_lo
        if count >= hi:
            return scale_hi
        t = (count - lo) / (hi - lo)
        return scale_lo + t * (scale_hi - scale_lo)

    if anchor_count < bin1_max - tz:
        return scale_bin1, f"<{bin1_max}"
    if anchor_count < bin1_max + tz:
        m = _lerp(anchor_count, bin1_max, scale_bin1, scale_bin2)
        return m, f"~{bin1_max}"
    if anchor_count < bin2_max - tz:
        return scale_bin2, f"{bin1_max}-{bin2_max}"
    if anchor_count < bin2_max + tz:
        m = _lerp(anchor_count, bin2_max, scale_bin2, scale_bin3)
        return m, f"~{bin2_max}"
    if anchor_count < bin3_max - tz:
        return scale_bin3, f"{bin2_max}-{bin3_max}"
    if anchor_count < bin3_max + tz:
        m = _lerp(anchor_count, bin3_max, scale_bin3, scale_bin4)
        return m, f"~{bin3_max}"
    return scale_bin4, f"{bin3_max}+"


def calibrate_fused_count(
    raw_count: int,
    pet_count: Optional[int] = None,
    settings: Optional[object] = None
) -> Tuple[int, float, str]:
    """
    Apply configurable piecewise count calibration.

    Returns:
        calibrated_count, multiplier, bin_label
    """
    raw = max(0, int(raw_count))
    if raw == 0:
        return 0, 1.0, "zero"

    enabled = bool(_cfg(settings, "count_calibration_enabled", True))
    if not enabled:
        return raw, 1.0, "disabled"

    min_raw = int(_cfg(settings, "count_calibration_min_raw_count", 3))
    if raw < min_raw:
        return raw, 1.0, "small_raw"

    anchor = raw
    if pet_count is not None:
        try:
            pet_value = int(pet_count)
            if pet_value > 0:
                anchor = max(raw, pet_value)
        except (TypeError, ValueError):
            pass

    multiplier, bin_label = get_count_calibration_multiplier(anchor, settings)
    max_multiplier = float(_cfg(settings, "count_calibration_max_multiplier", 1.40))
    multiplier = max(0.5, min(multiplier, max_multiplier))

    calibrated = int(round(raw * multiplier))
    calibrated = max(0, calibrated)
    return calibrated, multiplier, bin_label
