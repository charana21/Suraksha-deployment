"""
Unit tests for Homography Calibration Module

Tests cover:
- HomographyCalibration class initialization and transformations
- compute_homography() function with various inputs
- validate_homography() edge cases
- Batch operations
- Backward compatibility with PerspectiveCalibration interface
"""

import pytest
import numpy as np
import math
from typing import List
# Add project root to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.homography import (
    ReferencePoint,
    HomographyCalibration,
    compute_homography,
    validate_homography,
    create_homography_config
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def simple_rectangle_points() -> List[ReferencePoint]:
    """
    Simple 4-point rectangle mapping for testing.
    Pixel: 100x100 square at (100,100) to (200,200)
    World: 4m x 4m square at (0,0) to (4,4)
    """
    return [
        ReferencePoint(pixel=(100, 100), world=(0.0, 0.0)),
        ReferencePoint(pixel=(200, 100), world=(4.0, 0.0)),
        ReferencePoint(pixel=(200, 200), world=(4.0, 4.0)),
        ReferencePoint(pixel=(100, 200), world=(0.0, 4.0)),
    ]


@pytest.fixture
def perspective_points() -> List[ReferencePoint]:
    """
    Realistic FOB corridor perspective mapping.
    Near (bottom) is wider in pixels than far (top).
    """
    return [
        # Near edge (bottom of frame, wider in pixels)
        ReferencePoint(pixel=(100, 600), world=(0.0, 0.0)),
        ReferencePoint(pixel=(500, 600), world=(4.0, 0.0)),
        # Far edge (top of frame, narrower in pixels due to perspective)
        ReferencePoint(pixel=(200, 200), world=(0.0, 10.0)),
        ReferencePoint(pixel=(400, 200), world=(4.0, 10.0)),
    ]


@pytest.fixture
def calibration_config() -> dict:
    """Sample calibration config with homography"""
    return {
        'visible_area_m2': 40.0,
        'corridor_width_m': 4.0,
        'coverage_length_m': 10.0,
        'lane_count': 1,
        'camera_type': 'fob',
        'homography': {
            'enabled': True,
            'matrix': [
                [0.04, 0.0, -4.0],
                [0.0, 0.04, -4.0],
                [0.0, 0.0, 1.0]
            ],
            'reference_points': [
                {'pixel': [100, 100], 'world': [0.0, 0.0]},
                {'pixel': [200, 100], 'world': [4.0, 0.0]},
                {'pixel': [200, 200], 'world': [4.0, 4.0]},
                {'pixel': [100, 200], 'world': [0.0, 4.0]},
            ],
            'frame_size': [640, 480],
            'reprojection_error': 0.05,
            'calibrated_at': '2026-02-03T10:30:00Z',
            'calibrated_by': 'test'
        }
    }


@pytest.fixture
def config_without_homography() -> dict:
    """Config without homography (simple visible_area only)"""
    return {
        'visible_area_m2': 160.0,
        'corridor_width_m': 4.0,
        'coverage_length_m': 40.0,
        'lane_count': 1,
        'camera_type': 'fob'
    }


# =============================================================================
# Test compute_homography()
# =============================================================================

