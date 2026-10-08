"""
Forecasting engine for UTS & PRS prediction generation.
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any

from . import forecasting_config as config
from .common import (
    CalendarFeatures,
    compute_holiday_ratio,
    compute_doy_seasonal_index_array,
    TARGET_TRANSFORMS
)
from .features import (
    compute_named_holiday_ratios,
    build_named_ratio_array,
    compute_historical_context_features,
    build_frame,
    recursive_forecast
)
from .modeling import get_model_configs, EnsembleModel, IDENTITY
from .data_loader import build_target_series

logger = logging.getLogger(__name__)


def _fit_single(name: str, X_train: pd.DataFrame, y_train_raw: np.ndarray, model_configs: Dict[str, Any]):
    model_proto, transform_name = model_configs[name]
    fwd, inv = TARGET_TRANSFORMS[transform_name]
    model = type(model_proto)(**model_proto.get_params())
    model.fit(X_train, fwd(y_train_raw))
    return model, inv


def _fit_model(winner_name: str, X_train: pd.DataFrame, y_train_raw: np.ndarray, winner_members: Optional[List[str]] = None):
    model_configs = dict((n, (m, t)) for n, m, t in get_model_configs())
    if winner_members:
        fitted = [_fit_single(name, X_train, y_train_raw, model_configs) for name in winner_members if name in model_configs]
        if fitted:
            return EnsembleModel(fitted), IDENTITY
    
    if winner_name not in model_configs:
        winner_name = "GradientBoosting_raw"
    return _fit_single(winner_name, X_train, y_train_raw, model_configs)


def generate_target_forecast(df: pd.DataFrame, target: str, winner_name: str, winner_members: Optional[List[str]] = None):
    """
    Trains the winning model for `target` on all available history and returns
    a DataFrame for the complete year 2026 [2026-01-01 to 2026-12-31] with predictions, actuals,
    and Python `holidays`-sourced festivals.
    """
    forecast_start = pd.Timestamp(config.FORECAST_START)
    forecast_end = pd.Timestamp(config.FORECAST_END)

    latest_history = pd.Timestamp(df['Date'].max()).normalize()
    calendar_end = max(forecast_end, latest_history)

    cf = CalendarFeatures(df, calendar_end)
    base = cf.base_frame()
    idx_of_date = cf.idx_of_date

    values_actual_full, values_for_features_full, values_actual_clean = build_target_series(
        df, target, idx_of_date, cf.n)

    cutoff_idx = idx_of_date[latest_history]

    # Holiday features
    hol_idx_all = np.where(cf.is_holiday.to_numpy() == 1)[0]
    hol_idx_known = hol_idx_all[hol_idx_all <= cutoff_idx]
    holiday_ratio = compute_holiday_ratio(values_for_features_full, hol_idx_known)
    seasonal_arr = compute_doy_seasonal_index_array(df, target, cf.full_dates, lock_year=latest_history.year)
    on_med, before_med, after_med, p_on, p_bef, p_aft = compute_named_holiday_ratios(
        values_for_features_full, cf, cutoff_idx)
    named_ratio_arr = build_named_ratio_array(cf, on_med, before_med, after_med, p_on, p_bef, p_aft)
    hist_mdow_arr, hist_m_arr = compute_historical_context_features(
        df, target, cf.full_dates, latest_history
    )

    # Train model on historical actuals
    train_start = min(config.MIN_TRAIN_START_IDX, cutoff_idx)
    train_idx_raw = list(range(train_start, cutoff_idx + 1))
    train_idx = [i for i in train_idx_raw if not np.isnan(values_actual_clean[i])]
    if not train_idx:
        raise ValueError(f"No training observations available for {target}")

    X_train = build_frame(values_for_features_full, train_idx, cf, base, holiday_ratio,
                          seasonal_arr, named_ratio_arr, hist_mdow_arr=hist_mdow_arr, hist_m_arr=hist_m_arr)
    y_train = values_actual_clean[train_idx]
    model, inv = _fit_model(winner_name, X_train, y_train, winner_members)

    year_start_idx = idx_of_date[forecast_start]
    year_end_idx = idx_of_date[forecast_end]
    hist_end_idx = min(cutoff_idx, year_end_idx)

    preds_map = {}
    is_blind_map = {}

    # 1. Historical dates in 2026 (model predictions alongside actuals)
    if year_start_idx <= hist_end_idx:
        hist_idx = list(range(year_start_idx, hist_end_idx + 1))
        X_hist = build_frame(values_for_features_full, hist_idx, cf, base, holiday_ratio,
                             seasonal_arr, named_ratio_arr, hist_mdow_arr=hist_mdow_arr, hist_m_arr=hist_m_arr)
        raw_preds_hist = model.predict(X_hist)
        for i, p in zip(hist_idx, raw_preds_hist):
            preds_map[i] = max(float(inv(p)), 0.0)
            is_blind_map[i] = False

    # 2. Future dates in 2026 (recursive multi-step forecasting)
    if hist_end_idx < year_end_idx:
        future_idx = list(range(hist_end_idx + 1, year_end_idx + 1))
        preds_future = recursive_forecast(model, values_for_features_full, future_idx, cf, base,
                                          holiday_ratio, inv, seasonal_arr, named_ratio_arr,
                                          hist_mdow_arr=hist_mdow_arr, hist_m_arr=hist_m_arr,
                                          target_name=target)
        for i in future_idx:
            preds_map[i] = preds_future[i]
            is_blind_map[i] = True

    # Assemble all 2026 rows
    rows = []
    for i in range(year_start_idx, year_end_idx + 1):
        d = base['Date'].iloc[i]
        is_blind = is_blind_map.get(i, True)
        act = values_actual_full[i] if not is_blind else np.nan
        rows.append(dict(
            Date=d,
            prediction=preds_map.get(i, 0.0),
            actual=act,
            is_blind_forecast=is_blind
        ))

    out = pd.DataFrame(rows)
    out['target'] = target

    # Build a string-keyed dict from hol_name Series for reliable lookups
    # (Series.get() with Timestamp keys can be unreliable; use string keys instead)
    hol_name_dict = {
        d.strftime('%Y-%m-%d'): name
        for d, name in cf.hol_name.items()
        if name and str(name).strip()
    }
    out['holiday_name'] = out['Date'].apply(
        lambda d: hol_name_dict.get(d.strftime('%Y-%m-%d'), '')
    )
    return out, cf


def build_full_forecast_table(df: pd.DataFrame, winners: Dict[str, str],
                              winner_members: Optional[Dict[str, List[str]]] = None) -> pd.DataFrame:
    """
    Assembles complete wide prediction table for UTS and PRS for all 12 months of 2026.
    """
    winner_members = winner_members or {}
    per_target = {}
    for target in config.TARGETS:
        out, _ = generate_target_forecast(df, target, winners[target], winner_members.get(target))
        per_target[target] = out

    uts = per_target['UTS Total']
    prs = per_target['PRS Total']
    merged = uts.merge(prs, on='Date', suffixes=('_uts', '_prs'))

    wide = pd.DataFrame({
        'Date': merged['Date'],
        'Day of Week': merged['Date'].dt.day_name(),
        'UTS Total (Predicted)': merged['prediction_uts'].round(0).astype(int),
        'PRS Total (Predicted)': merged['prediction_prs'].round(0).astype(int),
        'UTS Total (Actual)': merged['actual_uts'],
        'PRS Total (Actual)': merged['actual_prs'],
        'Occasion / Public Holiday': merged['holiday_name_uts'].fillna(''),
        'Is Blind Forecast': merged['is_blind_forecast_uts'],
    })
    wide['Overall Total (Predicted)'] = wide['UTS Total (Predicted)'] + wide['PRS Total (Predicted)']

    overall_actuals = []
    for u, p in zip(wide['UTS Total (Actual)'], wide['PRS Total (Actual)']):
        if pd.notna(u) and pd.notna(p):
            overall_actuals.append(int(round(u + p)))
        elif pd.notna(u):
            overall_actuals.append(int(round(u)))
        elif pd.notna(p):
            overall_actuals.append(int(round(p)))
        else:
            overall_actuals.append(np.nan)
    wide['Overall Total (Actual)'] = overall_actuals
    wide = wide.sort_values('Date').reset_index(drop=True)

    wide['Note'] = ''
    bad_prs_date = config.BAD_DAY_BY_TARGET.get('PRS Total')
    if bad_prs_date:
        bad_mask = wide['Date'] == bad_prs_date
        wide.loc[bad_mask, 'Note'] = (
            'PRS sensor outage on this date; excluded from model training, shown here as-recorded'
        )
    return wide
