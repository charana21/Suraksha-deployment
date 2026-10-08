import os, sys, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import numpy as np

from services.forecasting.data_loader import _get_sync_db
from services.forecasting.modeling import metrics
from services.footfallinsights import FootfallInsightsService
from db.mongodb import MongoDB, connect_to_mongo
from config.config import get_settings

async def main():
    print("=" * 80)
    print("VERIFYING 2026 UTS & PRS FORECASTING RESULTS (ALL 12 MONTHS)")
    print("=" * 80)

    # 1. Inspect MongoDB forecasting_data directly
    db = _get_sync_db()
    docs = list(db.forecasting_data.find({'date': {'$regex': '^2026-'}}).sort('date', 1))
    print(f"Total 2026 records found in forecasting_data: {len(docs)}")
    assert len(docs) == 365, f"Expected 365 records for 2026, found {len(docs)}"

    df = pd.DataFrame(docs)
    df['dt'] = pd.to_datetime(df['date'])
    df['month'] = df['dt'].dt.month

    # 2. In-sample accuracy on Jan 01 - Sep 17
    hist_mask = df['dt'] <= '2026-09-17'
    hist_df = df[hist_mask].copy()

    print("\n" + "-" * 80)
    print("IN-SAMPLE MODEL ACCURACY (2026-01-01 to 2026-09-17, 260 days)")
    print("-" * 80)
    for name, p_col, a_col in [
        ('UTS Total', 'uts_total_predicted', 'uts_total_actual'),
        ('PRS Total', 'prs_total_predicted', 'prs_total_actual'),
        ('Overall Total', 'overall_total_predicted', 'overall_total_actual'),
    ]:
        valid = hist_df.dropna(subset=[p_col, a_col])
        m = metrics(valid[a_col], valid[p_col])
        print(f"{name:15s}: MAE={m['MAE']:6.1f} | RMSE={m['RMSE']:6.1f} | MAPE={m['MAPE']:5.2f}% | Accuracy={m['validation_accuracy']:5.2f}% | R2={m['R2']:.4f}")

    # 3. Monthly breakdown across all 12 months (Jan - Dec 2026)
    print("\n" + "-" * 80)
    print("MONTHLY PREDICTIONS & ACTUALS FOR ALL 12 MONTHS OF 2026")
    print("-" * 80)

    month_rows = []
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for m in range(1, 13):
        m_df = df[df['month'] == m]
        days = len(m_df)
        uts_pred_mean = m_df['uts_total_predicted'].mean()
        uts_pred_sum = m_df['uts_total_predicted'].sum()
        prs_pred_mean = m_df['prs_total_predicted'].mean()
        prs_pred_sum = m_df['prs_total_predicted'].sum()
        overall_pred_mean = m_df['overall_total_predicted'].mean()
        overall_pred_sum = m_df['overall_total_predicted'].sum()

        uts_act_mean = m_df['uts_total_actual'].dropna().mean() if len(m_df['uts_total_actual'].dropna()) else np.nan
        prs_act_mean = m_df['prs_total_actual'].dropna().mean() if len(m_df['prs_total_actual'].dropna()) else np.nan
        overall_act_mean = m_df['overall_total_actual'].dropna().mean() if len(m_df['overall_total_actual'].dropna()) else np.nan

        blind_count = m_df['is_blind_forecast'].sum()

        month_rows.append({
            'Month': f"{m:02d} - {month_names[m-1]}",
            'Days': days,
            'Blind Days': blind_count,
            'UTS Pred Mean': round(uts_pred_mean),
            'UTS Act Mean': round(uts_act_mean) if not np.isnan(uts_act_mean) else '-',
            'PRS Pred Mean': round(prs_pred_mean),
            'PRS Act Mean': round(prs_act_mean) if not np.isnan(prs_act_mean) else '-',
            'Overall Mean': round(overall_pred_mean),
            'Overall Act Mean': round(overall_act_mean) if not np.isnan(overall_act_mean) else '-',
            'Monthly Footfall': f"{overall_pred_sum:,.0f}",
        })

    m_summary_df = pd.DataFrame(month_rows)
    print(m_summary_df.to_string(index=False))

    # Detailed Q4 Festivals & Alert Levels
    print("\n" + "-" * 80)
    print("OCTOBER 2026 KEY FESTIVALS & RUSH DATES")
    print("-" * 80)
    oct_q = df[(df['date'] >= '2026-10-15') & (df['date'] <= '2026-10-26')]
    print(oct_q[['date', 'day_of_week', 'uts_total_predicted', 'prs_total_predicted', 'overall_total_predicted', 'occasion_or_holiday']].to_string(index=False))

    print("\n" + "-" * 80)
    print("NOVEMBER 2026 KEY FESTIVALS & RUSH DATES")
    print("-" * 80)
    nov_q = df[(df['date'] >= '2026-11-06') & (df['date'] <= '2026-11-26')]
    print(nov_q[['date', 'day_of_week', 'uts_total_predicted', 'prs_total_predicted', 'overall_total_predicted', 'occasion_or_holiday']].to_string(index=False))

    print("\n" + "-" * 80)
    print("DECEMBER 2026 KEY FESTIVALS & YEAR-END")
    print("-" * 80)
    dec_q = df[(df['date'] >= '2026-12-20') & (df['date'] <= '2026-12-31')]
    print(dec_q[['date', 'day_of_week', 'uts_total_predicted', 'prs_total_predicted', 'overall_total_predicted', 'occasion_or_holiday']].to_string(index=False))
    print("\n" + "-" * 80)
    print("CHECKING DASHBOARD PAYLOAD VIA FootfallInsightsService")
    print("-" * 80)
    await connect_to_mongo(get_settings())
    await FootfallInsightsService.ensure_indexes()
    payload = await FootfallInsightsService.get_dashboard_payload(year=2026)

    print(f"Payload Year: {payload.get('year')}")
    print(f"Total Predicted UTS Footfall: {payload.get('totalUtsPredicted'):,}")
    print(f"Total Predicted PRS Footfall: {payload.get('totalPrsPredicted'):,}")
    print(f"Total Annual Scheduled Footfall: {payload.get('totalScheduledPax'):,}")
    print(f"Live Today Passengers: {payload.get('livePax'):,}")

    cards = payload.get('months', [])
    print(f"Total Months returned in payload: {len(cards)}")
    for i, c in enumerate(cards):
        print(f"  {c.get('name', 'Month'):12s}: TotalPax={c.get('totalPax', 0):10,d} | ScheduledPax={c.get('totalScheduledPax', 0):10,d} | DaysCount={len(c.get('days', []))}")

    print("\n=== VERIFICATION COMPLETE: ALL CHECKS PASSED ===")

if __name__ == '__main__':
    asyncio.run(main())
