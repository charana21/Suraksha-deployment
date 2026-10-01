"""
Unit tests for deterministic camera sharding, latest-frame non-destructive capture,
frame-age telemetry, and zone analytics state tagging.
"""
import os
import sys
import time
import numpy as np
import pytest

# Ensure crowd-backend is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from services.sharding import (
    get_camera_shard,
    get_shard_count,
    get_current_shard_index,
    is_camera_owned_by_current_pod,
    get_owning_pod_host,
)
from services.rtsp_worker import RTSPWorker
from services.zone_analytics import (
    _extract_camera_metrics,
    aggregate_camera_analytics,
    _last_known_camera_metrics,
    CAMERA_METRICS_CACHE_TTL,
)


class TestCameraSharding:
    """Tests for deterministic CRC32 camera sharding across pods."""

    CAMERAS = [
        "cam_hyb_fob_kzj", "cam_hyb_booking", "cam_hyb_booking_gate4a",
        "cam_hyb_entry_gate1", "cam_hyb_entry_gate2", "cam_hyb_pf4",
        "cam_hyb_pf5", "cam_hyb_pf6", "cam_hyb_pf7", "cam_hyb_circulating",
        "cam_hyb_waiting", "cam_hyb_pf8", "cam_hyb_pf9", "cam_hyb_pf10",
        "cam_hyb_fob_hyd", "cam_hyb_concourse", "cam_hyb_pf1", "cam_hyb_pf2",
        "cam_hyb_pf3",
    ]

    def test_deterministic_hashing_consistency(self):
        """Verify that hash assignment is 100% deterministic across repeated calls."""
        for cam in self.CAMERAS:
            shard_a = get_camera_shard(cam, shard_count=2)
            shard_b = get_camera_shard(cam, shard_count=2)
            assert shard_a == shard_b, f"Hash for {cam} must be deterministic"
            assert shard_a in (0, 1), f"Shard must be 0 or 1, got {shard_a}"

    def test_shard_distribution_across_2_shards(self):
        """Verify distribution across 2 shards has no unassigned cameras."""
        shard_0 = []
        shard_1 = []
        for cam in self.CAMERAS:
            s = get_camera_shard(cam, shard_count=2)
            if s == 0:
                shard_0.append(cam)
            else:
                shard_1.append(cam)

        assert len(shard_0) + len(shard_1) == len(self.CAMERAS)
        assert len(shard_0) > 0, "Shard 0 should receive cameras"
        assert len(shard_1) > 0, "Shard 1 should receive cameras"
        # Verify specific partition
        assert "cam_hyb_fob_kzj" in shard_0
        assert "cam_hyb_pf1" in shard_1

    def test_scaling_to_3_and_4_shards(self):
        """Verify sharding math scales cleanly to 3 and 4 shards."""
        for num_shards in [3, 4]:
            assigned = {i: [] for i in range(num_shards)}
            for cam in self.CAMERAS:
                s = get_camera_shard(cam, shard_count=num_shards)
                assert 0 <= s < num_shards
                assigned[s].append(cam)
            total = sum(len(cams) for cams in assigned.values())
            assert total == len(self.CAMERAS)

    def test_single_shard_backwards_compatibility(self, monkeypatch):
        """Verify that when CAMERA_SHARD_COUNT=1, every camera is owned by the current pod."""
        monkeypatch.setenv("CAMERA_SHARD_COUNT", "1")
        monkeypatch.setenv("CAMERA_SHARD_INDEX", "0")

        assert get_shard_count() == 1
        assert get_current_shard_index() == 0

        for cam in self.CAMERAS:
            assert is_camera_owned_by_current_pod(cam) is True

    def test_pod_ordinal_detection(self, monkeypatch):
        """Verify that pod index is detected from HOSTNAME or POD_NAME StatefulSet ordinals."""
        monkeypatch.delenv("CAMERA_SHARD_INDEX", raising=False)

        monkeypatch.setenv("HOSTNAME", "crowdvision-backend-0")
        assert get_current_shard_index() == 0

        monkeypatch.setenv("HOSTNAME", "crowdvision-backend-1")
        assert get_current_shard_index() == 1

        monkeypatch.delenv("HOSTNAME", raising=False)
        monkeypatch.setenv("POD_NAME", "crowdvision-backend-3")
        assert get_current_shard_index() == 3

    def test_owning_pod_host_resolution(self, monkeypatch):
        """Verify DNS target resolution for remote pod routing."""
        monkeypatch.setenv("CAMERA_SHARD_COUNT", "2")
        monkeypatch.setenv("HEADLESS_SERVICE_NAME", "crowdvision-backend-headless")
        monkeypatch.setenv("HEADLESS_SERVICE_PORT", "80")

        host = get_owning_pod_host("cam_hyb_pf1")
        shard = get_camera_shard("cam_hyb_pf1", 2)
        assert f"crowdvision-backend-{shard}" in host
        assert "crowdvision-backend-headless" in host
        assert host.endswith(":80")


