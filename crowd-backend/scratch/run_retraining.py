import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from services.forecasting.runner import ForecastingRunner

print("=== STARTING FULL RETRAINING AND FORECAST GENERATION ===")
res = ForecastingRunner.run_pipeline_sync(skip_backtest=False)

print("\n=== PIPELINE RESULTS ===")
print("Status:", res["status"])
print("Winners:", res["winners"])
print("Historical rows used:", res["historical_rows"])

# Query and inspect MongoDB forecasting_data for Oct, Nov, Dec 2026
from services.forecasting.data_loader import _get_sync_db
db = _get_sync_db()
docs = list(db.forecasting_data.find({'date': {'$gte': '2026-10-01', '$lte': '2026-12-31'}}).sort('date', 1))
df = pd.DataFrame(docs)

print("\n=== UPDATED FORECAST IN DB (2026 Oct-Dec) ===")
print(df[['date', 'day_of_week', 'uts_total_predicted', 'prs_total_predicted', 'overall_total_predicted', 'occasion_or_holiday']].head(35).to_string())

print("\n=== UPDATED Q4 STATS BY MONTH ===")
df['month'] = pd.to_datetime(df['date']).dt.month
print(df.groupby('month')[['uts_total_predicted', 'prs_total_predicted', 'overall_total_predicted']].agg(['mean', 'min', 'max']))

# Color distribution in Q4 according to UI thresholds
# L1 Normal: < 140,000 (Green)
# L2 Alert: 140,000 to 160,000 (Orange)
# L3 Emergency: > 160,000 (Red)
def get_color(pax):
    if pax < 140000:
        return 'Green (Normal <140k)'
    elif pax <= 160000:
        return 'Orange (Alert 140k-160k)'
    else:
        return 'Red (Emergency >160k)'

df['color'] = df['overall_total_predicted'].apply(get_color)
print("\n=== Q4 DAY COLOR DISTRIBUTION ===")
print(df['color'].value_counts())
