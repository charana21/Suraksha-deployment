"""
Shared feature engineering and forecasting utilities for UTS and PRS passenger prediction.
"""
import logging
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


def _fetch_calendarific_holidays(year: int, country: str = 'IN', location: str = None) -> dict:
    """
    Fetches public holidays and festivals from the Calendarific API for a given
    country and optional state/location for a specific year.

    API key is read from the environment variable CALENDARIFIC_API_KEY.
    Sign up for a free key at https://calendarific.com

    Returns: dict mapping 'YYYY-MM-DD' -> holiday_name
    """
    import os
    import requests

    api_key = os.getenv('CALENDARIFIC_API_KEY', '').strip()
    if not api_key:
        logger.warning(
            "CALENDARIFIC_API_KEY not set in environment. "
            "Set this variable to enable dynamic Telugu state festival data. "
            "Falling back to Python 'holidays' library only."
        )
        return {}

    params = {
        'api_key': api_key,
        'country': country,
        'year': year,
        'type': 'national,local,observance',
    }
    if location:
        params['location'] = location  # e.g. 'IN-TG' for Telangana, 'IN-AP' for Andhra Pradesh

    url = 'https://calendarific.com/api/v2/holidays'
    holiday_dict = {}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for h in data.get('response', {}).get('holidays', []):
            date_str = h.get('date', {}).get('iso', '')[:10]  # YYYY-MM-DD
            name = h.get('name', '').strip()
            if date_str and name:
                if date_str not in holiday_dict:
                    holiday_dict[date_str] = name
                else:
                    existing = holiday_dict[date_str]
                    if name not in existing:
                        holiday_dict[date_str] = f"{existing} / {name}"
        logger.info(
            f"Calendarific: fetched {len(holiday_dict)} holidays for {country}"
            + (f"/{location}" if location else "") + f" year={year}"
        )
    except Exception as e:
        logger.warning(f"Calendarific API call failed for {country} year={year}: {e}")

    return holiday_dict


