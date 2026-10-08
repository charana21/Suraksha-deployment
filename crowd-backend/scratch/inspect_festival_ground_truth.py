import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np

from services.forecasting.data_loader import load_historical_data_sync
from services.forecasting.common import (
    CalendarFeatures, compute_holiday_ratio, compute_doy_seasonal_index_array,
    normalize_festival_name, MAJOR_TRAVEL_FESTIVALS
)
from services.forecasting.features import compute_named_holiday_ratios, build_named_ratio_array

df = load_historical_data_sync()
print(f"Loaded {len(df)} historical rows from {df['Date'].min().date()} to {df['Date'].max().date()}")

# Check all festivals around Dussehra, Diwali, etc. in 2022, 2023, 2024, 2025
cf = CalendarFeatures(df, pd.Timestamp('2026-12-31'))
base = cf.base_frame()

print("\n=== HISTORICAL DUSSEHRA TRAVEL WINDOWS (2022 - 2025) ===")
# In 2022: Oct 5
# In 2023: Oct 24
# In 2024: Oct 12
# In 2025: Oct 2
dussehra_dates = ['2022-10-05', '2023-10-24', '2024-10-12', '2025-10-02']
for d_str in dussehra_dates:
    dt = pd.Timestamp(d_str)
    sub = df[(df['Date'] >= dt - pd.Timedelta(days=5)) & (df['Date'] <= dt + pd.Timedelta(days=5))].copy()
    sub['DOW'] = sub['Date'].dt.day_name()
    sub['DaysFromFest'] = (sub['Date'] - dt).dt.days
    print(f"\n--- Around {d_str} (Dussehra is Day 0) ---")
    print(sub[['Date', 'DOW', 'DaysFromFest', 'UTS Total', 'PRS Total', 'Overall Total']].to_string(index=False))

print("\n=== HISTORICAL DIWALI TRAVEL WINDOWS (2022 - 2025) ===")
# 2022: Oct 24
# 2023: Nov 12
# 2024: Nov 1
# 2025: Oct 20
diwali_dates = ['2022-10-24', '2023-11-12', '2024-11-01', '2025-10-20']
for d_str in diwali_dates:
    dt = pd.Timestamp(d_str)
    sub = df[(df['Date'] >= dt - pd.Timedelta(days=5)) & (df['Date'] <= dt + pd.Timedelta(days=5))].copy()
    sub['DOW'] = sub['Date'].dt.day_name()
    sub['DaysFromFest'] = (sub['Date'] - dt).dt.days
    print(f"\n--- Around {d_str} (Diwali is Day 0) ---")
    print(sub[['Date', 'DOW', 'DaysFromFest', 'UTS Total', 'PRS Total', 'Overall Total']].to_string(index=False))

print("\n=== DECEMBER HISTORICAL PATTERNS (2022, 2023, 2024, 2025) ===")
df['Month'] = df['Date'].dt.month
df['Year'] = df['Date'].dt.year
dec_summary = df[df['Month'] == 12].groupby('Year')[['UTS Total', 'PRS Total', 'Overall Total']].agg(['mean', 'min', 'max'])
print(dec_summary)

all_month_summary = df.groupby(['Year', 'Month'])['Overall Total'].mean().unstack(level=1)
print("\n=== HISTORICAL MONTHLY MEANS ACROSS YEARS ===")
print(all_month_summary.round(0))
