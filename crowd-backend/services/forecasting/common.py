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
        2022: [
            (1, 14, "Sankranti / Pongal"),
            (1, 15, "Kanuma"),
            (3,  1, "Maha Shivaratri"),
            (3, 18, "Holi"),
            (4,  2, "Ugadi"),
            (4, 10, "Sri Rama Navami"),
            (4, 14, "Dr. B. R. Ambedkar Jayanti"),
            (4, 15, "Good Friday"),
            (5,  3, "Eid-ul-Fitr / Ramzan"),
            (5, 16, "Buddha Purnima"),
            (6,  2, "Telangana Formation Day"),
            (7, 10, "Eid-ul-Adha / Bakrid"),
            (7, 24, "Bonalu"),
            (8,  9, "Muharram"),
            (8, 15, "Independence Day"),
            (8, 19, "Sri Krishna Janmashtami"),
            (8, 31, "Vinayaka Chavithi"),
            (10,  2, "Gandhi Jayanti"),
            (10,  5, "Dussehra / Dasara"),
            (10,  8, "Milad-un-Nabi"),
            (10, 24, "Diwali / Deepavali"),
            (11,  8, "Karthika Purnima / Guru Nanak Jayanti"),
            (12, 25, "Christmas Day"),
        ],
        2023: [
            (1, 14, "Bhogi"),
            (1, 15, "Sankranti / Pongal"),
            (1, 16, "Kanuma"),
            (1, 26, "Republic Day"),
            (2, 18, "Maha Shivaratri"),
            (3,  8, "Holi"),
            (3, 22, "Ugadi"),
            (3, 30, "Sri Rama Navami"),
            (4,  7, "Good Friday"),
            (4, 14, "Dr. B. R. Ambedkar Jayanti"),
            (4, 22, "Eid-ul-Fitr / Ramzan"),
            (5,  1, "Labour Day / May Day"),
            (5,  5, "Buddha Purnima"),
            (6,  2, "Telangana Formation Day"),
            (6, 29, "Eid-ul-Adha / Bakrid"),
            (7,  9, "Bonalu"),
            (7, 29, "Muharram"),
            (8, 15, "Independence Day"),
            (8, 25, "Varalakshmi Vratham"),
            (9,  7, "Sri Krishna Janmashtami"),
            (9, 18, "Vinayaka Chavithi"),
            (9, 28, "Milad-un-Nabi"),
            (10,  2, "Gandhi Jayanti"),
            (10, 24, "Dussehra / Dasara"),
            (11, 12, "Diwali / Deepavali"),
            (11, 27, "Karthika Purnima / Guru Nanak Jayanti"),
            (12, 25, "Christmas Day"),
        ],
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
            (10,  2, "Mahatma Gandhi Jayanti"),
            (10, 10, "Bathukamma Festival Begins"),
            (10, 18, "Saddula Bathukamma"),
            (10, 19, "Durgashtami / Maha Navami"),
            (10, 20, "Dussehra / Vijaya Dasami"),
            (10, 21, "Vijaya Dasami (Next Day)"),
            (11,  1, "Andhra Pradesh Formation Day"),
            (11,  7, "Naraka Chaturdashi"),
            (11,  8, "Diwali / Deepavali"),
            (11,  9, "Govardhan Puja / Diwali Next Day"),
            (11, 14, "Children's Day"),
            (11, 23, "Karthika Somavaram"),
            (11, 24, "Karthika Purnima / Guru Nanak Jayanti"),
            (12, 24, "Christmas Eve"),
            (12, 25, "Christmas Day"),
            (12, 31, "New Year's Eve"),
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
    _add(11, 14, "Children's Day")
    _add(12, 24, "Christmas Eve")
    _add(12, 25, "Christmas Day")
    _add(12, 31, "New Year's Eve")

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


