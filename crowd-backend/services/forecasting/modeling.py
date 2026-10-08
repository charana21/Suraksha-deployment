"""
Model candidates, accuracy metrics, and fold-based backtesting model selection.
"""
import time
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, HistGradientBoostingRegressor

logger = logging.getLogger(__name__)

# Optional XGBoost and LightGBM imports with graceful fallbacks
try:
    from xgboost import XGBRegressor
    HAS_XGBOOST = True
except ImportError:
    XGBRegressor = None
    HAS_XGBOOST = False

try:
    from lightgbm import LGBMRegressor
    HAS_LIGHTGBM = True
except ImportError:
    LGBMRegressor = None
    HAS_LIGHTGBM = False

from . import forecasting_config as config
from .common import (
    compute_holiday_ratio,
    TARGET_TRANSFORMS,
    compute_doy_seasonal_index_array,
    two_sided_asymmetric_metrics
)
from .features import (
    compute_named_holiday_ratios,
    build_named_ratio_array,
    compute_historical_context_features,
    build_frame,
    recursive_forecast
)

IDENTITY = lambda y: np.asarray(y, dtype=float)


class EnsembleModel:
    """Wraps several fitted (model, inverse_transform_fn) pairs and averages their predictions."""

    def __init__(self, members):
        self.members = members

    def predict(self, X):
        preds = [inv(np.asarray(m.predict(X), dtype=float)) for m, inv in self.members]
        return np.mean(preds, axis=0)


def get_validation_cutoffs(df: pd.DataFrame):
    """Return every completed Aug-Dec validation season present in history.

    The original three cutoffs are retained for the bundled data.  As new
    years are loaded, completed years are appended automatically so model
    selection is based on all available validation history.
    """
    latest_date = pd.Timestamp(df['Date'].max()).normalize()
    earliest_cutoff = pd.Timestamp(df['Date'].min()).normalize() + pd.Timedelta(
        days=config.MIN_TRAIN_START_IDX
    )
    cutoffs = []
    for year in range(int(df['Date'].min().year), latest_date.year + 1):
        cutoff = pd.Timestamp(f'{year}-08-25')
        validation_end = pd.Timestamp(f'{year}-12-31')
        if cutoff >= earliest_cutoff and validation_end <= latest_date:
            cutoffs.append(cutoff.strftime('%Y-%m-%d'))
    return cutoffs or list(config.FOLD_CUTOFFS)


def get_model_configs():
    """Returns list of (name, estimator_prototype, target_transform_name)."""
    configs = []

    # High-performance gradient boosters with parallel execution
    if HAS_XGBOOST and XGBRegressor is not None:
        configs.extend([
            ('XGBoost_log', XGBRegressor(
                n_estimators=450, max_depth=5, learning_rate=0.03,
                subsample=0.85, colsample_bytree=0.85, random_state=42,
                verbosity=0, n_jobs=-1), 'log'),
            ('XGBoost_raw', XGBRegressor(
                n_estimators=400, max_depth=4, learning_rate=0.04,
                subsample=0.85, colsample_bytree=0.85, random_state=42,
                verbosity=0, n_jobs=-1), 'raw'),
        ])

    if HAS_LIGHTGBM and LGBMRegressor is not None:
        configs.extend([
            ('LightGBM_log', LGBMRegressor(
                n_estimators=450, max_depth=5, learning_rate=0.03,
                subsample=0.85, colsample_bytree=0.85, random_state=42,
                verbose=-1, n_jobs=-1), 'log'),
            ('LightGBM_raw', LGBMRegressor(
                n_estimators=400, max_depth=4, learning_rate=0.04,
                subsample=0.85, colsample_bytree=0.85, random_state=42,
                verbose=-1, n_jobs=-1), 'raw'),
        ])

    configs.extend([
        ('HistGBM_log', HistGradientBoostingRegressor(
            max_iter=350, max_depth=5, learning_rate=0.03, random_state=42), 'log'),
        ('HistGBM_raw', HistGradientBoostingRegressor(
            max_iter=350, max_depth=4, learning_rate=0.04, random_state=42), 'raw'),
        ('RandomForest_log', RandomForestRegressor(
            n_estimators=300, max_depth=8, min_samples_leaf=3, random_state=42, n_jobs=-1), 'log'),
        ('RandomForest_raw', RandomForestRegressor(
            n_estimators=300, max_depth=8, min_samples_leaf=3, random_state=42, n_jobs=-1), 'raw'),
    ])

    return configs


