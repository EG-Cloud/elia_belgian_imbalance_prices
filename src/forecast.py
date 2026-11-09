import logging
from datetime import date, timedelta

import pandas as pd

from db import get_connection

logger = logging.getLogger(__name__)

# On the morning of day D, only data up to D-2 is complete
DATA_LAG_DAYS = 2

# Validation period: used to choose between forecast settings
VALIDATION_START = date(2025, 7, 1)
VALIDATION_END = date(2025, 9, 30)

# Test period: 12 full months of validated data, used once for the final result
TEST_START = date(2025, 10, 1)
TEST_END = date(2026, 9, 30)

# Reference to beat: median of the same hour over the last 4 weeks, same kind of day
REFERENCE_SETTINGS = {"name": "reference_28d", "long_window_days": 28, "short_window_days": 7, "short_weight": 0.0}

# Candidates compared on the validation period.
# Option A: the reference with another window. Option B: blend of a short and a long window.
CANDIDATE_SETTINGS = [
    {"name": "A_window_7d",  "long_window_days": 7,  "short_window_days": 7, "short_weight": 0.0},
    {"name": "A_window_14d", "long_window_days": 14, "short_window_days": 7, "short_weight": 0.0},
    {"name": "A_window_28d", "long_window_days": 28, "short_window_days": 7, "short_weight": 0.0},
    {"name": "A_window_56d", "long_window_days": 56, "short_window_days": 7, "short_weight": 0.0},
    {"name": "B_28d_7d_w25", "long_window_days": 28, "short_window_days": 7, "short_weight": 0.25},
    {"name": "B_28d_7d_w50", "long_window_days": 28, "short_window_days": 7, "short_weight": 0.50},
    {"name": "B_28d_7d_w75", "long_window_days": 28, "short_window_days": 7, "short_weight": 0.75},
    {"name": "B_56d_7d_w25", "long_window_days": 56, "short_window_days": 7, "short_weight": 0.25},
    {"name": "B_56d_7d_w50", "long_window_days": 56, "short_window_days": 7, "short_weight": 0.50},
    {"name": "B_56d_7d_w75", "long_window_days": 56, "short_window_days": 7, "short_weight": 0.75},
]

HOURLY_PRICES_QUERY = """
    SELECT
        date_local,
        hour_local,
        day_type,
        avg_price_eur_mwh,
        is_validated
    FROM analytics.hourly_prices
    ORDER BY date_local, hour_local;
"""