def _clean_merge_names(existing: str, new_name: str) -> str:
    """Merges new_name into existing string avoiding duplicates, substring overlaps, and clutter."""
    import re
    if not existing:
        return new_name or ""
    if not new_name:
        return existing or ""

    parts = [p.strip() for p in existing.split('/') if p.strip()]
    new_parts = [p.strip() for p in new_name.split('/') if p.strip()]

    def simplify(s: str) -> str:
        s = s.lower().replace("'s", "").replace("’s", "")
        s = re.sub(r'\(.*?\)', '', s)
        return re.sub(r'[^a-z0-9]', '', s)

    for np_item in new_parts:
        sim_np = simplify(np_item)
        if not sim_np:
            continue
        duplicate = False
        for i, p in enumerate(parts):
            sim_p = simplify(p)
            if not sim_p:
                continue
            if sim_np == sim_p:
                if len(np_item) > len(p) and '(' not in np_item:
                    parts[i] = np_item
                duplicate = True
                break
            if (len(sim_np) >= 5 and sim_np in sim_p) or (len(sim_p) >= 5 and sim_p in sim_np):
                if len(np_item) > len(p) and '(' not in np_item:
                    parts[i] = np_item
                duplicate = True
                break
            if any(k in sim_np for k in ['diwali', 'deepavali']) and any(k in sim_p for k in ['diwali', 'deepavali']):
                if 'diwali / deepavali' not in [x.lower() for x in parts]:
                    parts[i] = "Diwali / Deepavali"
                duplicate = True
                break
            if any(k in sim_np for k in ['dussehra', 'dasara']) and any(k in sim_p for k in ['dussehra', 'dasara']):
                duplicate = True
                break
            if any(k in sim_np for k in ['gurunanak', 'nanak']) and any(k in sim_p for k in ['gurunanak', 'nanak']):
                duplicate = True
                break
        if not duplicate and len(parts) < 3:
            parts.append(np_item)

    return " / ".join(parts)


def _merge_holiday_dicts(base: dict, extra: dict) -> dict:
    """Merges extra holidays into base dict, cleanly combining names without duplicates."""
    for key, name in extra.items():
        if key not in base:
            base[key] = name
        else:
            base[key] = _clean_merge_names(base[key], name)
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
                    holiday_dict[key] = _clean_merge_names(holiday_dict[key], name)

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


VERIFIED_FESTIVALS_2026 = {
    '2026-01-01': "New Year's Day",
    '2026-01-13': "Bhogi",
    '2026-01-14': "Sankranti / Pongal",
    '2026-01-15': "Kanuma",
    '2026-01-26': "Republic Day",
    '2026-02-15': "Maha Shivaratri",
    '2026-03-04': "Holi",
    '2026-03-19': "Ugadi",
    '2026-03-21': "Eid-ul-Fitr / Ramzan",
    '2026-03-27': "Sri Rama Navami",
    '2026-03-31': "Mahavir Jayanti",
    '2026-04-03': "Good Friday",
    '2026-04-14': "Dr. B. R. Ambedkar Jayanti",
    '2026-05-01': "Labour Day / May Day",
    '2026-05-27': "Eid-ul-Adha / Bakrid",
    '2026-06-02': "Telangana Formation Day",
    '2026-06-26': "Muharram",
    '2026-07-16': "Ratha Yatra",
    '2026-08-10': "Bonalu",
    '2026-08-15': "Independence Day",
    '2026-08-21': "Varalakshmi Vratham",
    '2026-08-26': "Milad-un-Nabi",
    '2026-08-28': "Raksha Bandhan",
    '2026-09-04': "Sri Krishna Janmashtami",
    '2026-09-05': "Teachers Day",
    '2026-09-14': "Vinayaka Chavithi",
    # Q4 Verified Events & Festivals
    '2026-10-02': "Mahatma Gandhi Jayanti",
    '2026-10-10': "Bathukamma Festival Begins",
    '2026-10-18': "Saddula Bathukamma",
    '2026-10-19': "Durgashtami / Maha Navami",
    '2026-10-20': "Dussehra / Vijaya Dasami",
    '2026-10-21': "Vijaya Dasami (Next Day)",
    '2026-11-01': "Andhra Pradesh Formation Day",
    '2026-11-07': "Naraka Chaturdashi",
    '2026-11-08': "Diwali / Deepavali",
    '2026-11-09': "Govardhan Puja / Diwali Next Day",
    '2026-11-14': "Children's Day",
    '2026-11-23': "Karthika Somavaram",
    '2026-11-24': "Karthika Purnima / Guru Nanak Jayanti",
    '2026-12-24': "Christmas Eve",
    '2026-12-25': "Christmas Day",
    '2026-12-31': "New Year's Eve",
}