def metrics(y_true, y_pred):
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    validation_accuracy = max(0.0, 100.0 - mape)
    return dict(MAE=mae, RMSE=rmse, MAPE=mape, R2=r2,
                validation_accuracy=validation_accuracy)


def select_winner(avg_df):
    """Select the model that maximizes accuracy (minimizes MAE and MAPE) without quantile bias."""
    df_eval = avg_df.copy()
    sort_cols = [c for c in ['validation_accuracy', 'MAE', 'RMSE', 'MAPE'] if c in df_eval.columns]
    ascending_flags = [c != 'validation_accuracy' for c in sort_cols]
    ranked = df_eval.sort_values(
        sort_cols,
        ascending=ascending_flags,
    )
    return ranked.iloc[0]['model']


def run_backtest(df, cf_hist, base, target, idx_of_date, n_full, values_for_features_full,
                 values_actual_full, values_actual_clean, verbose=True):
    """
    Blind-recursive backtest across FOLD_CUTOFFS.
    Returns (winner_name, winner_members, avg_metrics_df, fold_results_df).
    """
    fold_results = []
    fold_preds = {}
    fold_y_true = {}

    for cutoff_str in get_validation_cutoffs(df):
        cutoff = pd.Timestamp(cutoff_str)
        if cutoff not in idx_of_date:
            continue
        cutoff_idx = idx_of_date[cutoff]
        fold_year = cutoff.year
        start_ts = pd.Timestamp(f'{fold_year}-08-26')
        end_ts = pd.Timestamp(f'{fold_year}-12-31')
        if start_ts not in idx_of_date or end_ts not in idx_of_date:
            continue
        fc_start = idx_of_date[start_ts]
        fc_end = idx_of_date[end_ts]
        forecast_idx = list(range(fc_start, fc_end + 1))
        y_true = values_actual_full[forecast_idx]
        if np.isnan(y_true).any():
            continue
        fold_y_true[fold_year] = y_true

        values_hidden = values_for_features_full.copy()
        values_hidden[cutoff_idx + 1:] = np.nan

        hol_idx_all = np.where(cf_hist.is_holiday.to_numpy() == 1)[0]
        hol_idx_known = hol_idx_all[hol_idx_all <= cutoff_idx]
        holiday_ratio = compute_holiday_ratio(values_hidden, hol_idx_known)
        seasonal_arr = compute_doy_seasonal_index_array(df, target, cf_hist.full_dates, lock_year=fold_year - 1)
        on_med, before_med, after_med, p_on, p_bef, p_aft = compute_named_holiday_ratios(
            values_hidden, cf_hist, cutoff_idx)
        named_ratio_arr = build_named_ratio_array(
            cf_hist, on_med, before_med, after_med, p_on, p_bef, p_aft)
        hist_mdow_arr, hist_m_arr = compute_historical_context_features(
            df, target, cf_hist.full_dates, cutoff)

        train_idx_raw = list(range(config.MIN_TRAIN_START_IDX, cutoff_idx + 1))
        train_valid_mask = ~np.isnan(values_actual_clean[train_idx_raw])
        train_idx = [i for i, m in zip(train_idx_raw, train_valid_mask) if m]
        X_train = build_frame(values_hidden, train_idx, cf_hist, base, holiday_ratio, seasonal_arr, named_ratio_arr,
                              hist_mdow_arr=hist_mdow_arr, hist_m_arr=hist_m_arr)
        y_train_raw = values_actual_clean[train_idx]

        for name, model_proto, transform_name in get_model_configs():
            t0 = time.time()
            fwd, inv = TARGET_TRANSFORMS[transform_name]
            model = type(model_proto)(**model_proto.get_params())
            model.fit(X_train, fwd(y_train_raw))
            preds = recursive_forecast(model, values_hidden, forecast_idx, cf_hist, base,
                                        holiday_ratio, inv, seasonal_arr, named_ratio_arr,
                                        hist_mdow_arr=hist_mdow_arr, hist_m_arr=hist_m_arr)
            y_pred = [preds[i] for i in forecast_idx]
            fold_preds[(fold_year, name)] = y_pred
            m = metrics(y_true, y_pred)
            am = two_sided_asymmetric_metrics(y_true, y_pred, config.UNDER_THRESHOLD, config.OVER_THRESHOLD)
            fold_results.append(dict(target=target, fold=fold_year, model=name, **m,
                                      under_violation_pct=am['under_violation_pct'],
                                      over_violation_pct=am['over_violation_pct'],
                                      violation_pct=am['violation_pct'],
                                      mean_under_amount=am['mean_under_amount'],
                                      mean_over_amount=am['mean_over_amount']))
            if verbose:
                logger.info(f"  fold={fold_year} {name:16s}: MAE={m['MAE']:.0f} MAPE={m['MAPE']:.2f}% "
                            f"Acc={m['validation_accuracy']:.2f}% R2={m['R2']:.3f} ({time.time()-t0:.1f}s)")

    if not fold_results:
        # Fallback if historical data doesn't cover all fold cutoffs
        logger.warning(f"No fold completed for target {target}, using default XGBoost_raw")
        return "XGBoost_raw", None, pd.DataFrame(), pd.DataFrame()

    fr = pd.DataFrame(fold_results)
    avg_base = fr.groupby('model')[['MAE', 'RMSE', 'MAPE', 'R2', 'validation_accuracy',
                                     'under_violation_pct', 'over_violation_pct', 'violation_pct',
                                     'mean_under_amount', 'mean_over_amount']].mean().reset_index()

    # Candidate ensembles: evaluate top-2 and top-3 ensembles by lowest MAE
    candidate_ensembles = [
        ('Ensemble_top2', avg_base.sort_values('MAE').head(2)['model'].tolist()),
        ('Ensemble_top3', avg_base.sort_values('MAE').head(3)['model'].tolist()),
    ]
    for ens_name, top_members in candidate_ensembles:
        if len(top_members) >= 2:
            for fold_year, y_true in fold_y_true.items():
                member_preds = [fold_preds[(fold_year, m)] for m in top_members if (fold_year, m) in fold_preds]
                if len(member_preds) == len(top_members):
                    y_pred = np.mean(member_preds, axis=0)
                    m = metrics(y_true, y_pred)
                    am = two_sided_asymmetric_metrics(y_true, y_pred, config.UNDER_THRESHOLD, config.OVER_THRESHOLD)
                    fold_results.append(dict(target=target, fold=fold_year, model=ens_name, **m,
                                              under_violation_pct=am['under_violation_pct'],
                                              over_violation_pct=am['over_violation_pct'],
                                              violation_pct=am['violation_pct'],
                                              mean_under_amount=am['mean_under_amount'],
                                              mean_over_amount=am['mean_over_amount']))

    fr = pd.DataFrame(fold_results)
    avg = fr.groupby('model')[['MAE', 'RMSE', 'MAPE', 'R2', 'validation_accuracy',
                                'under_violation_pct', 'over_violation_pct', 'violation_pct',
                                'mean_under_amount', 'mean_over_amount']].mean().reset_index()
    winner = select_winner(avg)
    winner_members = None
    for ens_name, members in candidate_ensembles:
        if winner == ens_name:
            winner_members = members
            break
    return winner, winner_members, avg, fr

