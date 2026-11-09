# Data Dictionary

All objects live in the Neon PostgreSQL database, in three schemas:

| Schema | Role | Written by |
|---|---|---|
| `raw` | Exact copy of the Elia API (dataset `ods134`). Never modified by hand. | `src/pipeline.py` (upsert) |
| `clean` | Readable names, harmonised empty values, Belgian local time, business columns. | `sql/02_create_clean_view.sql` |
| `analytics` | One view per analysis need, ready for Power BI. | `sql/03_` to `sql/08_` |
| `forecast` | Forecast backtest results and their error summaries. | `src/forecast.py` (table), `sql/09_` and `sql/10_` |

Conventions:

* Timestamps are stored in UTC. Columns ending in `_local` are in Belgian local time (`Europe/Brussels`), daylight saving time included.
* Units are part of the column name: `_mw` (average power over the quarter-hour), `_mwh` (energy), `_eur_mwh` (price).
* `clean` and `analytics` are views: they are always up to date with `raw`, with no refresh step.

---

## raw.imbalance_prices

Table. One row per quarter-hour (UTC). Primary key: `datetime`.

| Column | Type | Unit | Description |
|---|---|---|---|
| `datetime` | TIMESTAMPTZ | UTC | Start of the quarter-hour. Primary key. |
| `resolutioncode` | TEXT | | Time resolution, always `PT15M`. |
| `qualitystatus` | TEXT | | `NotValidated`, `DataIssue` or `Validated`. Month M is validated after the 15th of month M+1. |
| `ace` | NUMERIC | MW | Area Control Error: imbalance remaining after Elia's corrections. |
| `systemimbalance` | NUMERIC | MW | System imbalance before correction. Negative: short system. Positive: long system. |
| `alpha` | NUMERIC | EUR/MWh | Penalty component, added when the grid has been under stress. |
| `alpha_prime` | NUMERIC | EUR/MWh | Reserve-sharing component, neutralised since the MARI go-live. Null early in the dataset, 0 afterwards. |
| `marginalincrementalprice` | NUMERIC | EUR/MWh | Price of the last upward activation in the quarter-hour. |
| `marginaldecrementalprice` | NUMERIC | EUR/MWh | Price of the last downward activation in the quarter-hour. Can be negative. |
| `imbalanceprice` | NUMERIC | EUR/MWh | Published imbalance price. |
| `loaded_at` | TIMESTAMPTZ | UTC | Last time the row was inserted or updated by the pipeline. |

---

## clean.imbalance_prices

View on `raw.imbalance_prices`. Same rows, one per quarter-hour. `resolutioncode` is not kept (constant).

| Column | Type | Unit | Description |
|---|---|---|---|
| `datetime_utc` | TIMESTAMPTZ | UTC | Start of the quarter-hour. |
| `quality_status` | TEXT | | `NotValidated`, `DataIssue` or `Validated`. |
| `ace_mw` | NUMERIC | MW | Area Control Error. |
| `system_imbalance_mw` | NUMERIC | MW | System imbalance. Negative: short system. Positive: long system. |
| `alpha_eur_mwh` | NUMERIC | EUR/MWh | Alpha component. |
| `marginal_incremental_price_eur_mwh` | NUMERIC | EUR/MWh | Price of the last upward activation. |
| `marginal_decremental_price_eur_mwh` | NUMERIC | EUR/MWh | Price of the last downward activation. |
| `imbalance_price_eur_mwh` | NUMERIC | EUR/MWh | Published imbalance price. **Target variable.** |
| `loaded_at` | TIMESTAMPTZ | UTC | Last load time of the row. |
| `alpha_prime_eur_mwh` | NUMERIC | EUR/MWh | Alpha prime, with null replaced by 0. |
| `datetime_local` | TIMESTAMP | Belgian time | Start of the quarter-hour in Belgian local time. Appears twice for 02:00 to 02:45 on the autumn clock change. |
| `date_local` | DATE | Belgian time | Belgian calendar day. |
| `hour_local` | INTEGER | | Belgian hour, 0 to 23. |
| `weekday_local` | INTEGER | | ISO day of the week: 1 = Monday, 7 = Sunday. |
| `month_local` | INTEGER | | Month, 1 to 12. |
| `season` | TEXT | | Meteorological season (whole months): `winter` (Dec to Feb), `spring` (Mar to May), `summer` (Jun to Aug), `autumn` (Sep to Nov). |
| `system_state` | TEXT | | `short` if system imbalance < 0, otherwise `long` (an imbalance of exactly 0 counts as long). |
| `is_validated` | BOOLEAN | | True when `quality_status` is `Validated`. |
| `imbalance_energy_mwh` | NUMERIC | MWh | Energy of the system imbalance over the quarter-hour: MW × 0.25 h. |
| `recomputed_price_eur_mwh` | NUMERIC | EUR/MWh | Price rebuilt from its components: incremental + alpha (short system), decremental − alpha (long system). Used by the quality tests only. |

