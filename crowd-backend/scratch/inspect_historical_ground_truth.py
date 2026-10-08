import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np
from services.forecasting.data_loader import load_historical_data_sync, _get_sync_db

df = load_historical_data_sync()
df['Year'] = df['Date'].dt.year
df['Month'] = df['Date'].dt.month
df['DOW'] = df['Date'].dt.day_name()

print("="*80)
print("GROUND TRUTH HISTORICAL MONTHLY MEANS (UTS Total)")
print("="*80)
uts_piv = df.pivot_table(index='Month', columns='Year', values='UTS Total', aggfunc='mean')
print(uts_piv.round(0))

print("\n" + "="*80)
print("GROUND TRUTH HISTORICAL MONTHLY MEANS (PRS Total)")
print("="*80)
prs_piv = df.pivot_table(index='Month', columns='Year', values='PRS Total', aggfunc='mean')
print(prs_piv.round(0))

print("\n" + "="*80)
print("GROUND TRUTH HISTORICAL MONTHLY MEANS (Overall Total)")
print("="*80)
tot_piv = df.pivot_table(index='Month', columns='Year', values='Overall Total', aggfunc='mean')
print(tot_piv.round(0))

# Now compare with 2026 in DB
db = _get_sync_db()
if db is not None:
    f_docs = list(db.forecasting_data.find({'date': {'$gte': '2026-01-01', '$lte': '2026-12-31'}}).sort('date', 1))
    f_df = pd.DataFrame(f_docs)
    f_df['dt'] = pd.to_datetime(f_df['date'])
    f_df['Month'] = f_df['dt'].dt.month
    
    print("\n" + "="*80)
    print("2026 FORECAST IN DB VS 2025 ACTUALS COMPARISON")
    print("="*80)
    f_m = f_df.groupby('Month')[['uts_total_predicted', 'prs_total_predicted', 'overall_total_predicted']].mean()
    comp = pd.DataFrame({
        'UTS 2025 Act': uts_piv[2025],
        'UTS 2026 Pred': f_m['uts_total_predicted'],
        'UTS Diff': f_m['uts_total_predicted'] - uts_piv[2025],
        'UTS %Chg': ((f_m['uts_total_predicted'] - uts_piv[2025]) / uts_piv[2025] * 100).round(1),
        'PRS 2025 Act': prs_piv[2025],
        'PRS 2026 Pred': f_m['prs_total_predicted'],
        'PRS Diff': f_m['prs_total_predicted'] - prs_piv[2025],
        'PRS %Chg': ((f_m['prs_total_predicted'] - prs_piv[2025]) / prs_piv[2025] * 100).round(1),
        'Tot 2025 Act': tot_piv[2025],
        'Tot 2026 Pred': f_m['overall_total_predicted'],
        'Tot Diff': f_m['overall_total_predicted'] - tot_piv[2025],
        'Tot %Chg': ((f_m['overall_total_predicted'] - tot_piv[2025]) / tot_piv[2025] * 100).round(1),
    })
    print(comp.to_string())

# Also check 2026 actuals up to Sep 17
print("\n" + "="*80)
print("2026 ACTUALS (Jan-Sep 17) VS 2025 ACTUALS (Same period YoY growth)")
print("="*80)
y26 = df[df['Year'] == 2026].groupby('Month')[['UTS Total', 'PRS Total', 'Overall Total']].mean()
y25 = df[df['Year'] == 2025].groupby('Month')[['UTS Total', 'PRS Total', 'Overall Total']].mean()
yoy_uts = ((y26['UTS Total'] - y25['UTS Total']) / y25['UTS Total'] * 100).round(2)
yoy_prs = ((y26['PRS Total'] - y25['PRS Total']) / y25['PRS Total'] * 100).round(2)
yoy_tot = ((y26['Overall Total'] - y25['Overall Total']) / y25['Overall Total'] * 100).round(2)
yoy_df = pd.DataFrame({
    'UTS 2025': y25['UTS Total'].loc[y26.index],
    'UTS 2026': y26['UTS Total'],
    'UTS YoY %': yoy_uts,
    'PRS 2025': y25['PRS Total'].loc[y26.index],
    'PRS 2026': y26['PRS Total'],
    'PRS YoY %': yoy_prs,
    'Tot 2025': y25['Overall Total'].loc[y26.index],
    'Tot 2026': y26['Overall Total'],
    'Tot YoY %': yoy_tot,
})
print(yoy_df.to_string())