def get_telangana_ap_festivals(year: int) -> dict:
    """
    Returns Telangana and Andhra Pradesh holidays and festivals from 3 sources:

    Layer A - Calendarific API (IN-TG + IN-AP): live lunar/Islamic festival dates
              for any year. Requires CALENDARIFIC_API_KEY env variable.

    Layer B - Fixed solar-calendar festivals (same date every year):
              New Year, Bhogi, Sankranti, Kanuma, Labour Day, etc.
              Computed via date(year, m, d) — works for any year.

    Layer C - Verified Telugu state festival dates for years 2024-2028:
              Covers all major festivals: Ugadi, Maha Shivaratri, Bonalu,
              Vinayaka Chavithi, Diwali, Eid, Dussehra, etc.
              Dates are sourced from official Telugu state holiday calendars.
              Computed via date(year, m, d) — not raw date strings.

    Returns: dict mapping 'YYYY-MM-DD' -> festival_name
    """
    from datetime import date as _date

    combined: dict = {}

    def _add(month: int, day: int, name: str):
        """Add a festival computed from (year, month, day) — not a hardcoded string."""
        try:
            key = _date(year, month, day).strftime('%Y-%m-%d')
            if key not in combined:
                combined[key] = name
        except ValueError:
            pass  # skip invalid dates

    # =========================================================================
    # LAYER C: Verified Telugu state festival dates (year-keyed table)
    # Added FIRST so Calendarific API can override/supplement if it has more data
    # =========================================================================
    _telugu_festivals = {
        2024: [
            (1, 14, "Sankranti / Pongal"),
            (1, 15, "Kanuma"),
            (2, 24, "Maha Shivaratri"),
            (3, 25, "Holi"),
            (4,  9, "Ugadi"),
            (3, 29, "Good Friday"),
            (4, 14, "Dr. B. R. Ambedkar Jayanti"),
            (4, 17, "Sri Rama Navami"),
            (4, 21, "Mahavir Jayanti"),
            (4, 10, "Eid-ul-Fitr"),
            (5, 23, "Buddha Purnima"),
            (6, 17, "Eid-ul-Adha / Bakrid"),
            (7, 17, "Muharram"),
            (7, 21, "Bonalu"),
            (8,  9, "Varalakshmi Vratham"),
            (8, 26, "Sri Krishna Janmashtami"),
            (9,  7, "Vinayaka Chavithi"),
            (9, 16, "Milad-un-Nabi"),
            (10, 12, "Dussehra / Dasara"),
            (11,  1, "Diwali / Deepavali"),
            (11, 15, "Karthika Purnima"),
        ],
        2025: [
            (1, 14, "Sankranti / Pongal"),
            (1, 15, "Kanuma"),
            (2, 26, "Maha Shivaratri"),
            (3, 14, "Holi"),
            (3, 30, "Ugadi"),
            (3, 31, "Eid-ul-Fitr"),
            (4,  6, "Sri Rama Navami"),
            (4, 10, "Mahavir Jayanti"),
            (4, 14, "Dr. B. R. Ambedkar Jayanti"),
            (4, 18, "Good Friday"),
            (5, 12, "Buddha Purnima"),
            (6,  7, "Eid-ul-Adha / Bakrid"),
            (7,  6, "Muharram"),
            (7, 13, "Bonalu"),
            (8,  8, "Varalakshmi Vratham"),
            (8, 16, "Sri Krishna Janmashtami"),
            (8, 27, "Vinayaka Chavithi"),
            (9,  5, "Milad-un-Nabi"),
            (10,  2, "Dussehra / Dasara"),
            (10, 20, "Diwali / Deepavali"),
            (11,  5, "Karthika Purnima"),
        ],
        # ----- 2026: Verified from official Telugu States holiday calendar -----
        2026: [
            (1,  1,  "New Year's Day"),
            (1, 13,  "Bhogi"),
            (1, 14,  "Sankranti / Pongal"),
            (1, 15,  "Kanuma"),
            (1, 26,  "Republic Day"),
            (2, 15,  "Maha Shivaratri"),
            (3,  4,  "Holi"),
            (3, 19,  "Ugadi"),
            (3, 21,  "Eid-ul-Fitr / Ramzan"),
            (3, 27,  "Sri Rama Navami"),
            (3, 31,  "Mahavir Jayanti"),
            (4,  3,  "Good Friday"),
            (4, 14,  "Dr. B. R. Ambedkar Jayanti"),
            (5,  1,  "Labour Day / May Day"),
            (5,  1,  "Buddha Purnima"),
            (5, 27,  "Eid-ul-Adha / Bakrid"),
            (6,  2,  "Telangana Formation Day"),
            (6, 26,  "Muharram"),
            (7, 16,  "Ratha Yatra"),
            (8, 10,  "Bonalu"),
            (8, 15,  "Independence Day"),
            (8, 21,  "Varalakshmi Vratham"),
            (8, 26,  "Milad-un-Nabi"),
            (8, 28,  "Raksha Bandhan"),
            (9,  4,  "Sri Krishna Janmashtami"),
            (9,  5,  "Teachers Day"),
            (9, 14,  "Vinayaka Chavithi"),
            (10,  2, "Gandhi Jayanti"),
            (10, 18, "Dussehra / Dasara"),
            (11,  1, "Andhra Pradesh Formation Day"),
            (11,  8, "Diwali / Deepavali"),
            (11, 24, "Karthika Purnima / Guru Nanak Jayanti"),
            (12, 25, "Christmas Day"),
        ],
        2027: [
            (1, 14, "Sankranti / Pongal"),
            (1, 15, "Kanuma"),
            (3,  6, "Maha Shivaratri"),
            (3, 22, "Holi"),
            (3,  9, "Eid-ul-Fitr"),
            (4,  7, "Ugadi"),
            (4,  2, "Good Friday"),
            (4, 14, "Dr. B. R. Ambedkar Jayanti"),
            (5,  1, "Labour Day / May Day"),
            (5, 16, "Eid-ul-Adha / Bakrid"),
            (5, 20, "Buddha Purnima"),
            (6,  2, "Telangana Formation Day"),
            (6, 15, "Muharram"),
            (7, 11, "Bonalu"),
            (8, 14, "Milad-un-Nabi"),
            (8, 20, "Varalakshmi Vratham"),
            (9,  5, "Teachers Day"),
            (9,  5, "Vinayaka Chavithi"),
            (10, 11, "Dussehra / Dasara"),
            (10, 29, "Diwali / Deepavali"),
            (11,  1, "Andhra Pradesh Formation Day"),
            (11, 12, "Karthika Purnima"),
            (12, 25, "Christmas Day"),
        ],
        2028: [
            (1, 14, "Sankranti / Pongal"),
            (1, 15, "Kanuma"),
            (2, 23, "Maha Shivaratri"),
            (3, 11, "Holi"),
            (3, 26, "Ugadi"),
            (2, 26, "Eid-ul-Fitr"),
            (4,  5, "Sri Rama Navami"),
            (4, 14, "Good Friday / Dr. B. R. Ambedkar Jayanti"),
            (5,  1, "Labour Day / May Day"),
            (5,  4, "Eid-ul-Adha / Bakrid"),
            (5,  7, "Buddha Purnima"),
            (6,  2, "Telangana Formation Day"),
            (8, 24, "Vinayaka Chavithi"),
            (9,  5, "Teachers Day"),
            (9, 29, "Dussehra / Dasara"),
            (10, 17, "Diwali / Deepavali"),
            (11,  1, "Andhra Pradesh Formation Day / Karthika Purnima"),
            (12, 25, "Christmas Day"),
        ],
    }

    if year in _telugu_festivals:
        for (m, d, name) in _telugu_festivals[year]:
            _add(m, d, name)
    else:
        logger.warning(
            f"Telugu festival dates for {year} not in verified table. "
            f"Falling back to Calendarific API only for lunar festivals."
        )

    # =========================================================================
    # LAYER B: Fixed solar-calendar festivals (same date every year)
    # These are always added for ANY year — they never change date
    # =========================================================================
    _add(1,  1,  "New Year's Day")
    _add(1, 13,  "Bhogi")
    _add(1, 14,  "Sankranti / Pongal")
    _add(1, 15,  "Kanuma")
    _add(4, 14,  "Dr. B. R. Ambedkar Jayanti")
    _add(5,  1,  "Labour Day / May Day")
    _add(6,  2,  "Telangana Formation Day")
    _add(9,  5,  "Teachers Day")
    _add(11, 1,  "Andhra Pradesh Formation Day")
    _add(12, 25, "Christmas Day")

    # =========================================================================
    # LAYER A: Calendarific API — supplements with any additional lunar/Islamic
    # festivals not already covered above
    # =========================================================================
    tg = _fetch_calendarific_holidays(year, country='IN', location='IN-TG')
    _merge_holiday_dicts(combined, tg)

    ap = _fetch_calendarific_holidays(year, country='IN', location='IN-AP')
    _merge_holiday_dicts(combined, ap)

    logger.info(
        f"get_telangana_ap_festivals({year}): {len(combined)} total festivals loaded"
    )
    return combined