---

## analytics.public_holidays

View. One row per Belgian national public holiday, 2024 to 2027.

| Column | Type | Description |
|---|---|---|
| `holiday_date` | DATE | Date of the holiday. |
| `holiday_name` | TEXT | English name (e.g. `Easter Monday`). |

Movable holidays are derived from Easter: Easter Monday (+1 day), Ascension Day (+39 days), Whit Monday (+50 days). The list must be extended before the data reaches 2028 (checked by `test_09`).

---

## analytics.calendar

View. One row per Belgian calendar day present in the data. Date table for Power BI.

| Column | Type | Description |
|---|---|---|
| `date_local` | DATE | Belgian calendar day. Key for joins. |
| `year` | INTEGER | Year. |
| `month` | INTEGER | Month, 1 to 12. |
| `month_name` | TEXT | Month name in English. |
| `weekday` | INTEGER | ISO day of the week: 1 = Monday, 7 = Sunday. |
| `weekday_name` | TEXT | Day name in English. |
| `is_weekend` | BOOLEAN | True on Saturday and Sunday. |
| `is_holiday` | BOOLEAN | True on a Belgian national public holiday. |
| `holiday_name` | TEXT | Holiday name, or null. |
| `day_type` | TEXT | `holiday`, `weekend` or `weekday`. A holiday on a weekend counts as `holiday`. |
| `season` | TEXT | Meteorological season. |
| `season_label` | TEXT | Season with its year, e.g. `spring 2026`. December belongs to the following winter: `winter 2025-2026` covers December 2025 to February 2026. |

---

## analytics.price_thresholds

View. One row: the definitions of an extreme price, shared by all analytics views.

| Column | Type | Unit | Description |
|---|---|---|---|
| `negative_threshold_eur_mwh` | NUMERIC | EUR/MWh | A price below this value (0) is a **negative price**: risk for a long BRP. |
| `high_threshold_eur_mwh` | NUMERIC | EUR/MWh | 95th percentile of all published prices. A price above it is a **high price**: risk for a short BRP. Recomputed on the full history, so it moves slightly as data grows (278.64 EUR/MWh on 9 November 2026). |

---

## analytics.price_profile

View. One row per Belgian hour × day type × season.

| Column | Type | Unit | Description |
|---|---|---|---|
| `hour_local` | INTEGER | | Belgian hour, 0 to 23. |
| `day_type` | TEXT | | `weekday`, `weekend` or `holiday`. |
| `season` | TEXT | | Meteorological season. |
| `nb_quarter_hours` | INTEGER | | Number of quarter-hours in the group. |
| `avg_price_eur_mwh` | NUMERIC | EUR/MWh | Mean price. Includes extreme prices: reflects the cost over the period. |
| `median_price_eur_mwh` | NUMERIC | EUR/MWh | Median price: the typical price of the slot. |
| `p05_price_eur_mwh` | NUMERIC | EUR/MWh | 5th percentile. |
| `p95_price_eur_mwh` | NUMERIC | EUR/MWh | 95th percentile. |
| `stddev_price_eur_mwh` | NUMERIC | EUR/MWh | Sample standard deviation: volatility of the slot. |
| `pct_negative_price` | NUMERIC | % | Share of quarter-hours with a negative price. |
| `pct_high_price` | NUMERIC | % | Share of quarter-hours with a high price. |
| `pct_short_system` | NUMERIC | % | Share of quarter-hours with a short system. |

---

## analytics.daily_summary

View. One row per Belgian calendar day.

| Column | Type | Unit | Description |
|---|---|---|---|
| `date_local` | DATE | | Belgian calendar day. |
| `day_type` | TEXT | | `weekday`, `weekend` or `holiday`. |
| `season` | TEXT | | Meteorological season. |
| `season_label` | TEXT | | Season with its year. |
| `nb_quarter_hours` | INTEGER | | Normally 96. 92 on the spring clock change, 100 on the autumn clock change, fewer on the first and last days of the data. |
| `avg_price_eur_mwh` | NUMERIC | EUR/MWh | Mean price of the day. |
| `min_price_eur_mwh` | NUMERIC | EUR/MWh | Lowest price of the day. |
| `max_price_eur_mwh` | NUMERIC | EUR/MWh | Highest price of the day. |
| `stddev_price_eur_mwh` | NUMERIC | EUR/MWh | Volatility of the day. |
| `nb_negative_prices` | INTEGER | | Number of quarter-hours with a negative price. |
| `nb_high_prices` | INTEGER | | Number of quarter-hours with a high price. |
| `pct_short_system` | NUMERIC | % | Share of quarter-hours with a short system. |
| `is_fully_validated` | BOOLEAN | | True when every quarter-hour of the day is validated. |

---