class TestComputeHomography:
    """Tests for compute_homography function"""

    def test_simple_rectangle(self, simple_rectangle_points):
        """Test homography computation with simple rectangle"""
        H, error, mask = compute_homography(simple_rectangle_points)

        assert H is not None
        assert H.shape == (3, 3)
        assert error < 0.1  # Should be very low for exact points
        assert mask is not None

    def test_minimum_points(self):
        """Test with exactly 4 points (minimum required)"""
        points = [
            ReferencePoint(pixel=(0, 0), world=(0.0, 0.0)),
            ReferencePoint(pixel=(100, 0), world=(5.0, 0.0)),
            ReferencePoint(pixel=(100, 100), world=(5.0, 5.0)),
            ReferencePoint(pixel=(0, 100), world=(0.0, 5.0)),
        ]

        H, error, mask = compute_homography(points)

        assert H is not None
        assert H.shape == (3, 3)

    def test_too_few_points(self):
        """Test that fewer than 4 points raises ValueError"""
        points = [
            ReferencePoint(pixel=(0, 0), world=(0.0, 0.0)),
            ReferencePoint(pixel=(100, 0), world=(5.0, 0.0)),
            ReferencePoint(pixel=(100, 100), world=(5.0, 5.0)),
        ]

        with pytest.raises(ValueError, match="At least 4"):
            compute_homography(points)

    def test_extra_points_with_noise(self, simple_rectangle_points):
        """Test with extra points including noise (RANSAC should handle)"""
        # Add some noisy extra points
        extra_points = simple_rectangle_points + [
            ReferencePoint(pixel=(150, 150), world=(2.0, 2.0)),  # Good point
            ReferencePoint(pixel=(180, 120), world=(3.2, 0.8)),  # Good point
            ReferencePoint(pixel=(999, 999), world=(100.0, 100.0)),  # Outlier
        ]

        H, error, mask = compute_homography(extra_points)

        assert H is not None
        # Error should still be reasonable (RANSAC should reject outlier)
        assert error < 1.0

    def test_perspective_points(self, perspective_points):
        """Test homography with perspective distortion"""
        H, error, mask = compute_homography(perspective_points)

        assert H is not None
        assert H.shape == (3, 3)
        assert error < 0.5  # Should still be low


# =============================================================================
# Test HomographyCalibration class
# =============================================================================

class TestHomographyCalibration:
    """Tests for HomographyCalibration class"""

    def test_initialization_with_homography(self, calibration_config):
        """Test initialization with homography config"""
        cal = HomographyCalibration("test_cam", calibration_config)

        assert cal.camera_id == "test_cam"
        assert cal.has_homography is True
        assert cal.visible_area_m2 == 40.0

    def test_initialization_without_homography(self, config_without_homography):
        """Test initialization without homography"""
        cal = HomographyCalibration("test_cam", config_without_homography)

        assert cal.camera_id == "test_cam"
        assert cal.has_homography is False
        assert cal.visible_area_m2 == 160.0

    def test_pixel_to_world(self, calibration_config):
        """Test pixel to world coordinate transformation"""
        cal = HomographyCalibration("test_cam", calibration_config)

        # Test corner points
        world = cal.pixel_to_world(100, 100)
        assert abs(world[0] - 0.0) < 0.1
        assert abs(world[1] - 0.0) < 0.1

        world = cal.pixel_to_world(200, 200)
        assert abs(world[0] - 4.0) < 0.1
        assert abs(world[1] - 4.0) < 0.1

    def test_world_to_pixel(self, calibration_config):
        """Test world to pixel coordinate transformation"""
        cal = HomographyCalibration("test_cam", calibration_config)

        # Test inverse transformation
        pixel = cal.world_to_pixel(0.0, 0.0)
        assert abs(pixel[0] - 100) < 1.0
        assert abs(pixel[1] - 100) < 1.0

        pixel = cal.world_to_pixel(4.0, 4.0)
        assert abs(pixel[0] - 200) < 1.0
        assert abs(pixel[1] - 200) < 1.0

    def test_round_trip_transformation(self, calibration_config):
        """Test that pixel->world->pixel gives same result"""
        cal = HomographyCalibration("test_cam", calibration_config)

        test_pixels = [(120, 130), (150, 150), (180, 190)]

        for px, py in test_pixels:
            world = cal.pixel_to_world(px, py)
            back = cal.world_to_pixel(*world)

            assert abs(back[0] - px) < 0.1, f"X mismatch: {back[0]} vs {px}"
            assert abs(back[1] - py) < 0.1, f"Y mismatch: {back[1]} vs {py}"

    def test_real_distance(self, calibration_config):
        """Test real distance calculation"""
        cal = HomographyCalibration("test_cam", calibration_config)

        # Distance across the mapped square (100 pixels = 4 meters)
        distance = cal.real_distance((100, 100), (200, 100))
        assert abs(distance - 4.0) < 0.2  # Should be ~4m

        # Diagonal (4*sqrt(2) = 5.66m)
        distance = cal.real_distance((100, 100), (200, 200))
        expected = 4.0 * math.sqrt(2)
        assert abs(distance - expected) < 0.3

    def test_real_area_rect(self, calibration_config):
        """Test rectangular area calculation"""
        cal = HomographyCalibration("test_cam", calibration_config)

        # Full calibrated area should be 4x4 = 16 m²
        area = cal.real_area_rect(100, 100, 200, 200)
        assert abs(area - 16.0) < 1.0

    def test_real_area_polygon(self, calibration_config):
        """Test polygon area calculation"""
        cal = HomographyCalibration("test_cam", calibration_config)

        # Triangle = half of square = 8 m²
        polygon = [(100, 100), (200, 100), (200, 200)]
        area = cal.real_area_polygon(polygon)
        assert abs(area - 8.0) < 0.5

    def test_real_speed(self, calibration_config):
        """Test speed calculation"""
        cal = HomographyCalibration("test_cam", calibration_config)

        # Move 4 meters (100 pixels) in 2 seconds = 2 m/s
        speed = cal.real_speed((100, 100), (200, 100), dt=2.0)
        assert abs(speed - 2.0) < 0.2

        # Zero dt should return 0
        speed = cal.real_speed((100, 100), (200, 100), dt=0.0)
        assert speed == 0.0

    def test_real_velocity(self, calibration_config):
        """Test velocity vector calculation"""
        cal = HomographyCalibration("test_cam", calibration_config)

        # Move 4m in X, 0m in Y, over 2 seconds
        vx, vy = cal.real_velocity((100, 100), (200, 100), dt=2.0)
        assert abs(vx - 2.0) < 0.2
        assert abs(vy) < 0.1

    def test_fallback_without_homography(self, config_without_homography):
        """Test fallback methods when no homography configured"""
        cal = HomographyCalibration("test_cam", config_without_homography)

        # pixel_to_world should raise
        with pytest.raises(ValueError, match="No homography"):
            cal.pixel_to_world(100, 100)

        # Fallback methods should work
        assert cal.get_visible_area() == 160.0

        # Fallback distance should use average scale
        distance = cal._fallback_distance((0, 0), (100, 0))
        assert distance > 0

    def test_pixel_to_world_batch(self, calibration_config):
        """Test batch pixel to world transformation"""
        cal = HomographyCalibration("test_cam", calibration_config)

        pixels = np.array([
            [100, 100],
            [200, 100],
            [150, 150],
            [200, 200]
        ], dtype=np.float64)

        worlds = cal.pixel_to_world_batch(pixels)

        assert worlds.shape == (4, 2)

        # Check first point
        assert abs(worlds[0, 0] - 0.0) < 0.1
        assert abs(worlds[0, 1] - 0.0) < 0.1

        # Check last point
        assert abs(worlds[3, 0] - 4.0) < 0.1
        assert abs(worlds[3, 1] - 4.0) < 0.1

    def test_empty_batch(self, calibration_config):
        """Test batch transformation with empty array"""
        cal = HomographyCalibration("test_cam", calibration_config)

        pixels = np.empty((0, 2), dtype=np.float64)
        worlds = cal.pixel_to_world_batch(pixels)

        assert worlds.shape == (0, 2)


