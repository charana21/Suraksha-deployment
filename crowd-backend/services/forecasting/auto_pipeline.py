"""
Auto-Pipeline Trigger for UTS & PRS Forecasting.

This module provides:
  1. `AutoForecastTrigger.trigger()` — call this immediately after any
     historical_data write to kick off a non-blocking pipeline run.
  2. `AutoForecastTrigger.start_watcher()` — long-running asyncio task that
     polls `historical_data` every N minutes and auto-runs the pipeline
     whenever the document count (or latest date) increases.  This catches
     writes that arrive through paths other than the upload endpoint
     (e.g. the seeding script, direct Mongo inserts, etc.).

Design principles
─────────────────
• Only one pipeline run at a time (asyncio.Lock).  Concurrent triggers are
  silently dropped (the in-progress run already covers them).
• Never raises — a pipeline failure is logged but never propagates to the
  caller or breaks any other service.
• Fully independent of the rest of the application.  Import and call; no
  coupling to routes or other services.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Interval between background polls (seconds).  5 minutes is a reasonable
# default: low enough to catch manual inserts quickly, high enough not to
# waste CPU on training.
POLL_INTERVAL_SECONDS: int = 300  # 5 minutes


class AutoForecastTrigger:
    """
    Singleton-style class that holds shared state for the auto-pipeline.

    Usage
    ─────
        # In startup:
        AutoForecastTrigger.start_watcher_task()

        # After every historical_data upload / insert:
        await AutoForecastTrigger.trigger("manual_upload")

        # In shutdown:
        AutoForecastTrigger.stop()
    """

    _lock: asyncio.Lock = asyncio.Lock()
    _pipeline_running: bool = False
    _pipeline_scheduled: bool = False
    _rerun_requested: bool = False
    _last_doc_count: int = -1
    _last_max_date: Optional[str] = None
    _watcher_task: Optional[asyncio.Task] = None
    _stop_event: asyncio.Event = asyncio.Event()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    @classmethod
    async def trigger(cls, reason: str = "unknown") -> None:
        """
        Request a pipeline run.  If a run is already in progress the call
        returns immediately — the running pipeline will incorporate any new
        data via its own load_historical_data_sync() call.
        """
        if cls._pipeline_running or cls._pipeline_scheduled:
            # A write can arrive after the worker has loaded its input but before it
            # completes.  Remember it so that the completed run is never mistaken for
            # a forecast based on the newest history.
            cls._rerun_requested = True
            logger.info(
                f"[AutoForecast] Pipeline already queued/running; "
                f"changes from '{reason}' will be included in a follow-up run."
            )
            return

        cls._pipeline_scheduled = True
        asyncio.create_task(cls._run_pipeline(reason))

    @classmethod
    def start_watcher_task(cls) -> asyncio.Task:
        """
        Spawns the background polling loop.  Call once during app startup.
        Returns the asyncio.Task so the caller can store and cancel it.
        """
        cls._stop_event.clear()
        cls._watcher_task = asyncio.create_task(
            cls._watch_historical_data(), name="auto_forecast_watcher"
        )
        logger.info(
            f"[AutoForecast] Watcher started (poll interval={POLL_INTERVAL_SECONDS}s)."
        )
        return cls._watcher_task

    @classmethod
    def stop(cls) -> None:
        """Signal the watcher loop to exit on its next iteration."""
        cls._stop_event.set()
        if cls._watcher_task and not cls._watcher_task.done():
            cls._watcher_task.cancel()
            logger.info("[AutoForecast] Watcher task cancelled.")

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @classmethod
    async def _run_pipeline(cls, reason: str) -> None:
        """
        Acquires the lock, sets the running flag, executes the pipeline in
        a worker thread (so the event loop is never blocked), then updates
        internal state.  All exceptions are swallowed after logging.
        """
        async with cls._lock:
            cls._pipeline_scheduled = False
            if cls._pipeline_running:
                logger.info(
                    f"[AutoForecast] Concurrent run detected inside lock (reason='{reason}'); skipping."
                )
                return

            cls._pipeline_running = True
            started_at = datetime.now(timezone.utc)
            logger.info(
                f"[AutoForecast] Pipeline starting (reason='{reason}', at={started_at.isoformat()})..."
            )

            try:
                from services.forecasting.runner import ForecastingRunner

                # skip_backtest=False → model selection re-runs on each full pipeline.
                # Change to True for faster re-runs that reuse the last best model.
                result = await ForecastingRunner.run_pipeline_async(skip_backtest=False)

                finished_at = datetime.now(timezone.utc)
                elapsed = (finished_at - started_at).total_seconds()
                logger.info(
                    f"[AutoForecast] Pipeline completed in {elapsed:.1f}s "
                    f"(reason='{reason}', status={result.get('status')}, "
                    f"forecast_days={result.get('forecast_days')})."
                )
            except Exception:
                logger.exception(
                    f"[AutoForecast] Pipeline FAILED (reason='{reason}'). "
                    "forecasting_data collection may be stale."
                )
            finally:
                cls._pipeline_running = False
                if cls._rerun_requested:
                    cls._rerun_requested = False
                    cls._pipeline_scheduled = True
                    logger.info(
                        "[AutoForecast] Historical data changed during training; "
                        "starting a follow-up retraining run."
                    )
                    asyncio.create_task(cls._run_pipeline("changes_during_pipeline"))

    @classmethod
    async def _get_historical_snapshot(cls) -> tuple[int, Optional[str]]:
        """
        Returns (doc_count, max_date_str) from the `historical_data`
        collection.  Uses the async Motor client (safe on the event loop).
        Returns (-1, None) if the database is not yet connected.
        """
        try:
            from db.mongodb import MongoDB
            from services.forecasting.forecasting_config import HISTORICAL_COLLECTION

            if MongoDB.database is None:
                return -1, None

            collection = MongoDB.database[HISTORICAL_COLLECTION]
            count = await collection.count_documents({})

            # Find the most-recently-dated document
            cursor = collection.find({}, {"date": 1, "_id": 0}).sort("date", -1).limit(1)
            doc = await cursor.to_list(length=1)
            max_date = doc[0]["date"] if doc else None

            return count, max_date
        except Exception as e:
            logger.debug(f"[AutoForecast] Snapshot check failed: {e}")
            return -1, None

    @classmethod
    async def _watch_historical_data(cls) -> None:
        """
        Background polling loop.  Wakes up every POLL_INTERVAL_SECONDS,
        checks if `historical_data` has grown, and fires the pipeline if so.
        The first successful poll also initialises the baseline.
        """
        logger.info("[AutoForecast] Watcher loop running.")

        # Wait a short time at startup to let MongoDB finish connecting
        await asyncio.sleep(10)

        while not cls._stop_event.is_set():
            try:
                count, max_date = await cls._get_historical_snapshot()

                if count == -1:
                    # DB not yet ready — keep waiting
                    pass
                elif cls._last_doc_count == -1:
                    # First successful read: establish baseline, don't trigger
                    cls._last_doc_count = count
                    cls._last_max_date = max_date
                    logger.info(
                        f"[AutoForecast] Baseline established: "
                        f"{count} docs, max_date={max_date}."
                    )
                elif count != cls._last_doc_count or max_date != cls._last_max_date:
                    logger.info(
                        f"[AutoForecast] Change detected in historical_data "
                        f"({cls._last_doc_count} → {count} docs, "
                        f"max_date {cls._last_max_date} → {max_date}). "
                        "Triggering pipeline..."
                    )
                    cls._last_doc_count = count
                    cls._last_max_date = max_date
                    await cls.trigger("watcher_poll_change")

            except Exception as e:
                logger.debug(f"[AutoForecast] Watcher iteration error: {e}")

            try:
                await asyncio.wait_for(
                    cls._stop_event.wait(), timeout=POLL_INTERVAL_SECONDS
                )
            except asyncio.TimeoutError:
                pass  # Normal — just the poll interval expiring

        logger.info("[AutoForecast] Watcher loop exited.")
