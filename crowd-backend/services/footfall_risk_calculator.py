"""
Footfall Risk Calculator

Core risk calculation engine for island platform footfall detection.
Calculates footfall per island using sliding windows and detects threshold breaches.
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from db.mongodb import MongoDB
from services.island_platform_service import island_platform_service
from services.platform_history_service import platform_history_service
from utils.logging_config import get_logger
logger = get_logger(__name__)

class FootfallRiskCalculator:
    """Calculator for island platform footfall risk assessment."""

    @classmethod
    def _build_live_contribution(
        cls,
        train_number: str,
        train_name: str,
        arrival_time: Optional[datetime],
        departure_time: Optional[datetime],
        passengers: int,
        live_status: Dict
    ) -> Tuple[Dict, set]:
        """Build a train contribution from live platform status (most accurate)."""
        raw_pf = live_status.get('platform_number')
        platform_str = raw_pf if str(raw_pf).upper().startswith("PF") else f"PF {raw_pf}"

        train_contribution = {
            "train_number": train_number,
            "train_name": train_name,
            "arrival_time": arrival_time.strftime("%H:%M:%S") if arrival_time else None,
            "departure_time": departure_time.strftime("%H:%M:%S") if departure_time else None,
            "passengers": passengers,
            "platform": platform_str,
            "stability_percent": 100.0,
            "certainty": "HIGH",
            "explanation": f"Live platform data: {platform_str}"
        }

        affected_islands = set(island_platform_service.map_platform_to_islands(platform_str))
        return train_contribution, affected_islands

    @classmethod
    async def _build_historical_contribution(
        cls,
        train_number: str,
        train_name: str,
        arrival_time: Optional[datetime],
        departure_time: Optional[datetime],
        passengers: int
    ) -> Optional[Tuple[Dict, set]]:
        """
        Build a train contribution from historical platform predictions.

        Used when no live platform is available yet, so alerts can still be
        generated ahead of time (early warning).
        """
        expected_platforms_data = await platform_history_service.get_expected_platforms_for_train(
            train_number
        )

        # Train not in history either - conservative: don't make assumptions
        if not expected_platforms_data:
            logger.debug(f"Train {train_number} has no live status and no platform history, skipping")
            return None

        stability_info = await platform_history_service.get_platform_stability(train_number)

        train_contribution = {
            "train_number": train_number,
            "train_name": train_name,
            "arrival_time": arrival_time.strftime("%H:%M:%S") if arrival_time else None,
            "departure_time": departure_time.strftime("%H:%M:%S") if departure_time else None,
            "passengers": passengers,
            "expected_platforms": [p['platform'] for p in expected_platforms_data],
            "stability_percent": stability_info['stability_percent'],
            "certainty": stability_info['certainty'],
            "explanation": cls._generate_explanation(
                train_number,
                expected_platforms_data,
                stability_info
            )
        }

        # Worst-case safety: count on ALL islands this train could appear on
        affected_islands = set()
        for platform_data in expected_platforms_data:
            affected_islands.update(platform_data['islands'])

        return train_contribution, affected_islands

    @classmethod
    async def _build_train_contribution(
        cls,
        train: Dict,
        schedule_date_dt: datetime
    ) -> Optional[Tuple[Dict, set]]:
        """Build the footfall contribution (and affected islands) for a single train, if any."""
        train_number = train.get('train_number')
        train_name = train.get('train_name', 'Unknown')
        arrival_time = train.get('arrival_time')
        departure_time = train.get('departure_time')
        passengers = train.get('total_passengers', 0)

        if not train_number or passengers <= 0:
            return None

        # Determine the relevant time (arrival or departure)
        relevant_time = arrival_time or departure_time
        if not relevant_time:
            return None

        # Prefer live train status when available (most accurate)
        live_status = await MongoDB.database.train_live_status.find_one({
            "train_number": train_number,
            "schedule_date": schedule_date_dt
        })

        if live_status and live_status.get('platform_number'):
            return cls._build_live_contribution(
                train_number, train_name, arrival_time, departure_time, passengers, live_status
            )

        return await cls._build_historical_contribution(
            train_number, train_name, arrival_time, departure_time, passengers
        )

    @classmethod
    async def calculate_island_footfall_for_window(
        cls,
        start_time: datetime,
        end_time: datetime,
        target_date: date
    ) -> Dict[str, Dict]:
        """
        Calculate footfall for each island in the time window.

        Considers both arriving and departing trains, as both bring passengers
        to the island platform.

        Args:
            start_time: Window start (datetime with time)
            end_time: Window end (datetime with time)
            target_date: Date to query train schedules

        Returns:
            dict: Footfall per island
            {
              "island_2_3": {
                "total_footfall": 1350,
                "contributing_trains": [
                  {
                    "train_number": "12735",
                    "train_name": "Express",
                    "arrival_time": "10:30:00",
                    "departure_time": None,
                    "passengers": 500,
                    "expected_platforms": ["PF 3", "PF 4"],
                    "stability_percent": 50.0,
                    "certainty": "LOW",
                    "explanation": "..."
                  }
                ]
              },
              ...
            }
        """
        # Initialize footfall tracking for all islands
        island_footfall = {
            island_id: {"total_footfall": 0, "contributing_trains": []}
            for island_id in island_platform_service.get_all_island_ids()
        }

        # Query trains arriving OR departing in this window
        # Convert date to datetime for MongoDB compatibility
        schedule_date_dt = datetime.combine(target_date, datetime.min.time())

        # Find trains where arrival_time OR departure_time is in the window
        trains = await MongoDB.database.train_schedules.find({
            "schedule_date": schedule_date_dt,
            "$or": [
                {
                    "arrival_time": {
                        "$gte": start_time,
                        "$lt": end_time
                    }
                },
                {
                    "departure_time": {
                        "$gte": start_time,
                        "$lt": end_time
                    }
                }
            ]
        }).to_list(length=None)

        logger.debug(f"Found {len(trains)} trains in window {start_time} - {end_time}")

        # Process each train
        for train in trains:
            await cls._accumulate_train_footfall(train, schedule_date_dt, island_footfall)

        return island_footfall

    @classmethod
    async def _accumulate_train_footfall(
        cls,
        train: Dict,
        schedule_date_dt: datetime,
        island_footfall: Dict[str, Dict]
    ) -> None:
        """Look up a train's live platform and add its passengers to affected islands."""
        train_number = train.get('train_number')
        train_name = train.get('train_name', 'Unknown')
        arrival_time = train.get('arrival_time')
        departure_time = train.get('departure_time')
        passengers = train.get('total_passengers', 0)

        if not train_number or passengers <= 0:
            return

        # Determine the relevant time (arrival or departure)
        relevant_time = arrival_time or departure_time
        if not relevant_time:
            return

        # Query live train status instead of estimated history
        live_status = await MongoDB.database.train_live_status.find_one({
            "train_number": train_number,
            "schedule_date": schedule_date_dt
        })

        # If no live status or no platform assigned yet, skip it
        if not live_status or not live_status.get('platform_number'):
            logger.debug(f"Train {train_number} has no live platform assigned, skipping")
            return

        raw_pf = live_status.get('platform_number')
        platform_str = raw_pf if str(raw_pf).upper().startswith("PF") else f"PF {raw_pf}"

        # Build train contribution record
        train_contribution = {
            "train_number": train_number,
            "train_name": train_name,
            "arrival_time": arrival_time.strftime("%H:%M:%S") if arrival_time else None,
            "departure_time": departure_time.strftime("%H:%M:%S") if departure_time else None,
            "passengers": passengers,
            "platform": platform_str,
            "stability_percent": 100.0,
            "certainty": "HIGH",
            "explanation": f"Live platform data: {platform_str}"
        }

        # Map to affected islands
        affected_islands = set(island_platform_service.map_platform_to_islands(platform_str))

        for island_id in affected_islands:
            island_footfall[island_id]['total_footfall'] += passengers
            island_footfall[island_id]['contributing_trains'].append(
                train_contribution.copy()
            )

    @classmethod
    def _generate_explanation(
        cls,
        train_number: str,
        expected_platforms_data: List[Dict],
        stability_info: Dict
    ) -> str:
        """
        Generate human-readable explanation for train platform assignment.

        Args:
            train_number: Train identifier
            expected_platforms_data: Platform data from history
            stability_info: Stability information

        Returns:
            str: Explanation text
        """
        if not expected_platforms_data:
            return "No historical platform data available"

        stability = stability_info['stability_percent']
        dominant = stability_info['dominant_platform']

        if len(expected_platforms_data) == 1:
            # Single platform
            return (f"Train appears {stability:.0f}% on {dominant} historically")
        else:
            # Multiple platforms (unstable)
            platforms_str = ", ".join([
                f"{p['platform']} ({p['probability']*100:.0f}%)"
                for p in expected_platforms_data
            ])
            return (
                f"Train has unstable platform history: {platforms_str}. "
                f"Counted on ALL possible islands for safety."
            )

    @classmethod
    async def detect_risks_for_time_range(
        cls,
        start_datetime: datetime,
        end_datetime: datetime,
        step_minutes: int = 5
    ) -> List[Dict]:
        """
        Slide 45-min window across time range with configurable step size.

        Args:
            start_datetime: Range start
            end_datetime: Range end
            step_minutes: Window step size (default: 5)

        Returns:
            list: Risk windows
            [
              {
                "window_start": datetime,
                "window_end": datetime,
                "island_id": "island_2_3",
                "total_footfall": 1350,
                "threshold": 1200,
                "exceeds_threshold": True,
                "exceeds_by": 150,
                "exceeds_by_percent": 12.5,
                "risk_level": "MEDIUM",
                "certainty_breakdown": {
                  "high_certainty_trains": 2,
                  "medium_certainty_trains": 1,
                  "low_certainty_trains": 1,
                  "total_trains": 4
                },
                "contributing_trains": [...]
              }
            ]
        """
        risks = []
        threshold = island_platform_service.get_island_threshold()
        window_minutes = island_platform_service.get_window_duration_minutes()

        # Slide window across time range
        current_start = start_datetime
        step_delta = timedelta(minutes=step_minutes)
        window_delta = timedelta(minutes=window_minutes)

        while current_start < end_datetime:
            current_end = current_start + window_delta

            # Get date for querying train schedules
            target_date = current_start.date()

            # Calculate footfall for this window
            island_footfall = await cls.calculate_island_footfall_for_window(
                current_start,
                current_end,
                target_date
            )

            # Check each island for threshold breach
            for island_id, data in island_footfall.items():
                footfall = data['total_footfall']

                if footfall >= threshold:
                    # Calculate certainty breakdown
                    certainty_breakdown = cls._calculate_certainty_breakdown(
                        data['contributing_trains']
                    )

                    exceeds_by = footfall - threshold
                    exceeds_by_percent = (exceeds_by / threshold) * 100

                    risk_level = island_platform_service.calculate_risk_level(
                        footfall,
                        threshold
                    )

                    risks.append({
                        "window_start": current_start,
                        "window_end": current_end,
                        "island_id": island_id,
                        "island_name": island_platform_service.get_island_name(island_id),
                        "total_footfall": footfall,
                        "threshold": threshold,
                        "exceeds_threshold": True,
                        "exceeds_by": exceeds_by,
                        "exceeds_by_percent": round(exceeds_by_percent, 1),
                        "risk_level": risk_level,
                        "certainty_breakdown": certainty_breakdown,
                        "contributing_trains": data['contributing_trains']
                    })

            # Move to next window
            current_start += step_delta

        logger.info(f"Detected {len(risks)} risk windows between {start_datetime} and {end_datetime}")
        return risks

    @classmethod
    def _calculate_certainty_breakdown(cls, trains: List[Dict]) -> Dict:
        """
        Calculate breakdown of train certainties.

        Args:
            trains: List of contributing trains

        Returns:
            dict: Certainty counts
                {
                    "high_certainty_trains": int,
                    "medium_certainty_trains": int,
                    "low_certainty_trains": int,
                    "total_trains": int
                }
        """
        high = sum(1 for t in trains if t.get('certainty') == 'HIGH')
        medium = sum(1 for t in trains if t.get('certainty') == 'MEDIUM')
        low = sum(1 for t in trains if t.get('certainty') == 'LOW')

        return {
            "high_certainty_trains": high,
            "medium_certainty_trains": medium,
            "low_certainty_trains": low,
            "total_trains": len(trains)
        }

    @classmethod
    async def get_day_time_range(cls, target_date: date) -> Optional[Dict]:
        """
        Get time range for a specific date based on train schedules.

        Considers both arrival and departure times to find earliest and latest
        train activity. Extends range by planning_advance_minutes before first train.

        Args:
            target_date: Date to analyze

        Returns:
            dict: Time range or None if no trains
                {
                    "start_datetime": datetime,
                    "end_datetime": datetime,
                    "first_train_time": datetime,
                    "last_train_time": datetime
                }
        """
        # Get first and last train times for this date
        # Convert date to datetime for MongoDB compatibility
        schedule_date_dt = datetime.combine(target_date, datetime.min.time())

        # Get all trains with arrival or departure times
        all_trains = await MongoDB.database.train_schedules.find({
            "schedule_date": schedule_date_dt,
            "$or": [
                {"arrival_time": {"$ne": None}},
                {"departure_time": {"$ne": None}}
            ]
        }).to_list(length=None)

        if not all_trains:
            logger.warning(f"No trains found for date: {target_date}")
            return None

        # Find earliest and latest times (considering both arrival and departure)
        times = []
        for train in all_trains:
            if train.get('arrival_time'):
                times.append(train['arrival_time'])
            if train.get('departure_time'):
                times.append(train['departure_time'])

        if not times:
            logger.warning(f"No valid times found for date: {target_date}")
            return None

        first_time = min(times)
        last_time = max(times)

        # Extend start by planning advance minutes
        advance_minutes = island_platform_service.get_planning_advance_minutes()
        start_datetime = first_time - timedelta(minutes=advance_minutes)

        return {
            "start_datetime": start_datetime,
            "end_datetime": last_time,
            "first_train_time": first_time,
            "last_train_time": last_time
        }


# Singleton instance
footfall_risk_calculator = FootfallRiskCalculator()