# =============================================================================
# Test validate_homography()
# =============================================================================

class TestValidateHomography:
    """Tests for validate_homography function"""

    def test_valid_homography(self, simple_rectangle_points):
        """Test validation of a good homography"""
        H, _, _ = compute_homography(simple_rectangle_points)

        is_valid, msg = validate_homography(H, frame_size=(300, 300))

        assert is_valid is True
        assert "Valid" in msg
        assert "area:" in msg

    def test_invalid_flipped(self):
        """Test detection of flipped coordinate system"""
        # Create a homography that flips the image
        H = np.array([
            [-0.04, 0.0, 4.0],
            [0.0, 0.04, -4.0],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)

        is_valid, msg = validate_homography(H, frame_size=(200, 200))

        assert is_valid is False
        assert "flip" in msg.lower()

    def test_invalid_too_small_area(self):
        """Test detection of unreasonably small area"""
        # Create a homography that maps to tiny area
        H = np.array([
            [0.001, 0.0, 0.0],
            [0.0, 0.001, 0.0],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)

        is_valid, msg = validate_homography(
            H,
            frame_size=(1000, 1000),
            expected_area_range=(10.0, 1000.0)
        )

        assert is_valid is False
        assert "small" in msg.lower()

    def test_invalid_too_large_area(self):
        """Test detection of unreasonably large area"""
        # Create a homography that maps to huge area
        H = np.array([
            [100.0, 0.0, 0.0],
            [0.0, 100.0, 0.0],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64)

        is_valid, msg = validate_homography(
            H,
            frame_size=(100, 100),
            expected_area_range=(10.0, 1000.0)
        )

        assert is_valid is False
        assert "large" in msg.lower()

    def test_custom_area_range(self, simple_rectangle_points):
        """Test validation with custom expected area range"""
        H, _, _ = compute_homography(simple_rectangle_points)

        # The simple rectangle maps 100x100 pixel region to 4x4m.
        # For full 300x300 frame, the computed area is ~144m² (12m x 12m)
        # With a tight range that excludes 144m², validation should fail
        is_valid, msg = validate_homography(
            H,
            frame_size=(300, 300),
            expected_area_range=(200.0, 500.0)  # Excludes ~144m²
        )

        assert is_valid is False
        assert "small" in msg.lower()


# =============================================================================
# Test create_homography_config()
# =============================================================================

class TestCreateHomographyConfig:
    """Tests for create_homography_config function"""

    def test_create_valid_config(self, simple_rectangle_points):
        """Test creating a valid config dictionary"""
        config = create_homography_config(
            reference_points=simple_rectangle_points,
            frame_size=(300, 300),
            calibrated_by="test_user"
        )

        assert config['enabled'] is True
        assert 'matrix' in config
        assert len(config['matrix']) == 3
        assert len(config['matrix'][0]) == 3
        assert len(config['reference_points']) == 4
        assert config['frame_size'] == [300, 300]
        assert config['calibrated_by'] == "test_user"
        assert 'calibrated_at' in config
        assert config['reprojection_error'] >= 0

    def test_create_config_with_invalid_points(self):
        """Test that invalid points raise ValueError"""
        # Collinear points (all on a line)
        bad_points = [
            ReferencePoint(pixel=(0, 0), world=(0.0, 0.0)),
            ReferencePoint(pixel=(100, 0), world=(1.0, 0.0)),
            ReferencePoint(pixel=(200, 0), world=(2.0, 0.0)),
            ReferencePoint(pixel=(300, 0), world=(3.0, 0.0)),
        ]

        with pytest.raises(ValueError):
            create_homography_config(bad_points, (400, 400))


# =============================================================================
# Test Compatibility with PerspectiveCalibration
# =============================================================================

class TestCompatibility:
    """Tests for compatibility with existing PerspectiveCalibration interface"""

    def test_get_visible_area(self, calibration_config):
        """Test get_visible_area returns configured value"""
        cal = HomographyCalibration("test_cam", calibration_config)
        assert cal.get_visible_area() == 40.0

    def test_scale_at_y(self, calibration_config):
        """Test scale_at_y method exists and returns positive value"""
        cal = HomographyCalibration("test_cam", calibration_config)

        scale = cal.scale_at_y(y=100, frame_height=480, frame_width=640)
        assert scale > 0

        # Scale should vary with Y (perspective)
        scale_top = cal.scale_at_y(y=50, frame_height=480, frame_width=640)
        scale_bottom = cal.scale_at_y(y=400, frame_height=480, frame_width=640)

        # These should be different (perspective effect)
        assert scale_top != scale_bottom

    def test_get_lane_boundaries(self, calibration_config):
        """Test get_lane_boundaries returns valid boundaries"""
        cal = HomographyCalibration("test_cam", calibration_config)

        lanes = cal.get_lane_boundaries(frame_height=480)

        assert len(lanes) >= 1
        assert all(isinstance(lane, tuple) for lane in lanes)
        assert all(len(lane) == 2 for lane in lanes)
        assert all(lane[0] < lane[1] for lane in lanes)

    def test_to_dict(self, calibration_config):
        """Test serialization to dictionary"""
        cal = HomographyCalibration("test_cam", calibration_config)

        d = cal.to_dict()

        assert d['camera_id'] == "test_cam"
        assert 'visible_area_m2' in d
        assert 'homography' in d
        assert d['homography']['enabled'] is True
        assert 'matrix' in d['homography']

    def test_to_dict_without_homography(self, config_without_homography):
        """Test serialization without homography"""
        cal = HomographyCalibration("test_cam", config_without_homography)

        d = cal.to_dict()

        assert d['camera_id'] == "test_cam"
        assert 'homography' not in d

    def test_repr(self, calibration_config):
        """Test string representation"""
        cal = HomographyCalibration("test_cam", calibration_config)

        s = repr(cal)

        assert "test_cam" in s
        assert "HomographyCalibration" in s
        assert "homography=True" in s


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_empty_polygon_area(self, calibration_config):
        """Test area calculation with empty polygon"""
        cal = HomographyCalibration("test_cam", calibration_config)

        area = cal.real_area_polygon([])
        assert area == 0.0

        area = cal.real_area_polygon([(100, 100)])
        assert area == 0.0

        area = cal.real_area_polygon([(100, 100), (200, 200)])
        assert area == 0.0

    def test_negative_time_speed(self, calibration_config):
        """Test speed with negative time returns 0"""
        cal = HomographyCalibration("test_cam", calibration_config)

        speed = cal.real_speed((100, 100), (200, 200), dt=-1.0)
        assert speed == 0.0

    def test_malformed_config(self):
        """Test handling of malformed config"""
        bad_configs = [
            # Invalid matrix shape
            {'homography': {'enabled': True, 'matrix': [[1, 0], [0, 1]]}},
            # Missing matrix
            {'homography': {'enabled': True}},
            # Matrix is None
            {'homography': {'enabled': True, 'matrix': None}},
        ]

        for config in bad_configs:
            cal = HomographyCalibration("test_cam", config)
            # Should gracefully fall back to no homography
            assert cal.has_homography is False

    def test_default_values(self):
        """Test default values for empty config"""
        cal = HomographyCalibration("test_cam", {})

        assert cal.visible_area_m2 == 150.0
        assert cal.corridor_width_m == 4.0
        assert cal.lane_count == 1
        assert cal.has_homography is False


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests with realistic scenarios"""

    def test_fob_corridor_calibration(self):
        """Test realistic FOB corridor calibration"""
        # Realistic FOB corridor: 4m wide, 10m long
        # Camera mounted overhead at angle - top of frame is near, bottom is far
        # This matches standard image coordinates where Y increases downward
        points = [
            ReferencePoint(pixel=(200, 150), world=(0.0, 0.0)),   # top-left (near)
            ReferencePoint(pixel=(440, 150), world=(4.0, 0.0)),   # top-right (near)
            ReferencePoint(pixel=(540, 650), world=(4.0, 10.0)),  # bottom-right (far)
            ReferencePoint(pixel=(100, 650), world=(0.0, 10.0)),  # bottom-left (far)
        ]

        H, error, mask = compute_homography(points)
        is_valid, msg = validate_homography(H, (640, 720))

        assert is_valid, f"Validation failed: {msg}"
        assert error < 0.5

        # Create calibration and test
        config = {
            'visible_area_m2': 40.0,
            'homography': {
                'enabled': True,
                'matrix': H.tolist(),
                'reference_points': [
                    {'pixel': list(p.pixel), 'world': list(p.world)}
                    for p in points
                ],
                'frame_size': [640, 720],
                'reprojection_error': error
            }
        }

        cal = HomographyCalibration("fob_test", config)

        # Test some points
        near_world = cal.pixel_to_world(320, 150)  # Near center (top of frame)
        far_world = cal.pixel_to_world(320, 650)   # Far center (bottom of frame)

        # Y should increase going down frame (further in corridor)
        assert far_world[1] > near_world[1]

        # X should be approximately centered (~2m for 4m wide corridor)
        assert 1.5 < near_world[0] < 2.5

    def test_density_calculation_workflow(self, calibration_config):
        """Test typical density calculation workflow"""
        cal = HomographyCalibration("test_cam", calibration_config)

        # Simulate: 10 people detected in a zone
        people_count = 10

        # Define zone (polygon in pixels)
        zone_pixels = [(100, 100), (200, 100), (200, 200), (100, 200)]

        # Calculate real area of zone
        zone_area_m2 = cal.real_area_polygon(zone_pixels)

        # Calculate density
        density = people_count / zone_area_m2

        assert zone_area_m2 > 0
        assert density > 0

        # For 10 people in ~16m², density should be ~0.625/m²
        assert 0.5 < density < 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