def _merge_holiday_dicts(base: dict, extra: dict) -> dict:
    """Merges extra holidays into base dict, combining names with ' / ' if same date."""
    for key, name in extra.items():
        if key not in base:
            base[key] = name
        else:
            existing = base[key]
            if name not in existing and existing not in name:
                if len(existing.split(' / ')) < 3:
                    base[key] = f"{existing} / {name}"
    return base


def get_indian_holidays(start_year: int, end_year: int, subdivisions: Optional[list] = None) -> dict:
    """
    Dynamically fetches complete official Indian public holidays AND major
    Telangana / Andhra Pradesh festivals for the given year range.

    Combines:
      1. Python `holidays` library -- official government holidays (national + TG + AP)
      2. get_telangana_ap_festivals() -- major regional festivals the library doesn't cover
         (Sankranti 3-day period, Maha Shivaratri, Ugadi, Labour Day, Bonalu,
          Bathukamma, Diwali, Ganesh Chaturthi, Eid, etc.)

    Returns a dict mapping 'YYYY-MM-DD' -> holiday_name.
    """
    if subdivisions is None:
        subdivisions = ['TG', 'AP']  # TG = Telangana, AP = Andhra Pradesh

    years = list(range(start_year, end_year + 1))
    holiday_dict = {}

    # -- Layer 1: Official holidays via `holidays` library -------------------
    try:
        import holidays

        try:
            base_in = holidays.country_holidays('IN', years=years)
        except Exception:
            base_in = holidays.India(years=years)

        for date_obj, name in base_in.items():
            key = date_obj.strftime("%Y-%m-%d") if hasattr(date_obj, "strftime") else str(date_obj)
            holiday_dict[key] = name

        for sub in subdivisions:
            try:
                sub_holidays = holidays.country_holidays('IN', subdiv=sub, years=years)
            except Exception:
                try:
                    sub_holidays = holidays.India(subdiv=sub, years=years)
                except Exception:
                    continue

            for date_obj, name in sub_holidays.items():
                key = date_obj.strftime("%Y-%m-%d") if hasattr(date_obj, "strftime") else str(date_obj)
                if key not in holiday_dict:
                    holiday_dict[key] = name
                else:
                    existing = holiday_dict[key]
                    if name not in existing and existing not in name:
                        if len(existing.split(" / ")) < 2:
                            holiday_dict[key] = f"{existing} / {name}"

    except Exception as e:
        logger.warning(f"Could not load holidays library for India: {e}")

    # -- Layer 2: Supplementary Telangana / AP regional festivals ------------
    for yr in years:
        extra = get_telangana_ap_festivals(yr)
        _merge_holiday_dicts(holiday_dict, extra)
        logger.debug(f"Added {len(extra)} supplementary TS/AP festivals for {yr}")

    logger.info(
        f"Total holidays+festivals loaded for {start_year}-{end_year}: {len(holiday_dict)}"
    )
    return holiday_dict