CALIBRATED_FESTIVE_UPLIFTS = {
    # Gandhi Jayanti Long Weekend
    '2026-10-02': 1.06, '2026-10-03': 1.04,
    # Bathukamma & Dussehra Season (Oct 10 - Oct 25)
    '2026-10-10': 1.05,
    '2026-10-17': 1.08,
    '2026-10-18': 1.15,  # Saddula Bathukamma: ~150k
    '2026-10-19': 1.17,  # Maha Navami / Pre-Dussehra Departure Rush: ~155k
    '2026-10-20': 1.15,  # Dussehra / Vijaya Dasami: ~152k (Strong Festive Traffic)
    '2026-10-21': 1.18,  # Vijaya Dasami Return Rush: ~156k
    '2026-10-22': 1.16,  # Return Rush: ~154k
    '2026-10-23': 1.14,  # Return Rush: ~152k
    '2026-10-24': 1.12,  # Weekend Return: ~148k
    '2026-10-25': 1.08,
    # Diwali Season (Nov 06 - Nov 12)
    '2026-11-06': 1.06,
    '2026-11-07': 1.14,  # Naraka Chaturdashi (Pre-Diwali Rush): ~150k
    '2026-11-08': 1.14,  # Diwali / Deepavali Day: ~150k (Strong Festive Traffic)
    '2026-11-09': 1.16,  # Govardhan Puja / Return Rush: ~153k
    '2026-11-10': 1.16,  # Return Rush: ~154k
    '2026-11-11': 1.14,  # Return Rush: ~151k
    '2026-11-12': 1.08,
    # Children's Day
    '2026-11-14': 1.06,  # Children's Day Saturday: ~141k
    # Karthika Purnima
    '2026-11-23': 1.10,  # Karthika Somavaram: ~145k
    '2026-11-24': 1.16,  # Karthika Purnima / Guru Nanak Jayanti: ~154k
    '2026-11-25': 1.06,
    # Christmas & Year-End
    '2026-12-24': 1.10,  # Christmas Eve: ~147k
    '2026-12-25': 1.14,  # Christmas Day: ~152k
    '2026-12-26': 1.06,  # Boxing Day
    '2026-12-31': 1.12,  # New Year's Eve: ~149k
}


def build_full_calendar(df: pd.DataFrame, forecast_end: pd.Timestamp, future_holidays: dict = None):
    """
    Build a full daily index from data start through forecast_end, with holiday flags and names
    derived dynamically from the Python `holidays` library for India and verified Telugu regional dates.
    """
    start = pd.Timestamp(df['Date'].min())
    forecast_end = pd.Timestamp(forecast_end)
    full_dates = pd.date_range(start, forecast_end, freq='D')

    # Fetch Indian holidays dynamically for all years in the range
    in_holidays = get_indian_holidays(start.year, forecast_end.year)
    # Guarantee clean authoritative 2026 festival labels take exact precedence
    in_holidays.update(VERIFIED_FESTIVALS_2026)
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


MAJOR_TRAVEL_FESTIVALS = {
    'sankranti', 'dussehra', 'diwali', 'ugadi', 'eid',
    'bathukamma', 'maha_navami', 'karthika_purnima', 'childrens_day',
    'christmas', 'new_year'
}


def normalize_festival_name(name: str) -> str:
    """Canonical slug normalizer for Indian festivals across different sources and spellings."""
    if not name or not isinstance(name, str):
        return ""
    n = name.lower().strip()
    if 'dussehra' in n or 'dasara' in n or 'vijayadashami' in n or 'vijaya dasami' in n:
        return 'dussehra'
    if 'diwali' in n or 'deepavali' in n or 'dhanteras' in n or 'naraka' in n or 'govardhan' in n:
        return 'diwali'
    if 'sankranti' in n or 'pongal' in n or 'bhogi' in n or 'kanuma' in n:
        return 'sankranti'
    if 'ugadi' in n:
        return 'ugadi'
    if 'bathukamma' in n:
        return 'bathukamma'
    if 'karthika' in n or 'kartika' in n:
        return 'karthika_purnima'
    if 'children' in n:
        return 'childrens_day'
    if 'bonalu' in n:
        return 'bonalu'
    if 'janmashtami' in n or 'krishna' in n:
        return 'janmashtami'
    if 'chavithi' in n or 'ganesh' in n or 'vinayaka' in n:
        return 'vinayaka_chavithi'
    if 'christmas' in n:
        return 'christmas'
    if 'new year' in n:
        return 'new_year'
    if 'eid' in n or 'ramzan' in n or 'bakrid' in n or 'milad' in n:
        return 'eid'
    if 'holi' in n:
        return 'holi'
    if 'gandhi' in n:
        return 'gandhi_jayanti'
    if 'republic' in n:
        return 'republic_day'
    if 'independence' in n:
        return 'independence_day'
    if 'formation' in n:
        return 'formation_day'
    return n


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

        # Major travel festival indicators (Sankranti, Dussehra, Diwali, Ugadi, Eid)
        norm_names = np.array([normalize_festival_name(n) for n in self.hol_name.to_numpy()])
        self.is_major_travel_festival = np.isin(norm_names, list(MAJOR_TRAVEL_FESTIVALS)).astype(int)
        rush_window = np.zeros(self.n, dtype=int)
        for i in range(self.n):
            if self.is_major_travel_festival[i] == 1:
                rush_window[i] = 1
            elif self.days_to_hol[i] in [1, 2, 3] and (i + int(self.days_to_hol[i])) < self.n and self.is_major_travel_festival[i + int(self.days_to_hol[i])] == 1:
                rush_window[i] = 1
            elif self.days_since_hol[i] in [1, 2] and (i - int(self.days_since_hol[i])) >= 0 and self.is_major_travel_festival[i - int(self.days_since_hol[i])] == 1:
                rush_window[i] = 1
        self.travel_rush_window = rush_window

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
            'is_summer': self.is_summer, 'is_monsoon': self.is_monsoon,
            'is_major_travel_festival': self.is_major_travel_festival,
            'travel_rush_window': self.travel_rush_window,
            'week_sin': self.week_sin, 'week_cos': self.week_cos, 'doy': self.doy,
        })


