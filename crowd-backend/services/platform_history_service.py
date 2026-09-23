"""
Platform History Service

Loads and manages historical platform occupation data from CSV.
Provides query functions to determine expected platforms for trains.
"""

import csv
import os
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple
import aiofiles
from db.mongodb import MongoDB
from services.island_platform_service import island_platform_service
from utils.logging_config import get_logger

logger = get_logger(__name__)

REQUIRED_CSV_COLUMNS = [
    'train_number', 'PF 1', 'PF 2', 'PF 3', 'PF 4', 'PF 5',
    'PF 6', 'PF 7', 'PF 8', 'PF 9', 'total_occurrences',
    'dominant_platform', 'dominant_count', 'stability_percent'
]


class PlatformHistoryService:
    """Service for managing platform history data."""

    COLLECTION_NAME = "platform_history"

    @classmethod
    def _parse_platform_occurrences(cls, row: Dict[str, str], row_num: int, errors: List[str]) -> Dict[str, int]:
        platform_occurrences = {}
        for pf_num in range(1, 10):  # PF 1 through PF 9
            pf_key = f"PF {pf_num}"
            try:
                platform_occurrences[pf_key] = int(row.get(pf_key, 0))
            except ValueError:
                platform_occurrences[pf_key] = 0
                errors.append(f"Row {row_num}: Invalid count for {pf_key}")
        return platform_occurrences

    @classmethod
    def _parse_csv_row(cls, row: Dict[str, str], row_num: int, errors: List[str]) -> Optional[Dict[str, Any]]:
        """Parse a single CSV row into a document, or None if the row should be skipped."""
        train_number = row['train_number'].strip()
        if not train_number:
            errors.append(f"Row {row_num}: Empty train number")
            return None

        platform_occurrences = cls._parse_platform_occurrences(row, row_num, errors)

        try:
            total_occurrences = int(row['total_occurrences'])
        except ValueError:
            total_occurrences = sum(platform_occurrences.values())
            errors.append(f"Row {row_num}: Invalid total_occurrences, using sum")

        dominant_platform = row['dominant_platform'].strip()

        try:
            dominant_count = int(row['dominant_count'])
        except ValueError:
            dominant_count = 0
            errors.append(f"Row {row_num}: Invalid dominant_count")

        try:
            stability_percent = float(row['stability_percent'])
        except ValueError:
            stability_percent = 0.0
            errors.append(f"Row {row_num}: Invalid stability_percent")

        return {
            "train_number": train_number,
            "platform_occurrences": platform_occurrences,
            "total_occurrences": total_occurrences,
            "dominant_platform": dominant_platform,
            "dominant_count": dominant_count,
            "stability_percent": stability_percent,
            "loaded_at": datetime.now(UTC)
        }

    @classmethod
    async def _upsert_platform_history(cls, document: Dict[str, Any]) -> bool:
        """Upsert a document, returning True if a new record was inserted."""
        result = await MongoDB.database[cls.COLLECTION_NAME].update_one(
            {"train_number": document["train_number"]},
            {"$set": document},
            upsert=True
        )
        return bool(result.upserted_id)

    @classmethod
    async def _process_csv_row(cls, row: Dict[str, str], row_num: int, errors: List[str]) -> Optional[bool]:
        """Process one row. Returns True/False for inserted/updated, or None if skipped/errored."""
        try:
            document = cls._parse_csv_row(row, row_num, errors)
            if document is None:
                return None
            return await cls._upsert_platform_history(document)
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")
            logger.exception(f"Error processing row {row_num}")
            return None

    @classmethod
    def _read_csv_rows(cls, csv_text: str) -> Tuple[List[str], List[Dict[str, str]]]:
        reader = csv.DictReader(csv_text.splitlines())
        fieldnames = reader.fieldnames or []
        return fieldnames, list(reader)

    @classmethod
    async def load_platform_history_from_csv(cls, csv_path: str) -> Dict[str, int]:
        """
        Load platform history from CSV into MongoDB.

        CSV Format (expected columns):
            train_number,PF 1,PF 2,PF 3,PF 4,PF 5,PF 6,PF 7,PF 8,PF 9,
            total_occurrences,dominant_platform,dominant_count,stability_percent

        Args:
            csv_path: Path to CSV file

        Returns:
            dict: Statistics
                {
                    "records_loaded": int,
                    "records_updated": int,
                    "errors": list
                }

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            Exception: For CSV parsing or database errors
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        logger.info(f"Loading platform history from: {csv_path}")

        records_loaded = 0
        records_updated = 0
        errors: List[str] = []

        try:
            async with aiofiles.open(csv_path, 'r', encoding='utf-8') as csvfile:
                csv_text = await csvfile.read()

            fieldnames, rows = cls._read_csv_rows(csv_text)

            missing = [col for col in REQUIRED_CSV_COLUMNS if col not in fieldnames]
            if missing:
                raise ValueError(f"CSV missing required columns: {missing}")

            for row_num, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
                inserted = await cls._process_csv_row(row, row_num, errors)
                if inserted is True:
                    records_loaded += 1
                elif inserted is False:
                    records_updated += 1

            logger.info(f"Platform history loaded: {records_loaded} new, {records_updated} updated")

            if errors:
                logger.warning(f"Encountered {len(errors)} errors during CSV load")

            return {
                "records_loaded": records_loaded,
                "records_updated": records_updated,
                "total_records": records_loaded + records_updated,
                "errors": errors[:100]  # Limit to first 100 errors
            }

        except Exception:
            logger.exception("Failed to load platform history")
            raise

    @classmethod
    async def get_train_platform_history(cls, train_number: str) -> Optional[Dict]:
        """
        Get platform history for a specific train.

        Args:
            train_number: Train identifier

        Returns:
            dict: Platform history document or None if not found
        """
        return await MongoDB.database[cls.COLLECTION_NAME].find_one({"train_number": train_number})

    @classmethod
    async def get_expected_platforms_for_train(cls, train_number: str) -> List[Dict]:
        """
        Get all platforms where this train could appear (worst-case safety).

        For unstable trains (e.g., 50-50 split between PF 3 and PF 4),
        returns BOTH platforms to ensure no safety risk is missed.

        Args:
            train_number: Train identifier

        Returns:
            list: List of platform dictionaries
                [
                    {
                        "platform": "PF 3",
                        "count": 1,
                        "probability": 0.5,
                        "islands": ["island_2_3"]
                    },
                    {
                        "platform": "PF 4",
                        "count": 1,
                        "probability": 0.5,
                        "islands": ["island_4_5"]
                    }
                ]

            Empty list if train not found in history
        """
        history = await cls.get_train_platform_history(train_number)

        if not history:
            return []

        platforms = []
        total_occurrences = history.get('total_occurrences', 0)

        if total_occurrences == 0:
            return []

        # Return ALL platforms with >0 occurrences
        for platform, count in history.get('platform_occurrences', {}).items():
            if count > 0:
                probability = count / total_occurrences

                # Map platform to island(s)
                islands = island_platform_service.map_platform_to_islands(platform)

                platforms.append({
                    "platform": platform,
                    "count": count,
                    "probability": probability,
                    "islands": islands
                })

        return platforms

    @classmethod
    async def get_platform_stability(cls, train_number: str) -> Dict:
        """
        Get platform stability information for a train.

        Args:
            train_number: Train identifier

        Returns:
            dict: Stability info
                {
                    "train_number": str,
                    "dominant_platform": str,
                    "stability_percent": float,
                    "certainty": str,  # HIGH/MEDIUM/LOW
                    "is_stable": bool,  # True if ≥80%
                    "found": bool
                }
        """
        history = await cls.get_train_platform_history(train_number)

        if not history:
            return {
                "train_number": train_number,
                "dominant_platform": None,
                "stability_percent": 0.0,
                "certainty": "LOW",
                "is_stable": False,
                "found": False
            }

        stability_percent = history.get('stability_percent', 0.0)
        certainty = island_platform_service.get_certainty_label(stability_percent)

        return {
            "train_number": train_number,
            "dominant_platform": history.get('dominant_platform'),
            "stability_percent": stability_percent,
            "certainty": certainty,
            "is_stable": stability_percent >= 80.0,
            "found": True
        }

    @classmethod
    async def get_collection_stats(cls) -> Dict:
        """
        Get statistics about the platform history collection.

        Returns:
            dict: Collection statistics
                {
                    "total_trains": int,
                    "stable_trains": int,  # ≥80% stability
                    "unstable_trains": int,  # <80% stability
                    "last_loaded_at": datetime
                }
        """
        total_trains = await MongoDB.database[cls.COLLECTION_NAME].count_documents({})

        stable_trains = await MongoDB.database[cls.COLLECTION_NAME].count_documents({
            "stability_percent": {"$gte": 80.0}
        })

        unstable_trains = total_trains - stable_trains

        # Get most recent load timestamp
        recent = await MongoDB.database[cls.COLLECTION_NAME].find_one(
            {},
            sort=[("loaded_at", -1)],
            projection={"loaded_at": 1}
        )

        last_loaded_at = recent.get('loaded_at') if recent else None

        return {
            "total_trains": total_trains,
            "stable_trains": stable_trains,
            "unstable_trains": unstable_trains,
            "last_loaded_at": last_loaded_at
        }


# Singleton instance
platform_history_service = PlatformHistoryService()
