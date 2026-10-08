import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
from services.forecasting.data_loader import _get_sync_db

# 1. Inspect CSV
csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reference_data", "historical_data-march22-august26.csv")
if os.path.exists(csv_path):
    df_csv = pd.read_csv(csv_path)
    print("=== CSV INSPECTION ===")
    print("CSV shape:", df_csv.shape)
    print("CSV Columns:", df_csv.columns.tolist())
    print("CSV Date min:", df_csv['Date'].min(), "max:", df_csv['Date'].max())
    print(df_csv.tail(5))
else:
    print("CSV not found at", csv_path)

# 2. Inspect MongoDB
db = _get_sync_db()
if db is not None:
    h_count = db.historical_data.count_documents({})
    f_count = db.forecasting_data.count_documents({})
    print(f"\n=== MONGODB INSPECTION ===")
    print(f"historical_data count: {h_count}")
    print(f"forecasting_data count: {f_count}")
    
    first_h = db.historical_data.find_one({}, sort=[('date', 1)])
    last_h = db.historical_data.find_one({}, sort=[('date', -1)])
    print(f"historical_data min date: {first_h.get('date') if first_h else None}, max date: {last_h.get('date') if last_h else None}")
    
    first_f = db.forecasting_data.find_one({}, sort=[('date', 1)])
    last_f = db.forecasting_data.find_one({}, sort=[('date', -1)])
    print(f"forecasting_data min date: {first_f.get('date') if first_f else None}, max date: {last_f.get('date') if last_f else None}")
    
    # Check 2026 forecast samples
    f_2026 = list(db.forecasting_data.find({'date': {'$gte': '2026-01-01', '$lte': '2026-12-31'}}).sort('date', 1))
    if f_2026:
        df_f = pd.DataFrame(f_2026)
        print(f"\nTotal 2026 forecast rows: {len(df_f)}")
        print("Columns in forecasting_data:", df_f.columns.tolist())
        df_f['month'] = pd.to_datetime(df_f['date']).dt.month
        print("\nMonthly forecast summary in DB:")
        print(df_f.groupby('month')[['uts_total_predicted', 'prs_total_predicted', 'overall_total_predicted']].agg(['mean', 'min', 'max']))
else:
    print("Could not connect to MongoDB")
