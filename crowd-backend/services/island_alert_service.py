"""
Island Alert Service

Generates and persists island platform footfall risk alerts.
Manages alert lifecycle (triggered → acknowledged → resolved).
"""

import uuid
from datetime import UTC, datetime, date, timedelta
from typing import Dict, Optional
from db.mongodb import MongoDB
from services.footfall_risk_calculator import footfall_risk_calculator
from services.island_platform_service import island_platform_service
from utils.logging_config import get_logger
logger = get_logger(__name__)

# Filter for the list/live queries: only requires every contributing train
# to have an assigned platform; arrival/departure times may still be pending.
PLATFORM_ASSIGNED_FILTER = {
    "$not": {
        "$elemMatch": {"platform": {"$exists": False}}
    }
}

# Filter for WhatsApp: every contributing train must have either a live
# `platform` or a non-empty `expected_platforms` list (historical prediction).
PLATFORM_OR_EXPECTED_FILTER = {
    "$not": {
        "$elemMatch": {
            "platform": {"$in": [None, ""]},
            "expected_platforms.0": {"$exists": False}
        }
    }
}


class IslandAlertService:
    """Service for managing island platform footfall alerts."""

    COLLECTION_NAME = "island_alerts"

    @classmethod
    async def generate_alerts_for_day(cls, target_date: date) -> Dict:
        """
        Generate all alerts for a given day.

        Analyzes from 90 minutes before first train to last train arrival.

        Args:
            target_date: Date to generate alerts for

        Returns:
            dict: Generation results
                {
                    "status": "success|error",
                    "date": str,
                    "alert_ids": list,
                    "alerts_created": int,
                    "time_range": dict,
                    "errors": list
                }
        """
        try:
            logger.info(f"Generating island alerts for date: {target_date}")

            # Get time range for this date
            time_range = await footfall_risk_calculator.get_day_time_range(target_date)

            if not time_range:
                return {
                    "status": "error",
                    "date": str(target_date),
                    "alert_ids": [],
                    "alerts_created": 0,
                    "message": "No trains found for this date",
                    "errors": []
                }

            # Detect risk windows
            risk_windows = await footfall_risk_calculator.detect_risks_for_time_range(
                time_range['start_datetime'],
                time_range['end_datetime']
            )

            logger.info(f"Found {len(risk_windows)} risk windows for {target_date}")

            # Create alerts
            alert_ids = []
            errors = []

            for risk_window in risk_windows:
                try:
                    # Check for exact duplicate (same island + same window_start)
                    if await cls.check_duplicate_alert(
                        risk_window['island_id'],
                        risk_window['window_start']
                    ):
                        logger.debug(
                            f"Skipping exact duplicate alert for {risk_window['island_id']} "
                            f"at {risk_window['window_start']}"
                        )
                        continue

                    # Check for overlapping alerts and merge if needed
                    merged_alert_id = await cls.check_and_merge_overlapping_alert(
                        risk_window['island_id'],
                        risk_window['window_start'],
                        risk_window
                    )

                    if merged_alert_id:
                        # Alert was merged/updated, don't create new one
                        alert_ids.append(merged_alert_id)
                        continue

                    # No overlap found - create new alert
                    alert_doc = cls._build_alert_document(risk_window)

                    # Insert into database
                    result = await MongoDB.database[cls.COLLECTION_NAME].insert_one(alert_doc)
                    alert_ids.append(alert_doc['alert_id'])

                    logger.debug(f"Created new alert: {alert_doc['alert_id']}")

                except Exception as e:
                    error_msg = f"Failed to create alert for {risk_window['island_id']}: {e}"
                    errors.append(error_msg)
                    logger.exception(error_msg)

            return {
                "status": "success",
                "date": str(target_date),
                "alert_ids": alert_ids,
                "alerts_created": len(alert_ids),
                "time_range": {
                    "start": time_range['start_datetime'].isoformat(),
                    "end": time_range['end_datetime'].isoformat(),
                    "first_train": time_range['first_train_time'].isoformat(),
                    "last_train": time_range['last_train_time'].isoformat()
                },
                "errors": errors
            }

        except Exception as e:
            logger.exception(f"Error generating alerts for {target_date}")
            return {
                "status": "error",
                "date": str(target_date),
                "alert_ids": [],
                "alerts_created": 0,
                "error": str(e),
                "errors": [str(e)]
            }

    @classmethod
    def _build_alert_document(cls, risk_window: Dict) -> Dict:
        """
        Build alert document from risk window data.

        Args:
            risk_window: Risk window data from calculator

        Returns:
            dict: Complete alert document
        """
        alert_id = str(uuid.uuid4())
        advisory_message = cls._generate_advisory_message(risk_window)

        now = datetime.now(UTC) + timedelta(hours=5, minutes=30)  # IST
        return {
            "alert_id": alert_id,
            "alert_type": "ISLAND_FOOTFALL_RISK",
            "island_id": risk_window['island_id'],
            "island_name": risk_window['island_name'],
            "window_start": risk_window['window_start'],
            "window_end": risk_window['window_end'],
            "total_footfall": risk_window['total_footfall'],
            "threshold": risk_window['threshold'],
            "exceeds_by": risk_window['exceeds_by'],
            "exceeds_by_percent": risk_window['exceeds_by_percent'],
            "risk_level": risk_window['risk_level'],
            "certainty_breakdown": risk_window['certainty_breakdown'],
            "contributing_trains": risk_window['contributing_trains'],
            "status": "triggered",
            "created_at": now,
            "updated_at": now,
            "acknowledged_at": None,
            "resolved_at": None,
            "advisory_message": advisory_message
        }

    @classmethod
    def _generate_advisory_message(cls, risk_window: Dict) -> str:
        """
        Generate human-readable advisory message.

        Args:
            risk_window: Risk window data

        Returns:
            str: Advisory message
        """
        island_name = risk_window['island_name']
        window_start = risk_window['window_start'].strftime("%H:%M")
        window_end = risk_window['window_end'].strftime("%H:%M")
        footfall = risk_window['total_footfall']
        exceeds_by_percent = risk_window['exceeds_by_percent']

        certainty = risk_window['certainty_breakdown']
        total_trains = certainty['total_trains']
        high_count = certainty['high_certainty_trains']
        medium_count = certainty['medium_certainty_trains']
        low_count = certainty['low_certainty_trains']

        # Build certainty phrase
        certainty_parts = []
        if low_count > 0:
            certainty_parts.append(f"{low_count} low certainty")
        if medium_count > 0:
            certainty_parts.append(f"{medium_count} medium certainty")
        if high_count > 0:
            certainty_parts.append(f"{high_count} high certainty")

        certainty_phrase = ", ".join(certainty_parts)

        message = (
            f"Possible congestion risk on Island Platform {island_name} "
            f"between {window_start}-{window_end} due to overlapping arrivals. "
            f"{total_trains} trains expected ({certainty_phrase}). "
            f"Total estimated footfall: {footfall} passengers "
            f"(exceeds threshold by {exceeds_by_percent:.1f}%)."
        )

        return message

    @classmethod
    async def check_duplicate_alert(
        cls,
        island_id: str,
        window_start: datetime
    ) -> bool:
        """
        Check if alert already exists for this island/window.

        Uses exact window_start match to prevent duplicates.
        Overlapping window merging is handled in check_and_merge_overlapping_alert().

        Args:
            island_id: Island identifier
            window_start: Window start time

        Returns:
            bool: True if duplicate exists, False otherwise
        """
        existing = await MongoDB.database[cls.COLLECTION_NAME].find_one({
            "island_id": island_id,
            "window_start": window_start
        })

        return existing is not None

    @classmethod
    async def check_and_merge_overlapping_alert(
        cls,
        island_id: str,
        window_start: datetime,
        new_risk_window: Dict
    ) -> Optional[str]:
        """
        Check for overlapping alerts and merge if found.

        If an overlapping alert exists and the new risk is higher, update it.
        This prevents duplicate alerts for the same congestion event.

        Args:
            island_id: Island identifier
            window_start: New window start time
            new_risk_window: Complete risk window data

        Returns:
            str: Alert ID if merged/updated, None if no overlap found
        """
        # Look for active alerts within ±30 minutes
        overlap_margin = timedelta(minutes=30)

        existing = await MongoDB.database[cls.COLLECTION_NAME].find_one({
            "island_id": island_id,
            "window_start": {
                "$gte": window_start - overlap_margin,
                "$lte": window_start + overlap_margin
            },
            "status": {"$in": ["triggered", "acknowledged"]}  # Not resolved
        })

        if not existing:
            return None

        # Overlapping alert found - decide whether to update
        existing_footfall = existing.get('total_footfall', 0)
        new_footfall = new_risk_window['total_footfall']

        # If new footfall is higher, update the existing alert
        if new_footfall > existing_footfall:
            logger.info(
                f"Merging alert for {island_id}: existing footfall {existing_footfall} "
                f"→ new peak {new_footfall} at {window_start}"
            )

            # Build updated alert data
            updated_data = {
                "window_start": new_risk_window['window_start'],
                "window_end": new_risk_window['window_end'],
                "total_footfall": new_footfall,
                "exceeds_by": new_risk_window['exceeds_by'],
                "exceeds_by_percent": new_risk_window['exceeds_by_percent'],
                "risk_level": new_risk_window['risk_level'],
                "certainty_breakdown": new_risk_window['certainty_breakdown'],
                "contributing_trains": new_risk_window['contributing_trains'],
                "advisory_message": cls._generate_advisory_message(new_risk_window),
                "updated_at": datetime.now(UTC) + timedelta(hours=5, minutes=30)  # IST
            }

            # Update existing alert with new peak data
            await MongoDB.database[cls.COLLECTION_NAME].update_one(
                {"alert_id": existing['alert_id']},
                {"$set": updated_data}
            )

            logger.info(f"Updated alert {existing['alert_id']} with higher peak")
            return existing['alert_id']
        else:
            # Existing alert is equal or higher - skip creating new alert
            logger.debug(
                f"Skipping overlapping alert for {island_id}: existing peak "
                f"{existing_footfall} >= new {new_footfall}"
            )
            return existing['alert_id']

    @classmethod
    async def acknowledge_alert(cls, alert_id: str) -> Dict:
        """
        Mark alert as acknowledged.

        Args:
            alert_id: Alert UUID

        Returns:
            dict: Update result
                {"status": "success|error", "alert_id": str, "acknowledged_at": datetime}
        """
        try:
            acknowledged_at = datetime.now(UTC) + timedelta(hours=5, minutes=30)  # IST

            result = await MongoDB.database[cls.COLLECTION_NAME].update_one(
                {"alert_id": alert_id},
                {
                    "$set": {
                        "status": "acknowledged",
                        "acknowledged_at": acknowledged_at
                    }
                }
            )

            if result.matched_count == 0:
                return {
                    "status": "error",
                    "message": "Alert not found",
                    "alert_id": alert_id
                }

            return {
                "status": "success",
                "alert_id": alert_id,
                "acknowledged_at": acknowledged_at.isoformat()
            }

        except Exception as e:
            logger.exception(f"Error acknowledging alert {alert_id}")
            return {
                "status": "error",
                "message": str(e),
                "alert_id": alert_id
            }

    @classmethod
    async def resolve_alert(cls, alert_id: str) -> Dict:
        """
        Mark alert as resolved.

        Args:
            alert_id: Alert UUID

        Returns:
            dict: Update result
                {"status": "success|error", "alert_id": str, "resolved_at": datetime}
        """
        try:
            resolved_at = datetime.now(UTC) + timedelta(hours=5, minutes=30)  # IST

            result = await MongoDB.database[cls.COLLECTION_NAME].update_one(
                {"alert_id": alert_id},
                {
                    "$set": {
                        "status": "resolved",
                        "resolved_at": resolved_at
                    }
                }
            )

            if result.matched_count == 0:
                return {
                    "status": "error",
                    "message": "Alert not found",
                    "alert_id": alert_id
                }

            return {
                "status": "success",
                "alert_id": alert_id,
                "resolved_at": resolved_at.isoformat()
            }

        except Exception as e:
            logger.exception(f"Error resolving alert {alert_id}")
            return {
                "status": "error",
                "message": str(e),
                "alert_id": alert_id
            }

    @classmethod
    async def get_alert_by_id(cls, alert_id: str) -> Optional[Dict]:
        """
        Get alert by ID.

        Args:
            alert_id: Alert UUID

        Returns:
            dict: Alert document or None
        """
        return await MongoDB.database[cls.COLLECTION_NAME].find_one({"alert_id": alert_id})

    @classmethod
    async def list_alerts(
        cls,
        island_id: Optional[str] = None,
        status: Optional[str] = None,
        risk_level: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict:
        """
        List alerts with filters.

        Args:
            island_id: Filter by island
            status: Filter by status (triggered/acknowledged/resolved)
            risk_level: Filter by risk level (MEDIUM/HIGH/CRITICAL)
            start_date: Filter by window_start >= date
            end_date: Filter by window_start <= date
            limit: Max results (default 50, max 200)
            offset: Pagination offset

        Returns:
            dict: Results
                {
                    "status": "success",
                    "count": int,
                    "total": int,
                    "alerts": list
                }
        """
        # Build query
        query = {}

        # Only show alerts where every contributing train has an assigned
        # platform. Arrival/departure times may still be pending.
        query["contributing_trains"] = PLATFORM_ASSIGNED_FILTER

        if island_id:
            query["island_id"] = island_id

        if status:
            query["status"] = status

        if risk_level:
            query["risk_level"] = risk_level

        if start_date or end_date:
            query["window_start"] = {}
            if start_date:
                query["window_start"]["$gte"] = datetime.combine(
                    start_date, datetime.min.time()
                )
            if end_date:
                query["window_start"]["$lte"] = datetime.combine(
                    end_date, datetime.max.time()
                )

        # Enforce limit
        limit = min(limit, 200)

        # Get total count
        total = await MongoDB.database[cls.COLLECTION_NAME].count_documents(query)

        # Get paginated results
        alerts = await MongoDB.database[cls.COLLECTION_NAME].find(query).sort(
            "window_start", -1
        ).skip(offset).limit(limit).to_list(length=limit)

        return {
            "status": "success",
            "count": len(alerts),
            "total": total,
            "limit": limit,
            "offset": offset,
            "alerts": alerts
        }

    @classmethod
    async def get_latest_alerts(cls, limit: int = 10) -> list:
        """
        Get the most recently created alerts (no filters applied).

        Args:
            limit: Number of alerts to return (default 10)

        Returns:
            list: Alert documents, newest first by created_at
        """
        return await MongoDB.database[cls.COLLECTION_NAME].find({}).sort(
            "created_at", -1
        ).limit(limit).to_list(length=limit)

    @classmethod
    async def get_daily_summary(cls, target_date: date) -> Dict:
        """
        Get daily summary statistics.

        Args:
            target_date: Date to summarize

        Returns:
            dict: Summary statistics
        """
        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = datetime.combine(target_date, datetime.max.time())

        # Total alerts for the day
        total_alerts = await MongoDB.database[cls.COLLECTION_NAME].count_documents({
            "window_start": {"$gte": start_dt, "$lte": end_dt}
        })

        # Group by island
        by_island = {}
        for island_id in island_platform_service.get_all_island_ids():
            count = await MongoDB.database[cls.COLLECTION_NAME].count_documents({
                "island_id": island_id,
                "window_start": {"$gte": start_dt, "$lte": end_dt}
            })
            by_island[island_id] = count

        # Group by risk level
        by_risk_level = {}
        for risk_level in ["MEDIUM", "HIGH", "CRITICAL"]:
            count = await MongoDB.database[cls.COLLECTION_NAME].count_documents({
                "risk_level": risk_level,
                "window_start": {"$gte": start_dt, "$lte": end_dt}
            })
            by_risk_level[risk_level] = count

        # Group by status
        by_status = {}
        for status in ["triggered", "acknowledged", "resolved"]:
            count = await MongoDB.database[cls.COLLECTION_NAME].count_documents({
                "status": status,
                "window_start": {"$gte": start_dt, "$lte": end_dt}
            })
            by_status[status] = count

        # Peak hours (alerts per hour)
        pipeline = [
            {
                "$match": {
                    "window_start": {"$gte": start_dt, "$lte": end_dt}
                }
            },
            {
                "$group": {
                    "_id": {"$hour": "$window_start"},
                    "alert_count": {"$sum": 1}
                }
            },
            {
                "$sort": {"alert_count": -1}
            },
            {
                "$limit": 10
            }
        ]

        peak_hours_cursor = MongoDB.database[cls.COLLECTION_NAME].aggregate(pipeline)
        peak_hours = []
        async for doc in peak_hours_cursor:
            peak_hours.append({
                "hour": doc["_id"],
                "alert_count": doc["alert_count"]
            })

        return {
            "status": "success",
            "date": str(target_date),
            "total_alerts": total_alerts,
            "by_island": by_island,
            "by_risk_level": by_risk_level,
            "by_status": by_status,
            "peak_hours": peak_hours
        }

    @classmethod
    async def get_live_alerts(cls, hours_ahead: int = 2) -> Dict:
        """
        Get active alerts for current time + next N hours.

        Includes:
        - Currently active alerts (window_end >= now)
        - Upcoming alerts (window_start <= now + hours_ahead)

        Args:
            hours_ahead: Hours to look ahead (default: 2)

        Returns:
            dict: Live alerts
        """
        now = datetime.now(UTC) + timedelta(hours=5, minutes=30)  # IST
        future = now + timedelta(hours=hours_ahead)

        # Get alerts that are:
        # 1. Currently active (window_end >= now) OR
        # 2. Upcoming (window_start <= future)
        # AND window_start >= now - 1 hour (don't show old finished alerts)
        lookback = now - timedelta(hours=1)

        alerts = await MongoDB.database[cls.COLLECTION_NAME].find({
            "window_start": {"$gte": lookback, "$lte": future},  # Within time range
            "window_end": {"$gte": now},  # Alert hasn't ended yet
            "status": {"$in": ["triggered", "acknowledged"]},
            # Only trains with an assigned platform; arrival/departure
            # times may still be pending
            "contributing_trains": PLATFORM_ASSIGNED_FILTER
        }).sort("window_start", 1).to_list(length=50)

        return {
            "status": "success",
            "current_time": now.isoformat(),
            "window_end": future.isoformat(),
            "count": len(alerts),
            "alerts": alerts
        }


    @classmethod
    async def get_pending_whatsapp_alerts(cls, now_ist: datetime, lookahead_minutes: int) -> list:
        """
        Get active alerts that haven't been sent via WhatsApp yet.

        Picks alerts whose window hasn't ended and starts within the next
        `lookahead_minutes`, oldest window first.

        Args:
            now_ist: Current IST time (naive, same wall-clock basis as window_start)
            lookahead_minutes: How far ahead of window_start to notify

        Returns:
            list: Alert documents
        """
        return await MongoDB.database[cls.COLLECTION_NAME].find({
            "window_start": {"$lte": now_ist + timedelta(minutes=lookahead_minutes)},
            "window_end": {"$gte": now_ist},
            "status": "triggered",
            "whatsapp_sent": {"$ne": True},
            # Every train needs a live platform or expected platforms;
            # arrival/departure times may still be pending
            "contributing_trains": PLATFORM_OR_EXPECTED_FILTER
        }).sort("window_start", 1).to_list(length=50)

    @classmethod
    async def claim_whatsapp_send(cls, alert_id: str) -> bool:
        """
        Atomically flag an alert as sent via WhatsApp before dispatching it.

        Returns True only for the caller that flipped the flag, so overlapping
        cycles or multiple worker processes can never send the same alert twice.
        """
        result = await MongoDB.database[cls.COLLECTION_NAME].update_one(
            {"alert_id": alert_id, "whatsapp_sent": {"$ne": True}},
            {"$set": {
                "whatsapp_sent": True,
                "whatsapp_sent_at": datetime.now(UTC) + timedelta(hours=5, minutes=30)  # IST
            }}
        )
        return result.modified_count == 1


# Singleton instance
island_alert_service = IslandAlertService()
