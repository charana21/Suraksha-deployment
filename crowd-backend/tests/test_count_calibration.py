"""Unit tests for post-fusion count calibration."""

from types import SimpleNamespace
from utils.count_calibration import calibrate_fused_count

def _settings(**overrides):
    base = {
        "count_calibration_enabled": True,
        "count_calibration_min_raw_count": 3,
        "count_calibration_max_multiplier": 1.4,
        "count_calibration_bin1_max": 50,
        "count_calibration_bin2_max": 200,
        "count_calibration_bin3_max": 500,
        "count_calibration_scale_bin1": 1.12,
        "count_calibration_scale_bin2": 1.28,
        "count_calibration_scale_bin3": 1.09,
        "count_calibration_scale_bin4": 1.19,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_disabled_keeps_raw_count():
    s = _settings(count_calibration_enabled=False)
    calibrated, multiplier, bin_label = calibrate_fused_count(120, pet_count=140, settings=s)
    assert calibrated == 120
    assert multiplier == 1.0
    assert bin_label == "disabled"


def test_small_raw_count_not_scaled():
    s = _settings()
    calibrated, multiplier, bin_label = calibrate_fused_count(2, pet_count=100, settings=s)
    assert calibrated == 2
    assert multiplier == 1.0
    assert bin_label == "small_raw"


def test_bin_scaling_uses_pet_anchor():
    s = _settings()
    # Raw fused value from medium regime, anchored by PET count in 50-200 bucket.
    calibrated, multiplier, bin_label = calibrate_fused_count(82, pet_count=98, settings=s)
    assert calibrated == 105
    assert round(multiplier, 2) == 1.28
    assert bin_label == "50-200"


def test_large_bucket_scaling():
    s = _settings()
    calibrated, multiplier, bin_label = calibrate_fused_count(600, pet_count=700, settings=s)
    assert calibrated == 714
    assert round(multiplier, 2) == 1.19
    assert bin_label == "500+"