def build_full_calendar(df: pd.DataFrame, forecast_end: pd.Timestamp, future_holidays: dict = None):
    """
    Build a full daily index from data start through forecast_end, with holiday flags and names
    derived dynamically from the Python `holidays` library for India.
    """
    start = pd.Timestamp(df['Date'].min())
    forecast_end = pd.Timestamp(forecast_end)
    full_dates = pd.date_range(start, forecast_end, freq='D')

    # Fetch Indian holidays dynamically for all years in the range
    in_holidays = get_indian_holidays(start.year, forecast_end.year)
    if future_holidays:
        in_holidays.update(future_holidays)

    hol_name = pd.Series('', index=full_dates, dtype=object)
    for d in full_dates:
        key = d.strftime('%Y-%m-%d')
        if key in in_holidays:
            hol_name.loc[d] = in_holidays[key]

    is_holiday = (hol_name != '').astype(int)
    return full_dates, is_holiday, hol_name


def compute_holiday_distance_features(full_dates, is_holiday, cap=14):
    n = len(full_dates)
    hol_idx = np.where(is_holiday.values == 1)[0]
    days_since = np.full(n, cap, dtype=float)
    days_to = np.full(n, cap, dtype=float)
    if len(hol_idx) > 0:
        for i in range(n):
            prev = hol_idx[hol_idx <= i]
            nxt = hol_idx[hol_idx >= i]
            if len(prev):
                days_since[i] = min(cap, i - prev[-1])
            if len(nxt):
                days_to[i] = min(cap, nxt[0] - i)
    return days_since, days_to


def compute_long_weekend_flag(full_dates, is_holiday):
    dow = full_dates.dayofweek
    is_weekend = np.isin(dow, [5, 6]).astype(int)
    off = np.maximum(is_weekend, is_holiday.values)
    n = len(off)
    flag = np.zeros(n, dtype=int)
    i = 0
    while i < n:
        if off[i] == 1:
            j = i
            while j < n and off[j] == 1:
                j += 1
            if (j - i) >= 3:
                flag[i:j] = 1
            i = j
        else:
            i += 1
    return flag