## analytics.extreme_prices

View. One row per quarter-hour with a negative or high price.

| Column | Type | Unit | Description |
|---|---|---|---|
| `datetime_utc` | TIMESTAMPTZ | UTC | Start of the quarter-hour. |
| `datetime_local` | TIMESTAMP | Belgian time | Start of the quarter-hour in Belgian time. |
| `date_local` | DATE | | Belgian calendar day. |
| `hour_local` | INTEGER | | Belgian hour. |
| `day_type` | TEXT | | `weekday`, `weekend` or `holiday`. |
| `season` | TEXT | | Meteorological season. |
| `season_label` | TEXT | | Season with its year. |
| `extreme_type` | TEXT | | `negative` or `high`. |
| `imbalance_price_eur_mwh` | NUMERIC | EUR/MWh | Published price. |
| `system_imbalance_mw` | NUMERIC | MW | System imbalance. |
| `system_state` | TEXT | | `short` or `long`. |
| `is_validated` | BOOLEAN | | True when the price is validated. |

---

## analytics.hourly_prices

View. One row per Belgian day × hour. Input of the forecast.

| Column | Type | Unit | Description |
|---|---|---|---|
| `date_local` | DATE | | Belgian calendar day. |
| `hour_local` | INTEGER | | Belgian hour, 0 to 23. Hour 2 is missing on the spring clock change, and averages 8 quarter-hours on the autumn one. |
| `day_type` | TEXT | | `weekday`, `weekend` or `holiday`. |
| `avg_price_eur_mwh` | NUMERIC | EUR/MWh | Mean price of the quarter-hours of the hour. |
| `is_validated` | BOOLEAN | | True when every quarter-hour of the hour is validated. |

---

## forecast.backtest_results

Table, written by `src/forecast.py`. One row per model × forecast day × hour. Each run of a model replaces its rows. Primary key: `model_name`, `date_local`, `hour_local`.

| Column | Type | Unit | Description |
|---|---|---|---|
| `model_name` | TEXT | | Forecast settings, e.g. `reference_28d`, `A_window_56d`. |
| `date_local` | DATE | | Forecast day (Belgian). |
| `hour_local` | INTEGER | | Belgian hour. |
| `day_type` | TEXT | | `weekday`, `weekend` or `holiday`. |
| `actual_eur_mwh` | NUMERIC | EUR/MWh | Actual average price of the hour. |
| `forecast_eur_mwh` | NUMERIC | EUR/MWh | Forecast made with data known up to two days before. |
| `abs_error_eur_mwh` | NUMERIC | EUR/MWh | Absolute difference between actual and forecast. |
| `created_at` | TIMESTAMPTZ | UTC | Time the row was written. |

---

## forecast.model_summary

View. One row per model.

| Column | Type | Unit | Description |
|---|---|---|---|
| `model_name` | TEXT | | Forecast settings. |
| `first_day`, `last_day` | DATE | | Tested period. |
| `nb_hours` | INTEGER | | Number of tested hours. |
| `mae_eur_mwh` | NUMERIC | EUR/MWh | Mean absolute error: main metric. |
| `rmse_eur_mwh` | NUMERIC | EUR/MWh | Root mean squared error: dominated by a few extreme hours, given for reference. |

---

## forecast.error_by_hour_season

View. One row per model × Belgian hour × season.

| Column | Type | Unit | Description |
|---|---|---|---|
| `model_name` | TEXT | | Forecast settings. |
| `hour_local` | INTEGER | | Belgian hour. |
| `season` | TEXT | | Meteorological season. |
| `nb_hours` | INTEGER | | Number of tested hours in the group. |
| `mae_eur_mwh` | NUMERIC | EUR/MWh | Mean absolute error of the group. |
| `avg_actual_eur_mwh` | NUMERIC | EUR/MWh | Mean actual price. |
| `avg_forecast_eur_mwh` | NUMERIC | EUR/MWh | Mean forecast. |

---

## Known data particularities

Found by the quality tests (`tests/sql/`) and kept in the data:

* **Price not matching its components.** On 2024-08-30 at 12:15 UTC (validated row, long system of +618.7 MW), the published price is −221 EUR/MWh while the components give −204.509 EUR/MWh (gap of 16.49 EUR/MWh). The cause is not visible in the published data. It is the only case among more than 86,000 rows, and is listed as a known exception in `test_04`.
* **Price floor.** On 2026-04-06 (Easter Monday), from 13:45 to 14:45 Belgian time, the price was exactly −15,000 EUR/MWh for five consecutive quarter-hours, with a long system and the decremental price at the same value. This is most likely a technical price limit. The rows are real extreme values and are kept.
* **Belgian day boundaries.** Elia's days and months follow Belgian time. In summer, 22:00 UTC on the last day of a month is already the next month in Brussels: monthly figures must be computed on `date_local`, not on the UTC date.
