import asyncio

import pandas as pd

from services.forecasting.auto_pipeline import AutoForecastTrigger
from services.forecasting.modeling import get_validation_cutoffs, select_winner


def test_validation_cutoffs_expand_with_available_history():
    df = pd.DataFrame({"Date": pd.date_range("2022-03-01", "2028-12-31", freq="D")})

    assert get_validation_cutoffs(df) == [
        "2023-08-25", "2024-08-25", "2025-08-25",
        "2026-08-25", "2027-08-25", "2028-08-25",
    ]


def test_best_validation_accuracy_wins():
    results = pd.DataFrame([
        {"model": "RandomForest_raw", "validation_accuracy": 91.0, "MAE": 100, "violation_pct": 2},
        {"model": "GradientBoosting_raw", "validation_accuracy": 95.0, "MAE": 200, "violation_pct": 3},
    ])

    assert select_winner(results) == "GradientBoosting_raw"


def test_trigger_queues_follow_up_run_when_training_is_active():
    async def exercise():
        old_running = AutoForecastTrigger._pipeline_running
        old_scheduled = AutoForecastTrigger._pipeline_scheduled
        old_rerun = AutoForecastTrigger._rerun_requested
        try:
            AutoForecastTrigger._pipeline_running = True
            AutoForecastTrigger._pipeline_scheduled = False
            AutoForecastTrigger._rerun_requested = False
            await AutoForecastTrigger.trigger("test_write")
            assert AutoForecastTrigger._rerun_requested is True
        finally:
            AutoForecastTrigger._pipeline_running = old_running
            AutoForecastTrigger._pipeline_scheduled = old_scheduled
            AutoForecastTrigger._rerun_requested = old_rerun

    asyncio.run(exercise())
