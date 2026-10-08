import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np

from services.forecasting.data_loader import _get_sync_db, load_historical_data_sync, build_target_series
from services.forecasting.common import (
    CalendarFeatures, compute_holiday_ratio, compute_doy_seasonal_index_array,
    TARGET_TRANSFORMS, two_sided_asymmetric_metrics
)
from services.forecasting.features import compute_named_holiday_ratios, build_named_ratio_array, build_frame, recursive_forecast
from services.forecasting.modeling import get_model_configs, get_validation_cutoffs, run_backtest, metrics

# 1. Compare MongoDB forecasting_data predictions vs actuals for 2026
db = _get_sync_db()
if db is not None:
    f_docs = list(db.forecasting_data.find({'date': {'$gte': '2026-01-01', '$lte': '2026-09-17'}}).sort('date', 1))
    if f_docs:
        f_df = pd.DataFrame(f_docs)
        f_df['dt'] = pd.to_datetime(f_df['date'])
        f_df['month'] = f_df['dt'].dt.month
        
        print("=== 2026 IN-DB FORECAST VS ACTUAL PERFORMANCE (Jan - Sep 17) ===")
        for target, pred_col, act_col in [
            ('UTS Total', 'uts_total_predicted', 'uts_total_actual'),
            ('PRS Total', 'prs_total_predicted', 'prs_total_actual'),
            ('Overall Total', 'overall_total_predicted', 'overall_total_actual'),
        ]:
            valid = f_df.dropna(subset=[act_col, pred_col])
            m = metrics(valid[act_col], valid[pred_col])
            print(f"\nTarget: {target} (Overall 2026 to date):")
            print(f"  MAE: {m['MAE']:.1f} | RMSE: {m['RMSE']:.1f} | MAPE: {m['MAPE']:.2f}% | Acc: {m['validation_accuracy']:.2f}% | R2: {m['R2']:.3f}")
            
            print("  By Month Breakdown:")
            for mth, grp in valid.groupby('month'):
                sub_m = metrics(grp[act_col], grp[pred_col])
                mean_act = grp[act_col].mean()
                mean_pred = grp[pred_col].mean()
                print(f"    Month {mth:02d}: ActMean={mean_act:6.0f}, PredMean={mean_pred:6.0f}, MAE={sub_m['MAE']:5.0f}, MAPE={sub_m['MAPE']:5.2f}%, Acc={sub_m['validation_accuracy']:5.2f}%")

# 2. Check full backtesting across folds
print("\n" + "="*70)
print("=== RUNNING DETAILED MODEL BENCHMARK ON HISTORICAL DATA ===")
print("="*70)
df = load_historical_data_sync()
print(f"Historical records: {len(df)}, from {df['Date'].min().date()} to {df['Date'].max().date()}")

calendar_end = max(pd.Timestamp('2026-12-31'), pd.Timestamp(df['Date'].max()))
cf_hist = CalendarFeatures(df, calendar_end)
base = cf_hist.base_frame()
idx_of_date = cf_hist.idx_of_date

print("\nValidation cutoffs detected:", get_validation_cutoffs(df))

for target in ['UTS Total', 'PRS Total']:
    print(f"\n--- Backtesting for {target} ---")
    values_actual_full, values_for_features_full, values_actual_clean = build_target_series(
        df, target, idx_of_date, cf_hist.n)
    
    winner, members, avg, fr = run_backtest(
        df, cf_hist, base, target, idx_of_date, cf_hist.n,
        values_for_features_full, values_actual_full, values_actual_clean, verbose=True
    )
    print(f"\nWinner for {target}: {winner} (Members: {members})")
    print("\nSummary metrics table:")
    print(avg[['model', 'MAE', 'RMSE', 'MAPE', 'R2', 'validation_accuracy']].sort_values('MAE').to_string(index=False))
