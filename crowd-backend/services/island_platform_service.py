"""
Island Platform Configuration Service

Provides centralized configuration and utility functions for island platform
management at Secunderabad Railway Station.

Key Principle: Safety signals are never suppressed due to uncertainty.
"""

from typing import Dict, List, Optional
from config.config import get_settings

class IslandPlatformService:
    """Service for managing island platform configuration and utilities."""

    # Secunderabad Station Island Platform Configuration
    # Islands are physical platforms where two platform numbers share the same space
    ISLAND_CONFIG = {
        "island_2_3": {
            "platforms": ["PF 2", "PF 3"],
            "name": "Platforms 2 & 3",
            "display_order": 1
        },
        "island_4_5": {
            "platforms": ["PF 4", "PF 5"],
            "name": "Platforms 4 & 5",
            "display_order": 2
        },
        "island_6_7": {
            "platforms": ["PF 6", "PF 7"],
            "name": "Platforms 6 & 7",
            "display_order": 3
        },
        "island_8_9": {
            "platforms": ["PF 8", "PF 9"],
            "name": "Platforms 8 & 9",
            "display_order": 4
        }
    }

    # Side platforms (not islands)
    SIDE_PLATFORMS = ["PF 1", "PF 10"]

    @classmethod
    def get_island_config(cls) -> Dict[str, Dict]:
        """
        Get island platform configuration.

        Returns:
            dict: Island configuration mapping
            {
                "island_2_3": {
                    "platforms": ["PF 2", "PF 3"],
                    "name": "Platforms 2 & 3",
                    "display_order": 1
                },
                ...
            }
        """
        return cls.ISLAND_CONFIG.copy()

    @classmethod
    def get_all_island_ids(cls) -> List[str]:
        """
        Get list of all island IDs.

        Returns:
            list: ["island_2_3", "island_4_5", "island_6_7", "island_8_9"]
        """
        return list(cls.ISLAND_CONFIG.keys())

    @classmethod
    def get_island_name(cls, island_id: str) -> Optional[str]:
        """
        Get human-readable island name.

        Args:
            island_id: Island identifier (e.g., "island_2_3")

        Returns:
            str: Island name (e.g., "Platforms 2 & 3") or None if not found
        """
        island = cls.ISLAND_CONFIG.get(island_id)
        return island["name"] if island else None

    @classmethod
    def map_platform_to_islands(cls, platform: str) -> List[str]:
        """
        Map a platform to its island(s).

        Args:
            platform: Platform identifier (e.g., "PF 3", "PF 10")

        Returns:
            list: List of island IDs this platform belongs to
                  Returns [] for side platforms

        Examples:
            >>> map_platform_to_islands("PF 3")
            ["island_2_3"]
            >>> map_platform_to_islands("PF 10")
            []
        """
        # Check if this is a side platform
        if platform in cls.SIDE_PLATFORMS:
            return []

        # Find which island(s) contain this platform
        islands = []
        for island_id, config in cls.ISLAND_CONFIG.items():
            if platform in config["platforms"]:
                islands.append(island_id)

        return islands

    @classmethod
    def get_island_threshold(cls) -> int:
        """
        Get footfall threshold for island platforms.

        Returns:
            int: Passenger count threshold (default: 1200)
        """
        return get_settings().island_footfall_threshold

    @classmethod
    def get_certainty_label(cls, stability_percent: float) -> str:
        """
        Calculate certainty label based on platform stability percentage.

        Args:
            stability_percent: Percentage (0-100) of how often train appears
                              on dominant platform

        Returns:
            str: "HIGH" (≥80%), "MEDIUM" (50-79%), "LOW" (<50%)

        Examples:
            >>> get_certainty_label(85.0)
            "HIGH"
            >>> get_certainty_label(65.0)
            "MEDIUM"
            >>> get_certainty_label(45.0)
            "LOW"
        """
        if stability_percent >= get_settings().platform_certainty_high_threshold:
            return "HIGH"
        elif stability_percent >= get_settings().platform_certainty_medium_threshold:
            return "MEDIUM"
        else:
            return "LOW"

    @classmethod
    def calculate_risk_level(cls, footfall: int, threshold: int) -> str:
        """
        Calculate risk level based on how much threshold is exceeded.

        Args:
            footfall: Total passenger count
            threshold: Threshold value

        Returns:
            str: "MEDIUM", "HIGH", or "CRITICAL"

        Risk Levels:
            - MEDIUM: At threshold to 25% over (1200-1500)
            - HIGH: 25-50% over threshold (1500-1800)
            - CRITICAL: >50% over threshold (>1800)
        """
        if footfall < threshold:
            return "MEDIUM"  # Shouldn't happen for alerts, but safe default

        ratio = footfall / threshold

        if ratio >= get_settings().island_risk_critical_threshold:
            return "CRITICAL"
        elif ratio >= get_settings().island_risk_high_threshold:
            return "HIGH"
        else:
            return "MEDIUM"

    @classmethod
    def is_side_platform(cls, platform: str) -> bool:
        """
        Check if a platform is a side platform (not an island).

        Args:
            platform: Platform identifier (e.g., "PF 1")

        Returns:
            bool: True if side platform, False otherwise
        """
        return platform in cls.SIDE_PLATFORMS

    @classmethod
    def get_window_duration_minutes(cls) -> int:
        """
        Get sliding window duration in minutes.

        Returns:
            int: Window duration (default: 45 minutes)
        """
        return get_settings().island_alert_window_minutes

    @classmethod
    def get_step_minutes(cls) -> int:
        """
        Get sliding window step size in minutes.

        Returns:
            int: Step size (default: 5 minutes)
        """
        return get_settings().island_alert_step_minutes

    @classmethod
    def get_planning_advance_minutes(cls) -> int:
        """
        Get advance planning time in minutes.

        Returns:
            int: Minutes before first train to start alerts (default: 90)
        """
        return get_settings().island_planning_advance_minutes

    @classmethod
    def validate_configuration(cls) -> Dict[str, bool]:
        """
        Validate island platform configuration.

        Returns:
            dict: Validation results
        """
        validation = {
            "has_islands": len(cls.ISLAND_CONFIG) > 0,
            "threshold_positive": cls.get_island_threshold() > 0,
            "window_duration_positive": cls.get_window_duration_minutes() > 0,
            "step_positive": cls.get_step_minutes() > 0,
            "valid": True
        }

        # Check that all values are valid
        validation["valid"] = all([
            validation["has_islands"],
            validation["threshold_positive"],
            validation["window_duration_positive"],
            validation["step_positive"]
        ])

        return validation


# Singleton instance
island_platform_service = IslandPlatformService()
