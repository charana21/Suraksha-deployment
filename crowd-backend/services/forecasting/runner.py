"""
High-level orchestrator for the UTS & PRS forecasting pipeline.
Loads historical data from `historical_data` in MongoDB, trains models,
generates upcoming-month predictions, and stores results into `forecasting_data`.
"""
import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple
import pandas as pd

from . import forecasting_config as config
from .data_loader import load_historical_data_sync, build_target_series
from .common import CalendarFeatures
from .modeling import run_backtest
from .forecasting_engine import build_full_forecast_table
from .db_service import ForecastingDBService

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))
WINNER_CACHE_PATH = os.path.join(CACHE_DIR, "last_backtest_winner.json")

DEFAULT_WINNERS = {"UTS Total": "GBM_quantile65", "PRS Total": "GBM_quantile65"}


class ForecastingRunner:
    """Manages training and prediction generation runs."""

    @staticmethod
    def load_cached_winners() -> Tuple[Dict[str, str], Dict[str, Any]]:
        if os.path.isfile(WINNER_CACHE_PATH):
            try:
                with open(WINNER_CACHE_PATH, "r") as f:
                    data = json.load(f)
                    return data.get("winners", DEFAULT_WINNERS), data.get("winner_members", {})
            except Exception as e:
                logger.warning(f"Failed to read cached winners: {e}")
        return dict(DEFAULT_WINNERS), {}

    @staticmethod
    def save_cached_winners(winners: Dict[str, str], winner_members: Dict[str, Any]):
        try:
            with open(WINNER_CACHE_PATH, "w") as f:
                json.dump({"winners": winners, "winner_members": winner_members}, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cached winners: {e}")

    @classmethod
    def select_models(cls, df: pd.DataFrame, skip_backtest: bool = False) -> Tuple[Dict[str, str], Dict[str, Any], Dict[str, Any]]:
        if skip_backtest:
            winners, members = cls.load_cached_winners()
            logger.info(f"Skipping backtest, using winners: {winners}")
            return winners, members, {}

        # The validation calendar must include every historical record.  Otherwise
        # newly supplied years cannot affect the model comparison.
        calendar_end = max(config.FORECAST_END, pd.Timestamp(df['Date'].max()))
        cf_hist = CalendarFeatures(df, calendar_end)
        base = cf_hist.base_frame()
        idx_of_date = cf_hist.idx_of_date

        winners, winner_members, validation_results = {}, {}, {}
        for target in config.TARGETS:
            logger.info(f"Running backtest for {target}...")
            values_actual_full, values_for_features_full, values_actual_clean = build_target_series(
                df, target, idx_of_date, cf_hist.n)
            winner, members, avg, _ = run_backtest(
                df, cf_hist, base, target, idx_of_date, cf_hist.n,
                values_for_features_full, values_actual_full, values_actual_clean, verbose=False
            )
            logger.info(f"Target '{target}' winner: {winner}")
            winners[target] = winner
            winner_members[target] = members
            validation_results[target] = avg.to_dict(orient="records")

        cls.save_cached_winners(winners, winner_members)
        return winners, winner_members, validation_results

    @classmethod
    def run_pipeline_sync(cls, skip_backtest: bool = True) -> Dict[str, Any]:
        """
        Synchronous pipeline run:
        1. Load historical data from MongoDB `historical_data`.
        2. Run feature engineering and model training.
        3. Generate predictions for upcoming months.
        4. Save to `forecasting_data` collection in MongoDB.
        """
        logger.info("Starting UTS/PRS forecasting pipeline run...")
        df = load_historical_data_sync()
        logger.info(f"Loaded {len(df)} historical rows ({df['Date'].min().date()} to {df['Date'].max().date()})")

        winners, winner_members, validation_results = cls.select_models(df, skip_backtest=skip_backtest)

        logger.info("Generating full forecast table for complete year 2026 (Jan 01 - Dec 31, 2026)...")
        wide_df = build_full_forecast_table(df, winners, winner_members)

        db_result = ForecastingDBService.save_predictions_sync(wide_df)

        return {
            "status": "success",
            "historical_rows": len(df),
            "forecast_days": len(wide_df),
            "winners": winners,
            "validation_results": validation_results,
            "db_result": db_result,
        }

    @classmethod
    async def run_pipeline_async(cls, skip_backtest: bool = True) -> Dict[str, Any]:
        """Runs the pipeline asynchronously in a worker thread to avoid blocking FastAPI."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, cls.run_pipeline_sync, skip_backtest)


def run_forecasting_pipeline(skip_backtest: bool = True) -> Dict[str, Any]:
    return ForecastingRunner.run_pipeline_sync(skip_backtest=skip_backtest)
