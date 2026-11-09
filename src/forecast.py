import logging
from datetime import date, timedelta

import pandas as pd

from db import get_connection

logger = logging.getLogger(__name__)

# Baseline: median of the same hour over the last 4 weeks, same kind of day
BASELINE_WINDOW_DAYS = 28

# On the morning of day D, only data up to D-2 is complete
DATA_LAG_DAYS = 2

# Backtest period: 12 full months of validated data, fixed for reproducible results
TEST_START = date(2025, 10, 1)
TEST_END = date(2026, 9, 30)

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


def baseline_forecast(hourly_prices, target_day, is_working_day):
    """
    Forecast the 24 hourly prices of a day with the baseline method.

    Each hour is forecast as the median price of the same hour over the last
    BASELINE_WINDOW_DAYS days of known data, using only days of the same kind
    (working day, or weekend and holiday). Known data stops DATA_LAG_DAYS days
    before the target day.

    Args:
        hourly_prices (pd.DataFrame): output of load_hourly_prices.
        target_day (date): the day to forecast.
        is_working_day (bool): True for a weekday, False for a weekend or holiday.

    Returns:
        pd.DataFrame: one row per hour, with columns hour_local (int, 0 to 23)
            and forecast_eur_mwh (float).
    """

    # Window of known data, both bounds included
    window_end = target_day - timedelta(days=DATA_LAG_DAYS)
    window_start = window_end - timedelta(days=BASELINE_WINDOW_DAYS - 1)

    in_window = hourly_prices[
        (hourly_prices["date_local"] >= window_start)
        & (hourly_prices["date_local"] <= window_end)
    ]

    # Holidays are grouped with weekends: too few holidays in 4 weeks to stand alone
    if is_working_day:
        same_kind = in_window[in_window["day_type"] == "weekday"]
    else:
        same_kind = in_window[in_window["day_type"].isin(["weekend", "holiday"])]

    medians = same_kind.groupby("hour_local")["avg_price_eur_mwh"].median()

    forecast = medians.reset_index()
    forecast = forecast.rename(columns={"avg_price_eur_mwh": "forecast_eur_mwh"})

    return forecast


def backtest_baseline(hourly_prices, start_day, end_day):
    """
    Replay the baseline forecast day by day and compare it with actual prices.

    For each day of the period, the forecast only uses data known on that day
    (see baseline_forecast), so the evaluation contains no future information.

    Args:
        hourly_prices (pd.DataFrame): output of load_hourly_prices.
        start_day (date): first day to forecast (included).
        end_day (date): last day to forecast (included).

    Returns:
        pd.DataFrame: one row per tested hour, with columns date_local (date),
            hour_local (int), day_type (str), avg_price_eur_mwh (float, actual price),
            forecast_eur_mwh (float) and abs_error (float, EUR/MWh).
    """

    all_days = []
    current_day = start_day

    while current_day <= end_day:

        actual = hourly_prices[hourly_prices["date_local"] == current_day]

        # Days without data are skipped
        if not actual.empty:
            is_working_day = actual["day_type"].iloc[0] == "weekday"

            forecast = baseline_forecast(hourly_prices, current_day, is_working_day)

            day_result = actual.merge(forecast, on="hour_local")
            all_days.append(day_result)

        current_day = current_day + timedelta(days=1)

    results = pd.concat(all_days, ignore_index=True)
    results["abs_error"] = (results["avg_price_eur_mwh"] - results["forecast_eur_mwh"]).abs()

    return results

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    hourly_prices = load_hourly_prices()
    results = backtest_baseline(hourly_prices, TEST_START, TEST_END)
    mae = results["abs_error"].mean()
    logger.info(f"Baseline: {len(results)} hours tested, MAE = {mae:.2f} EUR/MWh")