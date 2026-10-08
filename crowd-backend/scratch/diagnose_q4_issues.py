import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np

from services.forecasting.data_loader import load_historical_data_sync
from services.forecasting.common import (
    CalendarFeatures, compute_holiday_ratio, compute_doy_seasonal_index_array,
    normalize_festival_name, MAJOR_TRAVEL_FESTIVALS
)
from services.forecasting.features import compute_historical_context_features, compute_named_holiday_ratios

df = load_historical_data_sync()
cutoff_date = pd.Timestamp(df['Date'].max())

for target in ['UTS Total', 'PRS Total']:
    m_dow, m_arr = compute_historical_context_features(df, target, pd.date_range('2026-10-01', '2026-12-31'), cutoff_date)
    print(f"\n{target} Historical Context in Q4 (Unweighted mean across 2022-2025):")
    print(f"  Oct Mean: {np.mean(m_arr[:31]):.0f}")
    print(f"  Nov Mean: {np.mean(m_arr[31:61]):.0f}")
    print(f"  Dec Mean: {np.mean(m_arr[61:]):.0f}")

# Check what recent years (2025 and 2026) actually had:
print("\nRecent Year Monthly Averages:")
for yr in [2024, 2025, 2026]:
    sub = df[df['Date'].dt.year == yr]
    q4_sub = sub[sub['Date'].dt.month.isin([9, 10, 11, 12])]
    print(f"Year {yr}:")
    for mth in [9, 10, 11, 12]:
        m_df = q4_sub[q4_sub['Date'].dt.month == mth]
        if len(m_df):
            print(f"  Month {mth:02d}: UTS={m_df['UTS Total'].mean():.0f}, PRS={m_df['PRS Total'].mean():.0f}, Overall={m_df['Overall Total'].mean():.0f}")