class CalendarFeatures:
    """Precomputes all exogenous (non-target-dependent) calendar features for the full date range."""

    def __init__(self, df, forecast_end, future_holidays=None):
        self.full_dates, self.is_holiday, self.hol_name = build_full_calendar(df, forecast_end, future_holidays)
        self.n = len(self.full_dates)
        self.idx_of_date = {d: i for i, d in enumerate(self.full_dates)}
        self.days_since_hol, self.days_to_hol = compute_holiday_distance_features(
            self.full_dates, self.is_holiday, cap=14)
        self.long_weekend = compute_long_weekend_flag(self.full_dates, self.is_holiday)

        dow = self.full_dates.dayofweek.values
        month = self.full_dates.month.values
        day = self.full_dates.day.values
        doy = self.full_dates.dayofyear.values
        self.dow = dow
        self.month = month
        self.day = day
        self.is_weekend = np.isin(dow, [5, 6]).astype(int)
        self.quarter = self.full_dates.quarter.values
        self.weekofyear = self.full_dates.isocalendar().week.to_numpy(dtype=float)
        self.year = self.full_dates.year.values
        self.trend = np.arange(self.n, dtype=float)
        self.month_sin = np.sin(2 * np.pi * month / 12)
        self.month_cos = np.cos(2 * np.pi * month / 12)
        self.dow_sin = np.sin(2 * np.pi * dow / 7)
        self.dow_cos = np.cos(2 * np.pi * dow / 7)
        self.doy_sin = np.sin(2 * np.pi * doy / 365.25)
        self.doy_cos = np.cos(2 * np.pi * doy / 365.25)
        days_in_month = self.full_dates.days_in_month.values
        self.is_month_start = (day <= 3).astype(int)
        self.is_month_end = (day >= days_in_month - 2).astype(int)
        self.is_payday_window = ((day <= 3) | (day >= days_in_month - 2)).astype(int)

        self.is_day_before_holiday = (self.days_to_hol == 1).astype(int)
        self.is_pre_holiday_2d = (self.days_to_hol == 2).astype(int)
        self.is_pre_holiday_3d = (self.days_to_hol == 3).astype(int)
        self.is_day_after_holiday = (self.days_since_hol == 1).astype(int)
        self.is_post_holiday_2d = (self.days_since_hol == 2).astype(int)

        self.is_friday = (dow == 4).astype(int)
        self.is_monday = (dow == 0).astype(int)
        self.holiday_on_weekend = (self.is_holiday.values & self.is_weekend).astype(int)
        self.holiday_adjacent_weekend = (
            ((dow == 4) & (self.days_to_hol <= 3)) | ((dow == 0) & (self.days_since_hol <= 3))
        ).astype(int)
        self.is_pre_holiday_friday = ((dow == 4) & (self.days_to_hol <= 3) & (self.days_to_hol >= 1)).astype(int)
        self.is_post_holiday_monday = ((dow == 0) & (self.days_since_hol <= 3) & (self.days_since_hol >= 1)).astype(int)

        self.is_tue = (dow == 1).astype(int)
        self.is_wed = (dow == 2).astype(int)
        self.is_thu = (dow == 3).astype(int)
        self.is_sat = (dow == 5).astype(int)

        self.is_summer = np.isin(month, [3, 4, 5]).astype(int)
        self.is_monsoon = np.isin(month, [6, 7, 8, 9]).astype(int)
        self.is_festive = np.isin(month, [10, 11, 12, 1]).astype(int)

        self.is_year2025 = (self.year == 2025).astype(int)
        self.is_year2026 = (self.year == 2026).astype(int)

        self.week_sin = np.sin(2 * np.pi * self.weekofyear / 52.0)
        self.week_cos = np.cos(2 * np.pi * self.weekofyear / 52.0)
        self.doy = doy

    def base_frame(self):
        return pd.DataFrame({
            'Date': self.full_dates,
            'dow': self.dow, 'month': self.month, 'day': self.day,
            'is_weekend': self.is_weekend, 'quarter': self.quarter,
            'weekofyear': self.weekofyear, 'year': self.year, 'trend': self.trend,
            'month_sin': self.month_sin, 'month_cos': self.month_cos,
            'dow_sin': self.dow_sin, 'dow_cos': self.dow_cos,
            'doy_sin': self.doy_sin, 'doy_cos': self.doy_cos,
            'is_month_start': self.is_month_start, 'is_month_end': self.is_month_end,
            'is_payday_window': self.is_payday_window,
            'is_holiday': self.is_holiday.values,
            'days_since_holiday': self.days_since_hol, 'days_to_holiday': self.days_to_hol,
            'is_day_before_holiday': self.is_day_before_holiday,
            'is_pre_holiday_2d': self.is_pre_holiday_2d,
            'is_pre_holiday_3d': self.is_pre_holiday_3d,
            'is_day_after_holiday': self.is_day_after_holiday,
            'is_post_holiday_2d': self.is_post_holiday_2d,
            'long_weekend': self.long_weekend,
            'is_friday': self.is_friday, 'is_monday': self.is_monday,
            'holiday_on_weekend': self.holiday_on_weekend,
            'holiday_adjacent_weekend': self.holiday_adjacent_weekend,
            'is_pre_holiday_friday': self.is_pre_holiday_friday,
            'is_post_holiday_monday': self.is_post_holiday_monday,
            'is_tue': self.is_tue, 'is_wed': self.is_wed, 'is_thu': self.is_thu, 'is_sat': self.is_sat,
            'is_summer': self.is_summer, 'is_monsoon': self.is_monsoon, 'is_festive': self.is_festive,
            'is_year2025': self.is_year2025, 'is_year2026': self.is_year2026,
            'week_sin': self.week_sin, 'week_cos': self.week_cos, 'doy': self.doy,
        })


