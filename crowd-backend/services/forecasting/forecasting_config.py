"""
Configuration for the UTS/PRS forecasting pipeline.
"""
import pandas as pd

TARGETS = ["UTS Total", "PRS Total"]

# Forecast window - Full Year 2026 (January to December)
FORECAST_START = pd.Timestamp("2026-01-01")
FORECAST_END = pd.Timestamp("2026-12-31")

MIN_TRAIN_START_IDX = 365
FOLD_CUTOFFS = ["2023-08-25", "2024-08-25", "2025-08-25"]

UNDER_THRESHOLD = 5000.0
OVER_THRESHOLD = 7500.0
UNDER_PENALTY_WEIGHT = 2.0
ENSEMBLE_SIZE = 3

# Known sensor-outage days
BAD_DAY_BY_TARGET = {
    "UTS Total": pd.Timestamp("2024-02-29"),
    "PRS Total": pd.Timestamp("2026-08-20"),
}

MODEL_VERSION = "v3_high_footfall_enhanced"

# MongoDB collections
HISTORICAL_COLLECTION = "historical_data"
FORECASTING_COLLECTION = "forecasting_data"
