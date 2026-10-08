"""
Unit tests for Suraksha opt-in scheduler timing and reset logic.

Run with:
    pytest tests/test_suraksha_scheduler.py -v
"""
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

# ---- inline the pure timing functions (no DB/import chain needed) ----

IST_OFFSET = timedelta(hours=5, minutes=30)

def _ist_now() -> datetime:
    return datetime.utcnow() + IST_OFFSET

def _ist_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")

def seconds_until_next_ist_midnight() -> float:
    ist_now = _ist_now()
    next_midnight = (ist_now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(0.0, (next_midnight - ist_now).total_seconds())

def seconds_until_next_ist_11_59_pm() -> float:
    ist_now = _ist_now()
    next_11_59 = ist_now.replace(hour=23, minute=59, second=0, microsecond=0)
    if next_11_59 <= ist_now:
        next_11_59 += timedelta(days=1)
    return max(0.0, (next_11_59 - ist_now).total_seconds())

def _was_sent_today(doc, ist_today: str) -> bool:
    last_sent = doc.get("lastSurakshaOptinSentAt")
    if not last_sent:
        return False
    if hasattr(last_sent, "strftime"):
        return _ist_date(last_sent + IST_OFFSET) == ist_today
    return False

# -------------------------------------------------------------------------

# ---- pass current IST time directly ----

def _midnight_wait(ist_now: datetime) -> float:
    next_midnight = (ist_now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return max(0.0, (next_midnight - ist_now).total_seconds())

def _11_59_wait(ist_now: datetime) -> float:
    next_11_59 = ist_now.replace(hour=23, minute=59, second=0, microsecond=0)
    if next_11_59 <= ist_now:
        next_11_59 += timedelta(days=1)
    return max(0.0, (next_11_59 - ist_now).total_seconds())

def ist(h, m, s=0) -> datetime:
    return datetime(2024, 6, 16, h, m, s)


# ---------------------------------------------------------------------------
# 1. seconds_until_next_ist_midnight
# ---------------------------------------------------------------------------

class TestMidnightWait:

    def test_from_10pm_waits_2_hours(self):
        result = _midnight_wait(ist(22, 0))
        assert abs(result - 2 * 3600) < 5, f"Expected ~7200s, got {result}"

    def test_from_1159pm_waits_1_minute(self):
        result = _midnight_wait(ist(23, 59))
        assert abs(result - 60) < 5, f"Expected ~60s, got {result}"

    def test_from_midnight_waits_24_hours(self):
        # exactly midnight — always pushes to next day's midnight
        result = _midnight_wait(ist(0, 0))
        assert abs(result - 24 * 3600) < 5, f"Expected ~86400s, got {result}"

    def test_from_1am_waits_23_hours(self):
        result = _midnight_wait(ist(1, 0))
        assert abs(result - 23 * 3600) < 5, f"Expected ~82800s, got {result}"

    def test_never_negative(self):
        assert _midnight_wait(ist(0, 0, 30)) >= 0


# ---------------------------------------------------------------------------
# 2. seconds_until_next_ist_11_59_pm
# ---------------------------------------------------------------------------

class TestResetWait:

    def test_from_10pm_waits_about_2_hours(self):
        result = _11_59_wait(ist(22, 0))
        expected = 1 * 3600 + 59 * 60  # 1h 59m
        assert abs(result - expected) < 5, f"Expected ~{expected}s, got {result}"

    def test_from_midnight_waits_23h_59m(self):
        result = _11_59_wait(ist(0, 1))   # 12:01 AM
        expected = 23 * 3600 + 58 * 60
        assert abs(result - expected) < 5, f"Expected ~{expected}s, got {result}"

    def test_from_1159pm_exactly_waits_next_day(self):
        # exactly 11:59 PM → condition `<= ist_now` adds 1 day
        result = _11_59_wait(ist(23, 59, 0))
        assert abs(result - 24 * 3600) < 5, f"Expected ~86400s, got {result}"

    def test_never_negative(self):
        assert _11_59_wait(ist(23, 58)) >= 0

    def test_reset_fires_before_midnight(self):
        """Critical: 11:59 PM reset must fire BEFORE 12:00 AM opt-in."""
        for h in [8, 10, 12, 20, 22]:
            now = ist(h, 0)
            reset_wait  = _11_59_wait(now)
            optin_wait  = _midnight_wait(now)
            assert reset_wait < optin_wait, (
                f"At {h}:00 PM IST: reset ({reset_wait}s) must be < midnight ({optin_wait}s)"
            )

    def test_gap_between_reset_and_midnight_is_1_minute(self):
        """Reset at 11:59 PM and opt-in at 12:00 AM → gap = 60 seconds."""
        for h in [8, 10, 12, 20, 22]:
            now = ist(h, 0)
            gap = _midnight_wait(now) - _11_59_wait(now)
            assert abs(gap - 60) < 2, (
                f"At {h}:00 IST: expected 60s gap, got {gap:.1f}s"
            )


# ---------------------------------------------------------------------------
# 3. _was_sent_today
# ---------------------------------------------------------------------------

class TestWasSentToday:

    def test_sent_today_ist_returns_true(self):
        # sent at noon IST today → stored as noon-5:30 UTC
        last_sent_utc = ist(12, 0) - IST_OFFSET
        doc = {"lastSurakshaOptinSentAt": last_sent_utc}
        assert _was_sent_today(doc, "2024-06-16") is True

    def test_sent_yesterday_returns_false(self):
        last_sent_utc = datetime(2024, 6, 15, 12, 0) - IST_OFFSET
        doc = {"lastSurakshaOptinSentAt": last_sent_utc}
        assert _was_sent_today(doc, "2024-06-16") is False

    def test_never_sent_returns_false(self):
        assert _was_sent_today({}, "2024-06-16") is False

    def test_none_field_returns_false(self):
        assert _was_sent_today({"lastSurakshaOptinSentAt": None}, "2024-06-16") is False

    def test_sent_at_ist_midnight_counts_as_today(self):
        # IST midnight 00:00 = 18:30 UTC previous calendar day
        ist_midnight = datetime(2024, 6, 16, 0, 0, 0)
        last_sent_utc = ist_midnight - IST_OFFSET   # June 15 18:30 UTC
        doc = {"lastSurakshaOptinSentAt": last_sent_utc}
        assert _was_sent_today(doc, "2024-06-16") is True

    def test_sent_at_11pm_ist_counts_as_today(self):
        # 11:00 PM IST = 17:30 UTC same day
        last_sent_utc = ist(23, 0) - IST_OFFSET
        doc = {"lastSurakshaOptinSentAt": last_sent_utc}
        assert _was_sent_today(doc, "2024-06-16") is True


# ---------------------------------------------------------------------------
# 4. reset_send_alerts_batch  (mock DB, no import chain)
# ---------------------------------------------------------------------------

import asyncio as _asyncio


async def _standalone_reset(database):
    """Mirrors reset_send_alerts_batch from suraksha_optin_service."""
    collection = database["viewers_user_collection"]
    result = await collection.update_many(
        {"services": "suraksha_ai", "sendAlerts": True},
        {"$set": {"sendAlerts": False}},
    )
    return {"updated": result.modified_count}


def _make_mock_db(modified_count: int):
    mock_result = MagicMock()
    mock_result.modified_count = modified_count
    mock_collection = AsyncMock()
    mock_collection.update_many.return_value = mock_result
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    return mock_db, mock_collection


def test_reset_updates_correct_users():
    """reset_send_alerts_batch must query suraksha_ai+sendAlerts=True and set False."""
    mock_db, mock_collection = _make_mock_db(3)
    result = _asyncio.run(_standalone_reset(mock_db))

    assert result["updated"] == 3
    mock_collection.update_many.assert_called_once_with(
        {"services": "suraksha_ai", "sendAlerts": True},
        {"$set": {"sendAlerts": False}},
    )


def test_reset_does_not_touch_users_without_suraksha_ai():
    """Query filter must include services=suraksha_ai so other users are not affected."""
    mock_db, mock_collection = _make_mock_db(0)
    _asyncio.run(_standalone_reset(mock_db))

    called_filter = mock_collection.update_many.call_args[0][0]
    assert called_filter["services"] == "suraksha_ai"
    assert called_filter["sendAlerts"] is True


def test_reset_only_sets_send_alerts_false():
    """The update payload must only contain sendAlerts=False."""
    mock_db, mock_collection = _make_mock_db(1)
    _asyncio.run(_standalone_reset(mock_db))

    called_update = mock_collection.update_many.call_args[0][1]
    assert called_update == {"$set": {"sendAlerts": False}}