def load_hourly_prices():
    """
    Load the average imbalance price per Belgian day and hour.

    Returns:
        pd.DataFrame: one row per day and hour, sorted by date then hour, with columns
            date_local (datetime.date), hour_local (int, 0 to 23),
            day_type (str: weekday, weekend or holiday),
            avg_price_eur_mwh (float), is_validated (bool).
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(HOURLY_PRICES_QUERY)
            rows = cur.fetchall()

            column_names = []
            for column in cur.description:
                column_names.append(column.name)

    hourly_prices = pd.DataFrame(rows, columns=column_names)

    # NUMERIC values arrive as Decimal: convert to float for calculations
    hourly_prices["avg_price_eur_mwh"] = hourly_prices["avg_price_eur_mwh"].astype(float)

    return hourly_prices


def median_profile(hourly_prices, target_day, is_working_day, window_days):
    """
    Median price of each hour over a window of known data, for one kind of day.

    The window ends DATA_LAG_DAYS days before the target day and covers
    window_days days. Holidays are grouped with weekends.

    Args:
        hourly_prices (pd.DataFrame): output of load_hourly_prices.
        target_day (date): the day to forecast.
        is_working_day (bool): True for a weekday, False for a weekend or holiday.
        window_days (int): number of days in the window.

    Returns:
        pd.DataFrame: one row per hour, with columns hour_local (int, 0 to 23)
            and median_eur_mwh (float).
    """

    window_end = target_day - timedelta(days=DATA_LAG_DAYS)
    window_start = window_end - timedelta(days=window_days - 1)

    in_window = hourly_prices[
        (hourly_prices["date_local"] >= window_start)
        & (hourly_prices["date_local"] <= window_end)
    ]

    # Too few holidays in a few weeks to stand alone
    if is_working_day:
        same_kind = in_window[in_window["day_type"] == "weekday"]
    else:
        same_kind = in_window[in_window["day_type"].isin(["weekend", "holiday"])]

    medians = same_kind.groupby("hour_local")["avg_price_eur_mwh"].median()

    profile = medians.reset_index()
    profile = profile.rename(columns={"avg_price_eur_mwh": "median_eur_mwh"})

    return profile


def forecast_day(hourly_prices, target_day, is_working_day, settings):
    """
    Forecast the 24 hourly prices of a day.

    forecast = short_weight x short-window median + (1 - short_weight) x long-window median.
    With short_weight = 0, this is the plain median profile of the long window.

    Args:
        hourly_prices (pd.DataFrame): output of load_hourly_prices.
        target_day (date): the day to forecast.
        is_working_day (bool): True for a weekday, False for a weekend or holiday.
        settings (dict): long_window_days (int), short_window_days (int),
            short_weight (float, 0 to 1).

    Returns:
        pd.DataFrame: one row per hour, with columns hour_local (int, 0 to 23)
            and forecast_eur_mwh (float).
    """

    long_profile = median_profile(hourly_prices, target_day, is_working_day, settings["long_window_days"])
    long_profile = long_profile.rename(columns={"median_eur_mwh": "long_eur_mwh"})

    short_weight = settings["short_weight"]

    if short_weight == 0:
        forecast = long_profile
        forecast["forecast_eur_mwh"] = forecast["long_eur_mwh"]
    else:
        short_profile = median_profile(hourly_prices, target_day, is_working_day, settings["short_window_days"])
        short_profile = short_profile.rename(columns={"median_eur_mwh": "short_eur_mwh"})

        # Inner join: an hour missing from the short window gets no forecast
        forecast = long_profile.merge(short_profile, on="hour_local")
        forecast["forecast_eur_mwh"] = (
            short_weight * forecast["short_eur_mwh"]
            + (1 - short_weight) * forecast["long_eur_mwh"]
        )

    return forecast[["hour_local", "forecast_eur_mwh"]]


def backtest(hourly_prices, start_day, end_day, settings):
    """
    Replay a forecast day by day and compare it with actual prices.

    Each day is forecast with data known on that day only (see median_profile),
    so the evaluation contains no future information.

    Args:
        hourly_prices (pd.DataFrame): output of load_hourly_prices.
        start_day (date): first day to forecast (included).
        end_day (date): last day to forecast (included).
        settings (dict): forecast settings, see forecast_day.

    Returns:
        pd.DataFrame: one row per tested hour, with columns date_local (date),
            hour_local (int), day_type (str), avg_price_eur_mwh (float, actual price),
            is_validated (bool), forecast_eur_mwh (float) and abs_error (float, EUR/MWh).
    """

    all_days = []
    current_day = start_day

    while current_day <= end_day:

        actual = hourly_prices[hourly_prices["date_local"] == current_day]

        # Days without data are skipped
        if not actual.empty:
            is_working_day = actual["day_type"].iloc[0] == "weekday"

            forecast = forecast_day(hourly_prices, current_day, is_working_day, settings)

            day_result = actual.merge(forecast, on="hour_local")
            all_days.append(day_result)

        current_day = current_day + timedelta(days=1)

    results = pd.concat(all_days, ignore_index=True)
    results["abs_error"] = (results["avg_price_eur_mwh"] - results["forecast_eur_mwh"]).abs()

    return results


def choose_best_settings(hourly_prices):
    """
    Compare all candidate settings on the validation period and keep the best.

    Args:
        hourly_prices (pd.DataFrame): output of load_hourly_prices.

    Returns:
        dict: the candidate settings with the lowest validation MAE.
    """

    best_settings = None
    best_mae = None

    for settings in CANDIDATE_SETTINGS:
        results = backtest(hourly_prices, VALIDATION_START, VALIDATION_END, settings)
        mae = results["abs_error"].mean()
        logger.info(f"Validation | {settings['name']:<14} | MAE = {mae:.2f} EUR/MWh")

        if best_mae is None or mae < best_mae:
            best_mae = mae
            best_settings = settings

    logger.info(f"Best on validation: {best_settings['name']} (MAE = {best_mae:.2f} EUR/MWh)")
    return best_settings


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    hourly_prices = load_hourly_prices()

    # 1. Choose the settings on the validation period only
    best_settings = choose_best_settings(hourly_prices)

    # 2. Evaluate the reference and the chosen settings once, on the test period
    reference_results = backtest(hourly_prices, TEST_START, TEST_END, REFERENCE_SETTINGS)
    best_results = backtest(hourly_prices, TEST_START, TEST_END, best_settings)

    reference_mae = reference_results["abs_error"].mean()
    best_mae = best_results["abs_error"].mean()
    skill = 1 - best_mae / reference_mae

    logger.info(f"Test | {REFERENCE_SETTINGS['name']:<14} | {len(reference_results)} hours | MAE = {reference_mae:.2f} EUR/MWh")
    logger.info(f"Test | {best_settings['name']:<14} | {len(best_results)} hours | MAE = {best_mae:.2f} EUR/MWh")
    logger.info(f"Skill vs reference: {skill:.1%}")