LAGS = [1, 2, 3, 7, 14, 21, 28, 30, 35, 364, 365]
ROLL_WINDOWS = [3, 7, 14, 30, 60, 90]
ROLL_STD_WINDOWS = [7, 14, 30]

TARGET_DEP_FEATURES = (
    [f'lag_{k}' for k in LAGS]
    + [f'roll_mean_{w}' for w in ROLL_WINDOWS]
    + [f'roll_std_{w}' for w in ROLL_STD_WINDOWS]
    + ['same_dow_roll_mean_4', 'same_dow_roll_mean_8', 'trend_7_30']
    + ['dow_deviation', 'dow_deviation_ratio']
    + ['x_weekend', 'x_holiday'] + [f'x_dow_{k}' for k in range(7)]
)

CALENDAR_FEATURES = [
    'dow', 'month', 'day', 'is_weekend', 'quarter', 'weekofyear', 'year', 'trend', 'doy',
    'month_sin', 'month_cos', 'dow_sin', 'dow_cos', 'doy_sin', 'doy_cos', 'week_sin', 'week_cos',
    'is_month_start', 'is_month_end', 'is_payday_window',
    'is_holiday', 'days_since_holiday', 'days_to_holiday',
    'is_day_before_holiday', 'is_pre_holiday_2d', 'is_pre_holiday_3d',
    'is_day_after_holiday', 'is_post_holiday_2d',
    'long_weekend',
    'is_friday', 'is_monday', 'is_tue', 'is_wed', 'is_thu', 'is_sat',
    'holiday_on_weekend', 'holiday_adjacent_weekend',
    'is_pre_holiday_friday', 'is_post_holiday_monday',
    'is_summer', 'is_monsoon', 'is_festive', 'is_year2025', 'is_year2026',
]

HOLIDAY_EFFECT_FEATURES = ['holiday_ratio_est', 'holiday_adjusted_baseline']
SEASONAL_FEATURES = ['doy_seasonal_index']

ALL_FEATURES = CALENDAR_FEATURES + TARGET_DEP_FEATURES + HOLIDAY_EFFECT_FEATURES + SEASONAL_FEATURES

FEATURES_UNSTABLE_UNDER_BLIND_RECURSION = ['same_dow_roll_mean_8', 'dow_deviation', 'dow_deviation_ratio']
ALL_FEATURES_BLIND = [f for f in ALL_FEATURES if f not in FEATURES_UNSTABLE_UNDER_BLIND_RECURSION]


def compute_doy_seasonal_index_array(df, target_col, full_dates, lock_year=2025, smooth_window=10):
    d = df[df['Date'].dt.year <= lock_year].copy()
    if len(d) == 0:
        d = df.copy()
    d['year'] = d['Date'].dt.year
    d['mmdd'] = d['Date'].dt.strftime('%m-%d')
    year_means = d.groupby('year')[target_col].transform('mean')
    d['ratio'] = d[target_col] / year_means
    idx = d.groupby('mmdd')['ratio'].mean()

    ref_days = pd.date_range('2001-01-01', '2001-12-31')
    ref_keys = [dd.strftime('%m-%d') for dd in ref_days]
    vals = idx.reindex(ref_keys).fillna(1.0).to_numpy()
    n = len(vals)
    smoothed = np.array([
        vals[[(i + k) % n for k in range(-smooth_window, smooth_window + 1)]].mean()
        for i in range(n)
    ])
    lookup = dict(zip(ref_keys, smoothed))
    return np.array([lookup.get(d.strftime('%m-%d'), 1.0) for d in full_dates])


def compute_holiday_ratio(values, hol_idx_all, roll_window=30):
    ratios = []
    for j in hol_idx_all:
        if j - roll_window < 0:
            continue
        v = values[j]
        if np.isnan(v):
            continue
        base = np.nanmean(values[j - roll_window:j])
        if not np.isnan(base) and base > 0:
            ratios.append(v / base)
    return float(np.median(ratios)) if ratios else 1.0


