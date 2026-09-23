import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from services.forecasting.data_loader import _get_sync_db, load_historical_data_sync

db = _get_sync_db()

# Historical data stats
hist_df = load_historical_data_sync()
print("=== HISTORICAL DATA OVERVIEW ===")
print("Date range:", hist_df['Date'].min(), "to", hist_df['Date'].max())
print("Total rows:", len(hist_df))
print(hist_df[['UTS Total', 'PRS Total', 'Overall Total']].describe())

# Check recent months actuals (e.g. 2025 Q4 and 2026 Q1-Q3)
hist_df['Year'] = pd.to_datetime(hist_df['Date']).dt.year
hist_df['Month'] = pd.to_datetime(hist_df['Date']).dt.month
hist_df['DOW'] = pd.to_datetime(hist_df['Date']).dt.day_name()

print("\n=== HISTORICAL MONTHLY MEANS (UTS, PRS, Overall) ===")
monthly = hist_df.groupby(['Year', 'Month'])[['UTS Total', 'PRS Total', 'Overall Total']].mean()
print(monthly.tail(24))

print("\n=== HISTORICAL DAY OF WEEK MEANS (Overall) ===")
print(hist_df.groupby('DOW')['Overall Total'].agg(['mean', 'median', 'std']))

# Forecasting data in DB
docs = list(db.forecasting_data.find({}).sort('date', 1))
f_df = pd.DataFrame(docs)
f_df['dt'] = pd.to_datetime(f_df['date'])
f_df['year'] = f_df['dt'].dt.year
f_df['month'] = f_df['dt'].dt.month

print("\n=== CURRENT FORECAST IN DB (2026 Oct-Dec) ===")
q4_2026 = f_df[f_df['date'] >= '2026-10-01']
print(q4_2026[['date', 'day_of_week', 'uts_total_predicted', 'prs_total_predicted', 'overall_total_predicted', 'occasion_or_holiday']].to_string())

print("\n=== Q4 FORECAST STATS BY MONTH ===")
print(q4_2026.groupby('month')[['uts_total_predicted', 'prs_total_predicted', 'overall_total_predicted']].agg(['mean', 'min', 'max']))
