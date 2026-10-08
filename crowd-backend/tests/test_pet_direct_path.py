from types import SimpleNamespace
import numpy as np
from models.model_wrapper import CrowdCountingModelWrapper

class _DummyYOLO:
    def detect_with_metrics(self, frame):
        return {
            "detections": [],
            "count": 2,
            "occupancy_ratio": 0.02,
            "avg_confidence": 0.8,
        }


def _make_wrapper(calibration_enabled: bool):
    wrapper = CrowdCountingModelWrapper.__new__(CrowdCountingModelWrapper)
    wrapper.yolo = _DummyYOLO()
    wrapper.density_model_type = "pet"
    wrapper.settings = SimpleNamespace(
        pet_use_adaptive_fusion=False,
        count_calibration_enabled=calibration_enabled,
        count_calibration_min_raw_count=3,
        count_calibration_bin1_max=50,
        count_calibration_bin2_max=200,
        count_calibration_bin3_max=500,
        count_calibration_scale_bin1=1.10,
        count_calibration_scale_bin2=1.0,
        count_calibration_scale_bin3=1.0,
        count_calibration_scale_bin4=1.0,
    )

    def _estimate_density(*args, **kwargs):
        density = np.ones((16, 16), dtype=np.float32)
        pet_points = np.array([[8.0, 8.0]], dtype=np.float32)
        return density, 0.85, 0.08, 40, {"mode": "pet"}, pet_points

    wrapper._estimate_density = _estimate_density
    return wrapper


def test_pet_direct_count_without_calibration():
    wrapper = _make_wrapper(calibration_enabled=False)
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    result = wrapper.predict(frame)

    assert result["final_count"] == 40
    assert result["fusion_rule"] == "PET_DIRECT"
    assert result["density_regime"] in {"SPARSE", "LOW", "MEDIUM", "HIGH"}


def test_pet_direct_count_with_calibration():
    wrapper = _make_wrapper(calibration_enabled=True)
    frame = np.zeros((32, 32, 3), dtype=np.uint8)
    result = wrapper.predict(frame)

    assert result["final_count"] == 44  # 40 * 1.10 (bin1)
    assert "PET_DIRECT" in result["fusion_rule"]
    assert "CAL[" in result["fusion_rule"]
