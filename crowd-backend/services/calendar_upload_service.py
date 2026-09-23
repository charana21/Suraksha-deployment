"""
Calendar and Special Trains data upload service
Handles Excel parsing and database operations for footfall insights
"""
import re
import pandas as pd
from datetime import UTC, datetime
from typing import Optional, List, Dict, Any
from io import BytesIO
from db.mongodb import MongoDB
from util.constants import DATABASE_NOT_CONNECTED, NO_VALID_RECORDS_FOUND

class CalendarUploadService:
    """Service to handle uploads for calendar and special_trains collections"""

    @staticmethod
    def _safe_int(val: Any) -> int:
        if pd.isna(val) or val is None:
            return 0
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _parse_date(val: Any) -> Optional[datetime]:
        if pd.isna(val) or val is None:
            return None
        
        # Handle pandas Timestamp
        if isinstance(val, pd.Timestamp):
            return val.to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)
            
        # Handle string date
        if isinstance(val, str):
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    dt = datetime.strptime(val.split('T')[0].split(' ')[0], fmt.split('T')[0].split(' ')[0])
                    return dt.replace(hour=0, minute=0, second=0, microsecond=0)
                except ValueError:
                    continue
        
        # Handle Excel serial
        if isinstance(val, (int, float)):
            try:
                dt = pd.to_datetime(val, unit='D', origin='1899-12-30')
                return dt.replace(hour=0, minute=0, second=0, microsecond=0)
            except (ValueError, TypeError, OverflowError):
                pass
                
        return None

    @staticmethod
    def _normalize_name(value: Any) -> str:
        if value is None:
            return ""
        return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())

    @staticmethod
    def _normalize_columns(df: pd.DataFrame, mapping: Dict[str, List[str]]) -> Dict[str, str]:
        actual_cols_norm = {CalendarUploadService._normalize_name(col): col for col in df.columns}
        col_map = {}
        for expected, variants in mapping.items():
            for variant in variants:
                normalized_variant = CalendarUploadService._normalize_name(variant)
                if normalized_variant in actual_cols_norm:
                    col_map[expected] = actual_cols_norm[normalized_variant]
                    break
        return col_map

    @staticmethod
    def _read_upload_dataframe(file_content: bytes, filename: str) -> pd.DataFrame:
        lower_name = (filename or "").lower()
        if lower_name.endswith(".csv"):
            return pd.read_csv(BytesIO(file_content))
        return pd.read_excel(BytesIO(file_content))

    @staticmethod
    async def _upsert_calendar_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
        if MongoDB.database is None:
            raise RuntimeError(DATABASE_NOT_CONNECTED)

        collection = MongoDB.database.calendar
        now = datetime.now(UTC)

        if not records:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        seen_keys = set()
        unique_records = []
        for rec in records:
            key = (rec["train_number"], rec["schedule_date"])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            unique_records.append(rec)

        train_numbers = list({rec["train_number"] for rec in unique_records})
        schedule_dates = list({rec["schedule_date"] for rec in unique_records})

        existing_docs = await collection.find(
            {
                "train_number": {"$in": train_numbers},
                "schedule_date": {"$in": schedule_dates},
            },
            {"train_number": 1, "schedule_date": 1, "boarding_count": 1, "deboarding_count": 1, "total_passengers": 1},
        ).to_list(length=None)

        existing_map = {
            (doc["train_number"], doc["schedule_date"]): doc for doc in existing_docs
        }

        from pymongo import UpdateOne

        operations = []
        inserted = 0
        updated = 0
        skipped = 0

        for rec in unique_records:
            filter_key = {
                "train_number": rec["train_number"],
                "schedule_date": rec["schedule_date"],
            }
            existing = existing_map.get((rec["train_number"], rec["schedule_date"]))

            if existing is None:
                operations.append(UpdateOne(
                    filter_key,
                    {
                        "$set": {
                            "boarding_count": rec.get("boarding_count", 0),
                            "deboarding_count": rec.get("deboarding_count", 0),
                            "total_passengers": rec.get("total_passengers", 0),
                            "updated_at": now,
                        },
                        "$setOnInsert": {"uploaded_at": now},
                    },
                    upsert=True,
                ))
                inserted += 1
                continue

            if (
                existing.get("boarding_count") != rec.get("boarding_count", 0)
                or existing.get("deboarding_count") != rec.get("deboarding_count", 0)
                or existing.get("total_passengers") != rec.get("total_passengers", 0)
            ):
                operations.append(UpdateOne(
                    filter_key,
                    {
                        "$set": {
                            "boarding_count": rec.get("boarding_count", 0),
                            "deboarding_count": rec.get("deboarding_count", 0),
                            "total_passengers": rec.get("total_passengers", 0),
                            "updated_at": now,
                        }
                    },
                ))
                updated += 1
            else:
                skipped += 1

        if operations:
            await collection.bulk_write(operations, ordered=False)

        return {
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
        }

    @staticmethod
    async def upload_calendar_excel(file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse and upload calendar (boarding/deboarding) data.
        Expected columns: _id, schedule_date, train_number, boarding_count, deboarding_count, total_passengers
        """
        if MongoDB.database is None:
            raise RuntimeError(DATABASE_NOT_CONNECTED)

        df = CalendarUploadService._read_upload_dataframe(file_content, filename)
        
        col_mapping = {
            "_id": ["_id", "id", "objectid"],
            "schedule_date": ["schedule_date", "date", "schedule date", "scheduled date", "scheduled_date", "scheduleddate"],
            "train_number": ["train_number", "train", "train no", "train number", "trainno"],
            "boarding_count": ["boarding_count", "boarding", "boarding count", "boardingcount"],
            "deboarding_count": ["deboarding_count", "deboarding", "deboarding count", "deboardingcount"],
            "total_passengers": ["total_passengers", "total", "total passengers", "pax", "totalpassengers"]
        }
        
        col_map = CalendarUploadService._normalize_columns(df, col_mapping)
        records = []
        errors = []

        for idx in range(len(df)):
            try:
                row = df.iloc[idx]

                schedule_col = col_map.get("schedule_date", "schedule_date")
                train_col = col_map.get("train_number", "train_number")
                boarding_col = col_map.get("boarding_count", "boarding_count")
                deboarding_col = col_map.get("deboarding_count", "deboarding_count")
                total_col = col_map.get("total_passengers", "total_passengers")

                date_val = CalendarUploadService._parse_date(row.get(schedule_col))
                if not date_val:
                    errors.append(f"Row {idx+2}: Missing or invalid schedule_date")
                    continue

                train_val = row.get(train_col)
                train_num = str(train_val).strip().split('.')[0] if pd.notna(train_val) else ""
                if not train_num or train_num == "nan":
                    errors.append(f"Row {idx+2}: Missing train_number")
                    continue

                records.append({
                    "schedule_date": date_val,
                    "train_number": train_num,
                    "boarding_count": CalendarUploadService._safe_int(row.get(boarding_col)),
                    "deboarding_count": CalendarUploadService._safe_int(row.get(deboarding_col)),
                    "total_passengers": CalendarUploadService._safe_int(row.get(total_col)),
                })
            except Exception as e:
                errors.append(f"Row {idx+2}: {str(e)}")

        if not records:
            return {"status": "error", "message": NO_VALID_RECORDS_FOUND, "errors": errors}

        write_result = await CalendarUploadService._upsert_calendar_records(records)
        
        return {
            "status": "success",
           
            "records_inserted": write_result["inserted"],
            "records_updated": write_result["updated"],
            "records_skipped": write_result["skipped"],
            "errors": errors[:10]
        }

    @staticmethod
    async def upload_special_trains_excel(file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Parse and upload special trains data.
        Expected columns: train_number, schedule_date, total_passengers
        """
        if MongoDB.database is None:
            raise RuntimeError(DATABASE_NOT_CONNECTED)

        df = CalendarUploadService._read_upload_dataframe(file_content, filename)
        
        col_mapping = {
            "train_number": ["train_number", "train", "train no", "train number"],
            "schedule_date": ["schedule_date", "date", "schedule date"],
            "total_passengers": ["total_passengers", "total", "total passengers", "pax"]
        }
        
        col_map = CalendarUploadService._normalize_columns(df, col_mapping)
        records = []
        errors = []
        
        for idx, row in df.iterrows():
            try:
                record = {}
                
                # Handle train_number
                train_num = str(row.get(col_map.get("train_number", "train_number"))).strip().split('.')[0]
                if train_num and train_num != "nan":
                    record["train_number"] = train_num
                else:
                    errors.append(f"Row {idx+2}: Missing train_number")
                    continue

                # Handle schedule_date
                date_val = CalendarUploadService._parse_date(row.get(col_map.get("schedule_date", "schedule_date")))
                if date_val:
                    record["schedule_date"] = date_val
                else:
                    errors.append(f"Row {idx+2}: Missing or invalid schedule_date")
                    continue

                # Numeric fields
                record["total_passengers"] = CalendarUploadService._safe_int(row.get(col_map.get("total_passengers", "total_passengers")))
                
                record["updated_at"] = datetime.now(UTC)
                records.append(record)
            except Exception as e:
                errors.append(f"Row {idx+2}: {str(e)}")

        if not records:
            return {"status": "error", "message": NO_VALID_RECORDS_FOUND, "errors": errors}

        from pymongo import UpdateOne
        operations = []
        for rec in records:
            filter_key = {"train_number": rec["train_number"], "schedule_date": rec["schedule_date"]}
            operations.append(UpdateOne(filter_key, {"$set": rec}, upsert=True))

        result = await MongoDB.database.special_trains.bulk_write(operations, ordered=False)
        
        return {
            "status": "success",
            "records_processed": len(df),
            "records_inserted": result.upserted_count,
            "records_updated": result.modified_count,
            "records_skipped": result.matched_count - result.modified_count,
            "errors": errors[:10]
        }