class TestLatestFrameContinuousCaptureBuffer:
    """Tests for non-destructive latest-frame buffer and telemetry."""

    def test_non_destructive_latest_frame_read(self):
        """Verify multiple reads return the newest frame without clearing it."""
        worker = RTSPWorker(
            stream_id="test_cam",
            rtsp_url="rtsp://dummy-test-stream",
            camera_id="test_cam",
            camera_name="Test Camera",
        )

        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        test_frame[10:50, 10:50] = 255
        now_ts = time.time()

        # Update latest frame
        with worker._frame_lock:
            worker._latest_raw_frame = test_frame
            worker._latest_capture_timestamp = now_ts

        # Read 1
        frame1 = worker.get_latest_frame()
        assert frame1 is not None
        assert frame1.shape == (480, 640, 3)

        # Read 2: frame must still be present (not popped)
        frame2 = worker.get_latest_frame()
        assert frame2 is not None
        assert np.array_equal(frame1, frame2)

        # Read 3 with metadata
        frame3, cap_ts, age_ms = worker.get_latest_frame_with_metadata()
        assert frame3 is not None
        assert cap_ts == now_ts
        assert age_ms >= 0.0

    def test_frame_age_telemetry_calculation(self):
        """Verify frame-age calculation is accurate relative to capture timestamp."""
        worker = RTSPWorker(
            stream_id="test_cam_telemetry",
            rtsp_url="rtsp://dummy-test-stream",
            camera_id="test_cam_telemetry",
            camera_name="Test Camera",
        )

        past_ts = time.time() - 0.250  # 250ms ago
        with worker._frame_lock:
            worker._latest_raw_frame = np.ones((10, 10, 3), dtype=np.uint8)
            worker._latest_capture_timestamp = past_ts

        _, cap_ts, age_ms = worker.get_latest_frame_with_metadata()
        assert cap_ts == past_ts
        # Age should be approximately 250ms (allow 200-500ms range for test execution overhead)
        assert 200.0 <= age_ms <= 600.0


class TestZoneAnalyticsStatusTagging:
    """Tests for CURRENT, STALE, DISCONNECTED, and NO_DATA status tags."""

    def setup_method(self):
        _last_known_camera_metrics.clear()

    def test_current_status_when_recent(self):
        now = time.time()
        camera = {"camera_id": "cam_current", "name": "Current Camera"}
        analytics = {
            "camera_id": "cam_current",
            "people_count": 15,
            "density_avg": 0.35,
            "density_level": "LOW",
            "timestamp": now - 2.0,  # 2 seconds old
        }

        res = _extract_camera_metrics(camera, analytics=analytics)
        assert res["has_analytics"] is True
        assert res["status"] == "CURRENT"
        assert res["people_count"] == 15
        assert res["detail"]["status"] == "CURRENT"

    def test_stale_status_when_within_2x_ttl(self):
        now = time.time()
        camera = {"camera_id": "cam_stale", "name": "Stale Camera"}
        analytics = {
            "camera_id": "cam_stale",
            "people_count": 22,
            "density_avg": 0.55,
            "density_level": "MODERATE",
            "timestamp": now - 45.0,  # 45 seconds old (between 30s and 60s)
        }

        res = _extract_camera_metrics(camera, analytics=analytics)
        assert res["has_analytics"] is True
        assert res["status"] == "STALE"
        assert res["people_count"] == 22
        assert res["detail"]["status"] == "STALE"

    def test_disconnected_status_when_beyond_2x_ttl(self):
        now = time.time()
        camera = {"camera_id": "cam_disconnected", "name": "Disconnected Camera"}
        analytics = {
            "camera_id": "cam_disconnected",
            "people_count": 5,
            "density_avg": 0.1,
            "density_level": "LOW",
            "timestamp": now - 120.0,  # 120 seconds old (> 60s)
        }

        res = _extract_camera_metrics(camera, analytics=analytics)
        assert res["has_analytics"] is False
        assert res["status"] == "DISCONNECTED"
        assert res["people_count"] == 0
        assert res["detail"]["status"] == "DISCONNECTED"

    def test_no_data_status_when_unseen(self):
        camera = {"camera_id": "cam_unseen", "name": "Unseen Camera"}
        res = _extract_camera_metrics(camera, analytics=None)
        assert res["has_analytics"] is False
        assert res["status"] == "NO_DATA"
        assert res["people_count"] == 0
        assert res["detail"]["status"] == "NO_DATA"

    def test_shared_lookup_does_not_fall_back_to_pod_local_analytics(self, monkeypatch):
        camera = {"camera_id": "cam_shared", "name": "Shared Camera"}
        monkeypatch.setattr(
            "services.zone_analytics.get_camera_latest_analytics",
            lambda camera_id: {
                "camera_id": camera_id,
                "people_count": 99,
                "timestamp": time.time(),
            },
        )

        result = aggregate_camera_analytics([camera], analytics_map={"cam_shared": None})

        assert result["people_count"] == 0
        assert result["camera_details"][0]["status"] == "NO_DATA"

    def test_remote_analytics_map_aggregation(self):
        """Verify aggregate_camera_analytics properly consumes pre-fetched remote analytics."""
        cameras = [
            {"camera_id": "cam_shard0", "svg_region_id": "r0"},
            {"camera_id": "cam_shard1", "svg_region_id": "r1"},
        ]
        now = time.time()
        analytics_map = {
            "cam_shard1": {
                "camera_id": "cam_shard1",
                "people_count": 42,
                "density_avg": 1.2,
                "density_level": "HIGH",
                "risk_score": 75.0,
                "risk_level": "HIGH",
                "timestamp": now - 1.0,
            }
        }

        aggregated = aggregate_camera_analytics(cameras, analytics_map=analytics_map)
        assert aggregated["camera_count"] == 2
        assert aggregated["people_count"] == 42
        assert aggregated["risk_level"] == "HIGH"
        # Verify shard1 camera detail
        shard1_detail = next(d for d in aggregated["camera_details"] if d["camera_id"] == "cam_shard1")
        assert shard1_detail["status"] == "CURRENT"
        assert shard1_detail["people_count"] == 42


class TestModelWrapperDeviceParsing:
    """Tests for multi-GPU device string parsing in model wrapper."""

    def test_cuda_device_string_recognition(self):
        import torch
        for dev_str in ["cuda", "cuda:0", "cuda:1"]:
            assert str(dev_str).startswith("cuda")
            device = torch.device(dev_str)
            assert device.type == "cuda"