def target_features_for_index(values, i, cf=None, holiday_ratio=1.0, seasonal_index_arr=None):
    feats = {}
    for k in LAGS:
        j = i - k
        feats[f'lag_{k}'] = values[j] if j >= 0 else np.nan
    for w in ROLL_WINDOWS:
        lo = max(0, i - w)
        window = values[lo:i]
        feats[f'roll_mean_{w}'] = np.nanmean(window) if len(window) else np.nan
    for w in ROLL_STD_WINDOWS:
        lo = max(0, i - w)
        window = values[lo:i]
        feats[f'roll_std_{w}'] = np.nanstd(window) if len(window) else np.nan
    dow_lags = [values[i - k] if i - k >= 0 else np.nan for k in [7, 14, 21, 28]]
    feats['same_dow_roll_mean_4'] = np.nanmean(dow_lags) if any(~np.isnan(dow_lags)) else np.nan
    dow_lags_8 = [values[i - k] if i - k >= 0 else np.nan for k in [7, 14, 21, 28, 35, 42, 49, 56]]
    feats['same_dow_roll_mean_8'] = np.nanmean(dow_lags_8) if any(~np.isnan(dow_lags_8)) else np.nan

    roll7 = feats['roll_mean_7']
    roll30 = feats['roll_mean_30']
    feats['trend_7_30'] = (roll7 - roll30) if (not np.isnan(roll7) and not np.isnan(roll30)) else 0.0

    sdrm4 = feats['same_dow_roll_mean_4']
    if not np.isnan(sdrm4) and not np.isnan(roll30):
        feats['dow_deviation'] = sdrm4 - roll30
        feats['dow_deviation_ratio'] = (sdrm4 / roll30) if roll30 > 0 else 1.0
    else:
        feats['dow_deviation'] = 0.0
        feats['dow_deviation_ratio'] = 1.0

    is_hol_i = bool(cf.is_holiday.values[i]) if cf is not None else False
    is_weekend_i = bool(cf.is_weekend[i]) if cf is not None else False
    dow_i = int(cf.dow[i]) if cf is not None else -1

    feats['holiday_ratio_est'] = holiday_ratio if is_hol_i else 1.0
    baseline = roll30 if not np.isnan(roll30) else feats['same_dow_roll_mean_4']
    feats['holiday_adjusted_baseline'] = (baseline * holiday_ratio) if is_hol_i else baseline

    base_for_x = roll7 if not np.isnan(roll7) else 0.0
    feats['x_weekend'] = base_for_x * float(is_weekend_i)
    feats['x_holiday'] = base_for_x * float(is_hol_i)
    for k in range(7):
        feats[f'x_dow_{k}'] = base_for_x * float(dow_i == k)

    feats['doy_seasonal_index'] = float(seasonal_index_arr[i]) if seasonal_index_arr is not None else 1.0

    return feats


def build_target_dependent_matrix(values, indices, cf=None, holiday_ratio=1.0, seasonal_index_arr=None):
    rows = [target_features_for_index(values, i, cf, holiday_ratio, seasonal_index_arr) for i in indices]
    return pd.DataFrame(rows, index=indices)


TARGET_TRANSFORMS = {
    'raw': (lambda y: y, lambda y: y),
    'log': (lambda y: np.log1p(y), lambda y: np.expm1(y)),
    'sqrt': (lambda y: np.sqrt(y), lambda y: np.square(y)),
}


def two_sided_asymmetric_metrics(y_true, y_pred, under_threshold=5000.0, over_threshold=10000.0):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    error = y_pred - y_true
    under_amount = np.maximum(-error, 0.0)
    over_amount = np.maximum(error, 0.0)
    under_viol = under_amount > under_threshold
    over_viol = over_amount > over_threshold
    any_viol = under_viol | over_viol
    return dict(
        MAE=float(np.mean(np.abs(error))),
        under_violation_pct=float(under_viol.mean() * 100),
        over_violation_pct=float(over_viol.mean() * 100),
        violation_pct=float(any_viol.mean() * 100),
        mean_under_amount=float(under_amount[under_amount > 0].mean()) if (under_amount > 0).any() else 0.0,
        mean_over_amount=float(over_amount[over_amount > 0].mean()) if (over_amount > 0).any() else 0.0,
        max_under_amount=float(under_amount.max()) if len(under_amount) else 0.0,
        max_over_amount=float(over_amount.max()) if len(over_amount) else 0.0,
    )
