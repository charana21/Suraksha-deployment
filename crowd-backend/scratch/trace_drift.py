import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np

from services.forecasting.data_loader import load_historical_data_sync, build_target_series
from services.forecasting.common import (
    CalendarFeatures, compute_holiday_ratio, compute_doy_seasonal_index_array,
    TARGET_TRANSFORMS, CALENDAR_FEATURES, ALL_FEATURES_BLIND as FEATURES
)
from services.forecasting.features import build_frame, target_features_for_index
from xgboost import XGBRegressor

df = load_historical_data_sync()
latest_history = pd.Timestamp(df['Date'].max())
cf = CalendarFeatures(df, pd.Timestamp('2026-12-31'))
base = cf.base_frame()
idx_of_date = cf.idx_of_date

# Recency context
def get_recency_context(df, target, full_dates, cutoff):
    hist = df[df['Date'] <= cutoff].copy()
    hist['Month'] = hist['Date'].dt.month
    hist['DOW'] = hist['Date'].dt.dayofweek
    max_yr = hist['Date'].dt.year.max()
    hist['W'] = np.exp(0.65 * (hist['Date'].dt.year - max_yr))
    
    m_dow_map = {}
    for (m, dow), grp in hist.groupby(['Month', 'DOW']):
        m_dow_map[(m, dow)] = np.average(grp[target], weights=grp['W'])
        
    m_map = {}
    for m, grp in hist.groupby('Month'):
        m_map[m] = np.average(grp[target], weights=grp['W'])
        
    g_mean = np.average(hist[target], weights=hist['W'])
    m_dow_arr = np.array([m_dow_map.get((d.month, d.dayofweek), m_map.get(d.month, g_mean)) for d in full_dates])
    m_arr = np.array([m_map.get(d.month, g_mean) for d in full_dates])
    return m_dow_arr, m_arr

target = 'UTS Total'
v_act, v_feat, v_clean = build_target_series(df, target, idx_of_date, cf.n)
cutoff_idx = idx_of_date[latest_history]
holiday_ratio = compute_holiday_ratio(v_feat, np.where(cf.is_holiday.to_numpy() == 1)[0])
seasonal_arr = compute_doy_seasonal_index_array(df, target, cf.full_dates, lock_year=latest_history.year)
hist_mdow, hist_m = get_recency_context(df, target, cf.full_dates, latest_history)
named_ratio_arr = np.ones(cf.n)

train_idx = [i for i in range(365, cutoff_idx + 1) if not np.isnan(v_clean[i])]
X_train = build_frame(v_feat, train_idx, cf, base, holiday_ratio, seasonal_arr, named_ratio_arr,
                      hist_mdow_arr=hist_mdow, hist_m_arr=hist_m)
y_train = v_clean[train_idx]

fwd, inv = TARGET_TRANSFORMS['log']
m = XGBRegressor(n_estimators=450, max_depth=5, learning_rate=0.03, subsample=0.85, colsample_bytree=0.85, random_state=42, n_jobs=-1, verbosity=0)
m.fit(X_train, fwd(y_train))

# Check feature importances!
imp = pd.Series(m.feature_importances_, index=FEATURES).sort_values(ascending=False)
print("TOP 15 FEATURE IMPORTANCES FOR UTS:")
print(imp.head(15))

# Check recursive forecast day by day for Oct 1, Nov 1, Dec 1
fut_idx = list(range(cutoff_idx + 1, idx_of_date[pd.Timestamp('2026-12-31')] + 1))
values = v_feat.copy()
log_rows = []
for i in fut_idx:
    tfeat = target_features_for_index(values, i, cf, holiday_ratio, seasonal_arr, hist_mdow, hist_m)
    cfeat = base.iloc[i][CALENDAR_FEATURES].to_dict()
    nr = named_ratio_arr[i]
    r7 = tfeat['roll_mean_7'] if not np.isnan(tfeat['roll_mean_7']) else tfeat['roll_mean_30']
    r30 = tfeat['roll_mean_30'] if not np.isnan(tfeat['roll_mean_30']) else r7
    base_anchor = r30 if not np.isnan(r30) else 10000.0
    tfeat['named_holiday_ratio'] = nr
    tfeat['named_holiday_adjusted_baseline'] = base_anchor * nr
    row = {**cfeat, **tfeat}
    X = pd.DataFrame([row])[FEATURES]
    p = max(float(inv(float(m.predict(X)[0]))), 0.0)
    values[i] = p
    
    d = cf.full_dates[i]
    if d.day in [1, 15] or (d.month == 10 and d.day in [18, 19, 20, 21]) or (d.month == 11 and d.day in [7, 8, 9, 14, 24]):
        log_rows.append({
            'date': d.strftime('%Y-%m-%d'),
            'pred': round(p),
            'lag_1': round(tfeat['lag_1']),
            'lag_7': round(tfeat['lag_7']),
            'roll_7': round(tfeat['roll_mean_7']),
            'roll_30': round(tfeat['roll_mean_30']),
            'hist_m': round(tfeat['hist_month_mean']),
            'hist_mdow': round(tfeat['hist_month_dow_mean']),
            'doy_idx': round(tfeat['doy_seasonal_index'], 3),
        })

print("\nRECURSIVE TRACE FOR SELECTED DATES:")
print(pd.DataFrame(log_rows).to_string(index=False))
