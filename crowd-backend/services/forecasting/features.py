"""
Feature engineering layer for UTS and PRS passenger forecasting.
Computes named holiday demand ratios and recursive feature frames.
"""
import numpy as np
import pandas as pd

from .common import (
    CALENDAR_FEATURES,
    ALL_FEATURES_BLIND,
    target_features_for_index,
    build_target_dependent_matrix
)

FEATURES = ALL_FEATURES_BLIND + ['named_holiday_ratio', 'named_holiday_adjusted_baseline']


def compute_named_holiday_ratios(values_for_features, cf, cutoff_idx, roll_window=30, min_occurrences=1):
    """
    Median (actual / trailing-30-day-baseline) ratio per holiday name, split by whether
    the day is the holiday itself, the day immediately before it, or the day immediately
    after -- using only occurrences at or before cutoff_idx (no leakage).
    """
    names_by_pos = cf.hol_name.to_numpy()
    is_hol_pos = cf.is_holiday.to_numpy()
    on_r, before_r, after_r = {}, {}, {}
    for i in range(min(cutoff_idx, cf.n - 1) + 1):
        if is_hol_pos[i] != 1:
            continue
        name = names_by_pos[i]
        if not name:
            continue
        if i - roll_window >= 0:
            v = values_for_features[i]
            base = np.nanmean(values_for_features[i - roll_window:i])
            if not np.isnan(v) and not np.isnan(base) and base > 0:
                on_r.setdefault(name, []).append(v / base)
        if i - 1 >= 0 and is_hol_pos[i - 1] == 0 and (i - 1) - roll_window >= 0:
            vb = values_for_features[i - 1]
            baseb = np.nanmean(values_for_features[(i - 1) - roll_window:i - 1])
            if not np.isnan(vb) and not np.isnan(baseb) and baseb > 0:
                before_r.setdefault(name, []).append(vb / baseb)
        if i + 1 <= cutoff_idx and is_hol_pos[i + 1] == 0 and (i + 1) - roll_window >= 0:
            va = values_for_features[i + 1]
            basea = np.nanmean(values_for_features[(i + 1) - roll_window:i + 1])
            if not np.isnan(va) and not np.isnan(basea) and basea > 0:
                after_r.setdefault(name, []).append(va / basea)

    def summarize(d):
        return {k: float(np.median(v)) for k, v in d.items() if len(v) >= min_occurrences}

    def pooled(d):
        allv = [x for v in d.values() for x in v]
        return float(np.median(allv)) if allv else 1.0

    return (
        summarize(on_r),
        summarize(before_r),
        summarize(after_r),
        pooled(on_r),
        pooled(before_r),
        pooled(after_r)
    )


def build_named_ratio_array(cf, on_med, before_med, after_med, pooled_on, pooled_before, pooled_after,
                             overrides=None):
    """
    Exogenous array of holiday multipliers aligned to the full date grid with multi-day pre/post support.
    """
    n = cf.n
    names_by_pos = cf.hol_name.to_numpy()
    is_hol_pos = cf.is_holiday.to_numpy()
    days_to = cf.days_to_hol
    days_since = cf.days_since_hol
    arr = np.ones(n)
    overrides = overrides or {}
    for i in range(n):
        if is_hol_pos[i] == 1:
            name = names_by_pos[i]
            if name in overrides and 'on' in overrides[name]:
                arr[i] = overrides[name]['on']
            else:
                arr[i] = on_med.get(name, pooled_on)
        elif days_to[i] in [1, 2, 3] and (i + int(days_to[i])) < n and is_hol_pos[i + int(days_to[i])] == 1:
            dt = int(days_to[i])
            name = names_by_pos[i + dt]
            key_override = f'before_{dt}' if dt > 1 else 'before'
            if name in overrides and key_override in overrides[name]:
                arr[i] = overrides[name][key_override]
            elif name in overrides and 'before' in overrides[name] and dt == 1:
                arr[i] = overrides[name]['before']
            elif dt == 1:
                arr[i] = before_med.get(name, pooled_before)
            else:
                arr[i] = max(before_med.get(name, pooled_before) * (1.0 - 0.03 * (dt - 1)), 1.0)
        elif days_since[i] in [1, 2] and (i - int(days_since[i])) >= 0 and is_hol_pos[i - int(days_since[i])] == 1:
            ds = int(days_since[i])
            name = names_by_pos[i - ds]
            key_override = f'after_{ds}' if ds > 1 else 'after'
            if name in overrides and key_override in overrides[name]:
                arr[i] = overrides[name][key_override]
            elif name in overrides and 'after' in overrides[name] and ds == 1:
                arr[i] = overrides[name]['after']
            elif ds == 1:
                arr[i] = after_med.get(name, pooled_after)
            else:
                arr[i] = max(after_med.get(name, pooled_after) * (1.0 - 0.03 * (ds - 1)), 1.0)
    return arr


def build_frame(values_src, indices, cf, base, holiday_ratio, seasonal_arr, named_ratio_arr):
    """
    Build the model input matrix for a batch of date indices.
    """
    tdep = build_target_dependent_matrix(values_src, indices, cf, holiday_ratio, seasonal_arr)
    tdep = tdep.reset_index(drop=True)
    cal = base.iloc[indices][CALENDAR_FEATURES].reset_index(drop=True)
    nr = named_ratio_arr[indices]
    tdep['named_holiday_ratio'] = nr
    
    # Balanced baseline anchor without upward max bias
    r7 = tdep['roll_mean_7']
    r30 = tdep['roll_mean_30']
    sd4 = tdep['same_dow_roll_mean_4']
    base_anchor = r30.fillna(r7).fillna(sd4).fillna(10000.0)
    
    tdep['named_holiday_adjusted_baseline'] = base_anchor * nr
    return pd.concat([cal, tdep], axis=1)[FEATURES]


def recursive_forecast(model, values_hidden, forecast_idx, cf, base, holiday_ratio, inv, seasonal_arr,
                        named_ratio_arr):
    """
    Blind multi-step forecast: each day's prediction is fed back in for subsequent lags.
    Deseasonalizes holiday spikes when feeding back into base rolling features to prevent ratchet inflation.
    """
    values = values_hidden.copy()
    preds = {}
    for i in forecast_idx:
        tfeat = target_features_for_index(values, i, cf, holiday_ratio, seasonal_arr)
        cfeat = base.iloc[i][CALENDAR_FEATURES].to_dict()
        nr = named_ratio_arr[i]
        
        r7 = tfeat['roll_mean_7'] if not np.isnan(tfeat['roll_mean_7']) else tfeat['roll_mean_30']
        r30 = tfeat['roll_mean_30'] if not np.isnan(tfeat['roll_mean_30']) else r7
        sd4 = tfeat['same_dow_roll_mean_4'] if not np.isnan(tfeat['same_dow_roll_mean_4']) else r30
        valid_anchors = [x for x in [r30, r7, sd4] if not np.isnan(x)]
        base_anchor = valid_anchors[0] if valid_anchors else 10000.0

        tfeat['named_holiday_ratio'] = nr
        tfeat['named_holiday_adjusted_baseline'] = base_anchor * nr
        row = {**cfeat, **tfeat}
        X = pd.DataFrame([row])[FEATURES]
        raw_pred = float(model.predict(X)[0])
        p = max(float(inv(raw_pred)), 0.0)
        
        # Store exact prediction for output
        preds[i] = p
        
        # Feed deseasonalized baseline into feature matrix to prevent holiday spike accumulation
        base_p = (p / nr) if (nr is not None and nr > 1.0) else p
        values[i] = base_p
    return preds