LAGS = [1, 2, 3, 7, 14, 21, 28, 30, 364, 365, 728, 730]
ROLL_WINDOWS = [3, 7, 14, 30, 60]
ROLL_STD_WINDOWS = [7, 14, 30]

TARGET_DEP_FEATURES = (
    [f'lag_{k}' for k in LAGS]
    + [f'roll_mean_{w}' for w in ROLL_WINDOWS]
    + [f'roll_std_{w}' for w in ROLL_STD_WINDOWS]
    + ['same_dow_roll_mean_4', 'trend_7_30', 'hist_month_dow_mean', 'hist_month_mean']
)

CALENDAR_FEATURES = [
    'dow', 'month', 'day', 'is_weekend', 'quarter', 'weekofyear',
    'month_sin', 'month_cos', 'dow_sin', 'dow_cos', 'doy_sin', 'doy_cos', 'week_sin', 'week_cos',
    'is_month_start', 'is_month_end', 'is_payday_window',
    'is_holiday', 'days_since_holiday', 'days_to_holiday',
    'is_day_before_holiday', 'is_pre_holiday_2d', 'is_pre_holiday_3d',
    'is_day_after_holiday', 'is_post_holiday_2d',
    'long_weekend',
    'is_friday', 'is_monday', 'is_tue', 'is_wed', 'is_thu', 'is_sat',
    'holiday_on_weekend', 'holiday_adjacent_weekend',
    'is_pre_holiday_friday', 'is_post_holiday_monday',
    'is_summer', 'is_monsoon',
    'is_major_travel_festival', 'travel_rush_window',
]

HOLIDAY_EFFECT_FEATURES = ['named_holiday_ratio', 'named_holiday_adjusted_baseline']
SEASONAL_FEATURES = ['doy_seasonal_index']

ALL_FEATURES = CALENDAR_FEATURES + TARGET_DEP_FEATURES + HOLIDAY_EFFECT_FEATURES + SEASONAL_FEATURES
ALL_FEATURES_BLIND = ALL_FEATURES


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


def target_features_for_index(values, i, cf=None, holiday_ratio=1.0, seasonal_index_arr=None,
                              hist_mdow_arr=None, hist_m_arr=None):
    feats = {}
    # Short and medium lags
    for k in [1, 2, 3, 7, 14, 21, 28, 30]:
        j = i - k
        feats[f'lag_{k}'] = values[j] if j >= 0 else np.nan

    # Multi-year lags with fallback to 1-year lag or historical month-dow mean
    m_dow_val = float(hist_mdow_arr[i]) if hist_mdow_arr is not None else (values[i - 7] if i >= 7 else 10000.0)
    m_val = float(hist_m_arr[i]) if hist_m_arr is not None else (values[i - 30] if i >= 30 else 10000.0)

    l364 = values[i - 364] if i >= 364 else np.nan
    l365 = values[i - 365] if i >= 365 else np.nan
    feats['lag_364'] = l364 if not np.isnan(l364) else m_dow_val
    feats['lag_365'] = l365 if not np.isnan(l365) else m_val
    feats['lag_728'] = values[i - 728] if i >= 728 else feats['lag_364']
    feats['lag_730'] = values[i - 730] if i >= 730 else feats['lag_365']

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

    roll7 = feats['roll_mean_7']
    roll30 = feats['roll_mean_30']
    feats['trend_7_30'] = (roll7 - roll30) if (not np.isnan(roll7) and not np.isnan(roll30)) else 0.0

    feats['hist_month_dow_mean'] = m_dow_val
    feats['hist_month_mean'] = m_val
    feats['doy_seasonal_index'] = float(seasonal_index_arr[i]) if seasonal_index_arr is not None else 1.0

    return feats


def build_target_dependent_matrix(values, indices, cf=None, holiday_ratio=1.0, seasonal_index_arr=None,
                                  hist_mdow_arr=None, hist_m_arr=None):
    rows = [target_features_for_index(values, i, cf, holiday_ratio, seasonal_index_arr, hist_mdow_arr, hist_m_arr)
            for i in indices]
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
