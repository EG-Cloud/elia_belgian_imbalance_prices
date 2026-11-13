# Belgian Imbalance Prices

Automated pipeline and analysis of Belgian electricity imbalance prices (Elia Open Data).

> **Status:** complete. The pipeline runs every day on GitHub Actions; the analysis, forecast evaluation and Power BI report cover data up to November 2026.
> See [docs/feasibility_note.md](docs/feasibility_note.md) for the project scope and [docs/data_dictionary.md](docs/data_dictionary.md) for every table, view and column.

---

## Why this project

In Belgium, every **Balance Responsible Party (BRP)** commits the day before to a balanced schedule for each quarter-hour. Any deviation is settled afterwards at the **imbalance price**, published by Elia, the Belgian transmission system operator. This price changes every 15 minutes, can spike to several hundred euros per MWh, and can also turn negative.

**Business question:** a BRP can use this analysis to identify the time slots (hour, day, season) where an imbalance costs the most, and focus its forecasting efforts there.

Analysis questions:

1. At which hours, days and seasons is the imbalance price highest, or most volatile?
2. How often do extreme prices occur (both high and negative), and when?
3. Can these time slots be anticipated better than with a simple hourly average?

## What this project demonstrates

| Skill | How |
|---|---|
| API extraction | Python collection from the Elia Open Data API, with explicit filtering and sorting |
| Cloud database | Hosted PostgreSQL on Neon |
| Automation | Daily scheduled run on GitHub Actions, no local machine needed |
| Data engineering | Idempotent upserts, batch loading, retries on temporary errors, logging |
| Security | No credentials in the code or the repository (`.env` locally, GitHub secret in CI) |
| SQL modelling | Raw, clean and analytics layers in PostgreSQL views, with 10 automated data quality tests |
| Reporting | Three-page Power BI report built on the analytics views |
| Forecast evaluation | Day-ahead hourly forecast, rolling backtest without look-ahead, settings chosen on a separate validation period, honest comparison with a baseline |

## Architecture

```mermaid
flowchart LR
    A[Elia Open Data API<br/>dataset ods134] -->|requests, one call per day| B[Python pipeline<br/>src/]
    C[GitHub Actions<br/>daily schedule] -->|runs| B
    B -->|upsert| D[(Neon PostgreSQL<br/>raw)]
    D --> E[Views<br/>clean / analytics]
    E --> G{{Quality tests<br/>tests/sql}}
    E --> F[Power BI report]
```

## Data source

| Item | Value |
|---|---|
| Publisher | Elia Transmission Belgium, [Open Data portal](https://opendata.elia.be) |
| Dataset | `ods134`: imbalance prices per quarter-hour |
| Coverage | From 22 May 2024 (Belgian go-live on the European MARI platform) |
| Granularity | 15 minutes, 96 rows per UTC day |
| Volume | About 85,800 rows (early November 2026), growing by 96 rows per day |
| Access | Public API, no key required |

The dataset starts at the MARI go-live because the price calculation method changed on that date. Earlier data has a different structure and is out of scope.

### Key columns

| Column | Unit | Meaning |
|---|---|---|
| `datetime` | UTC timestamp | Start of the quarter-hour |
| `qualitystatus` | text | `NotValidated`, `DataIssue` or `Validated` |
| `systemimbalance` | MW | System imbalance before correction. Negative: short system. Positive: long system |
| `marginalincrementalprice` | EUR/MWh | Price of the last upward activation |
| `marginaldecrementalprice` | EUR/MWh | Price of the last downward activation |
| `alpha` | EUR/MWh | Penalty component added when the grid is under stress |
| `imbalanceprice` | EUR/MWh | **Target variable**: final imbalance price |

Price logic, verified on real rows: short system, price = incremental price + alpha; long system, price = decremental price − alpha.

## Pipeline design

**One API call per day.** A UTC day holds 96 rows, below the API limit of 100 records per call, so each day is fetched with a single filtered request.

**Batch loading.** Periods are split into batches of 30 days. Each batch is fetched and saved right away, so a failure only loses the current batch.

**Idempotent upsert.** Rows are written with `INSERT ... ON CONFLICT (datetime) DO UPDATE`. Running the pipeline several times on the same days never creates duplicates, and updated values replace older ones.

**Daily 50-day window.** Elia validates the data of month M after the 15th of month M+1, so a value can change up to about 45 days after publication. Every daily run reloads the last 50 days: new days are inserted, recent days are updated with their validated values, and missed runs are caught up automatically.

**Retries and failure handling.** Network errors and server errors (5xx) are retried up to 3 times, with a pause between attempts. Request errors (4xx) are not retried. Any final failure is logged with its full traceback, and the run exits with code 1 so that GitHub Actions marks it as failed.

**Time zones.** Timestamps are stored in UTC (`TIMESTAMPTZ`): no duplicated or missing quarter-hours on daylight saving days. Analysis is done in Belgian time (`Europe/Brussels`), because Elia's days and months follow Belgian time.

## Power BI report

The report ([`powerbi/elia_imbalance_prices.pbix`](powerbi/elia_imbalance_prices.pbix)) answers the business question in three pages.

**1. Overview**: average price, share of negative and high prices, daily price over the whole period, and the share of extreme quarter-hours per month.

![Overview page](docs/images/overview.png)

**2. When is an imbalance most expensive?**: price profile by Belgian hour, filtered by day type and season, with a heat map of negative prices by hour and season.

![Risk by hour page](docs/images/risk_by_hour.png)

**3. Can the price be forecast the day before?**: error of the reference and of the best model, actual against forecast prices for a chosen day, and a heat map of the forecast error by hour and season.

![Forecast page](docs/images/forecast.png)

The report uses Import mode on the `analytics` and `forecast` views only. To refresh it, open the file in Power BI Desktop and enter your own database credentials.

## Data model

| Layer | Objects | Role |
|---|---|---|
| `raw` | `imbalance_prices` (table) | Exact copy of the API, written by the pipeline |
| `clean` | `imbalance_prices` (view) | Readable names, harmonised empty values, Belgian local time, business columns (system state, validation flag, energy, recomputed price) |
| `analytics` | `calendar`, `public_holidays`, `price_thresholds`, `price_profile`, `daily_summary`, `extreme_prices`, `hourly_prices` (views) | One view per analysis need, ready for Power BI |
| `forecast` | `backtest_results` (table), `model_summary`, `error_by_hour_season` (views) | Forecast backtest results, written by `src/forecast.py` |

All layers above `raw` are views: they are always up to date, with no refresh step. Full column descriptions: [docs/data_dictionary.md](docs/data_dictionary.md).

**Extreme prices** are defined once, in `analytics.price_thresholds`:

* **negative price**: below 0 EUR/MWh, a risk for a BRP that is long (too much energy)
* **high price**: above the 95th percentile of all published prices (278.64 EUR/MWh in November 2026), a risk for a BRP that is short

## Data quality tests

Each file in `tests/sql/` is a query that returns the rows failing a rule: 0 rows means the test passed. The tests run after every daily load, and a failure stops the run.

| Test | Rule |
|---|---|
| `test_01` | No duplicated quarter-hour |
| `test_02` | No missing quarter-hour between the first and the last one loaded |
| `test_03` | Resolution is always 15 minutes |
| `test_04` | Published price matches its components (one documented exception) |
| `test_05` | No empty value in the key columns |
| `test_06` | Prices between −15,000 and +15,000 EUR/MWh, imbalance between −5,000 and +5,000 MW |
| `test_07` | Latest data is less than 2 days old |
| `test_08` | Rows older than 50 days are all validated |
| `test_09` | The public holiday list covers the latest year of data |
| `test_10` | Every day of the data has a calendar row |

## Results

### When is an imbalance most expensive?

Profile of the imbalance price by Belgian hour, on spring weekdays (`analytics.price_profile`):

* **Midday solar dip.** From 10:00 to 15:00, negative prices become frequent: about one quarter-hour in three at 12:00 and 13:00 (30.7% and 32.6%), against 1 to 3% in the evening. A BRP that is **long** (too much energy) is most exposed at midday.
* **Morning and evening ramps.** High prices (above 278.64 EUR/MWh) are most frequent at 07:00 to 08:00 (6 to 7%) and at 19:00 (8.2%, with the highest average price of the day). A BRP that is **short** is most exposed during these ramps.
* **08:00 carries both risks**: 7.4% negative prices and 7.3% high prices in the same hour.
* **Mean and median diverge.** At 12:00 the mean (46.95) is far above the median (29.17), pulled up by a few very high prices; at 04:00 it is below (83.68 against 98.35), pulled down by a few very negative ones. Both are reported: the median describes a typical slot, the mean the cost over the period.

These patterns are observed on two springs (2025 and 2026): they describe what happened, not a law.

### Autumn 2026: a period of sustained tension

From early October 2026, the average daily price rose steadily: from about 150 to 200 EUR/MWh in early October to 250 to 430 EUR/MWh at the end of October and in early November, with up to 47% of the November quarter-hours above the high-price threshold. Over the same period, the system was short 60 to 90% of the time: energy was missing most of the day, Elia activated expensive upward offers, and the imbalance price followed. These rows are not validated yet by Elia, and November 2026 is a partial month. This period is after the forecast test period and does not affect the forecast results.

### Can the price be forecast the day before?

**Setup** (`src/forecast.py`):

* **Target**: the average price of each of the 24 Belgian hours of day D, forecast on the morning of D-1 with data known up to D-2 (Elia publishes with a delay).
* **Reference to beat**: median of the same hour over the last 28 days, same kind of day (working day, or weekend and holiday).
* **Candidates**: the same median with windows of 7 to 56 days (option A), and blends of the last 7 days with a 28 or 56-day profile (option B).
* **Rolling backtest**: every day is forecast with past data only, then compared with the actual prices.
* **Three separate periods**: history from May 2024; validation from July to September 2025, used only to choose among the 10 candidates; test from October 2025 to September 2026 (8,759 hours, all validated), used once for the final result.
* **Metric**: mean absolute error (MAE), in EUR/MWh.

**Results on the test period** (`forecast.model_summary`):

| Model | MAE (EUR/MWh) | RMSE (EUR/MWh) |
|---|---|---|
| Reference: 28-day hourly median | 47.19 | 182.34 |
| Best on validation: 56-day hourly median | 46.26 | 182.28 |

The selected model reduces the error by **2%**. Longer windows always did better on validation, and giving weight to the last 7 days always did worse.

**Where the forecast fails** (`forecast.error_by_hour_season`): the largest errors are at midday in spring (14:00: 217.80 EUR/MWh, 13:00: 113.73), largely driven by the Easter Monday 2026 price floor (−15,000 EUR/MWh from 13:45 to 14:45), then midday and evening hours in summer and autumn (around 60 to 72). The most reliable hours are summer nights (01:00 to 04:00, about 25 to 30 EUR/MWh).

**Conclusion.** Recent days add noise rather than signal: a period of high or low prices does not carry over to the next day. What repeats is the shape of the day (midday dip, morning and evening peaks), best estimated over a long window. With past prices only, the hourly imbalance price is hard to forecast the day before: the stable daily profile is the best predictor found, and the remaining fluctuations, which make most of the error, are not predictable from price history. The RMSE, four times the MAE, shows how much a few extreme hours weigh.

For a BRP, a precise hour-by-hour forecast is not realistic with this data. What is useful is knowing **where the risks are**: the hours where negative and high prices concentrate, as shown above.

**Next step.** The real drivers of imbalances are forecast errors of wind, solar and consumption. Adding these inputs (also published by Elia) is the most promising way to improve the forecast.

## Project structure

```
elia_belgian_imbalance_prices/
├── .github/workflows/
│   └── daily.yml          # GitHub Actions: daily scheduled run
├── docs/
│   ├── images/            # screenshots of the Power BI report
│   ├── data_dictionary.md
│   ├── feasibility_note.md
│   └── project_walkthrough.pdf
├── powerbi/
│   └── elia_imbalance_prices.pbix
├── exploration/
│   └── explore_api.py     # first API exploration script
├── sql/                   # setup files, run in name order
│   ├── 01_create_raw_table.sql
│   ├── 02_create_clean_view.sql
│   ├── 03_create_calendar.sql
│   ├── 04_create_price_thresholds.sql
│   ├── 05_create_price_profile.sql
│   ├── 06_create_daily_summary.sql
│   ├── 07_create_extreme_prices.sql
│   ├── 08_create_hourly_prices.sql
│   ├── 09_create_forecast_table.sql
│   └── 10_create_forecast_errors.sql
├── src/
│   ├── extract.py         # Elia API: fetch_day, fetch_range (with retries)
│   ├── db.py              # Neon: connection, SQL runner, upsert, quality tests
│   ├── pipeline.py        # entry point: load_period, run_daily, run_history
│   └── forecast.py        # baseline forecast, backtest, model selection
├── tests/
│   └── sql/               # data quality tests (test_01 to test_10)
├── .env.example           # secrets needed, without their values
├── CLAUDE.md              # coding conventions for AI-assisted work
├── requirements.txt
└── README.md
```

## Getting started

### Prerequisites

* Python 3.14 (tested version)
* A PostgreSQL database (a free [Neon](https://neon.com) project works)

### 1. Install

```bash
git clone https://github.com/EG-Cloud/elia_belgian_imbalance_prices.git
cd elia_belgian_imbalance_prices

python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure the database connection

Copy `.env.example` to `.env`, and fill in your connection string:

```
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

`.env` is listed in `.gitignore` and must never be committed.

### 3. Create the database objects and run the tests

```bash
python src/db.py
```

This runs every file of `sql/` in name order (raw table, then the clean and analytics views), then the quality tests of `tests/sql/`. It can be run several times safely (`IF NOT EXISTS`, `CREATE OR REPLACE`). On an empty database, run it again after loading the data: the freshness test fails until data is present.

### 4. Load the data

```bash
# One-off: full history since 22 May 2024 (about 900 API calls, 10 to 15 minutes)
python src/pipeline.py history

# Daily update: reload the last 50 days
python src/pipeline.py daily

# Forecast evaluation: choose settings on validation, evaluate on test, store results
python src/forecast.py
```

## Automation

The workflow [`.github/workflows/daily.yml`](.github/workflows/daily.yml) runs `python src/pipeline.py daily` every day at **06:17 UTC**, on a fresh GitHub-hosted machine:

1. check out the repository
2. set up Python
3. install the dependencies from `requirements.txt`
4. run the daily pipeline and the quality tests, with `DATABASE_URL` provided by a **GitHub repository secret**

It can also be started by hand from the **Actions** tab, with **Run workflow**.

To use it on your own fork, add a repository secret named `DATABASE_URL` in **Settings → Secrets and variables → Actions**.

## Data quality notes

* **Provisional values.** Recent rows are `NotValidated` or `DataIssue` until Elia validates them. The 50-day window replaces them automatically.
* **Incomplete latest day.** The most recent UTC day can miss its last quarter-hours: they belong to the next Belgian day, which is not published yet (for example, 23:00 to 23:45 UTC in winter). They are completed by the next daily run.
* **Belgian month boundaries.** In summer, 22:00 UTC on the last day of a month is already midnight of the next month in Brussels. Monthly aggregates must therefore be computed in Belgian time.
* **Price not matching its components.** On 30 August 2024 at 12:15 UTC, the published price (−221 EUR/MWh) differs by 16.49 EUR/MWh from the price rebuilt from its components. The cause is not visible in the published data. It is the only case among more than 86,000 rows, documented as a known exception in `test_04`.
* **Price floor.** On Easter Monday 2026, from 13:45 to 14:45 Belgian time, the price was exactly −15,000 EUR/MWh for five consecutive quarter-hours (long system, decremental price at the same value). This is most likely a technical price limit. These real extreme values are kept in the analysis.
* **Seasons.** Seasons are meteorological (whole months). With data since May 2024, each season is observed only two or three times: seasonal differences are described, not generalised.
* **Empty values.** `alpha_prime` is null at the start of the dataset and 0 afterwards (this component was neutralised with the MARI go-live).
* **Units.** System imbalance is an average power (MW) over 15 minutes. The matching energy is MW × 0.25 h, to be used when computing costs.

## Roadmap

- [x] **Phase 0** · Feasibility: API exploration, data understanding, [feasibility note](docs/feasibility_note.md)
- [x] **Phase 1** · Automated collection: extraction, Neon database, idempotent upsert, history load, daily GitHub Actions run, logging and retries
- [x] **Phase 2** · SQL modelling: clean and analytics layers, 10 data quality tests, [data dictionary](docs/data_dictionary.md)
- [x] **Phase 3** · Analysis and forecasting: price profiles, extreme prices, day-ahead forecast evaluated against a baseline
- [x] **Phase 4** · Reporting: three-page Power BI report, final documentation, [project walkthrough](docs/project_walkthrough.pdf)

## Limitations

* About two and a half years of history since the MARI go-live: enough for daily and seasonal patterns, limited for long-term trends.
* Analysis is based on public, aggregated system data. It does not include the position of any specific BRP.
* The forecast uses past prices only. Wind, solar and load forecasts, the main drivers of imbalances, are not included.
* The forecast is evaluated on one year (October 2025 to September 2026). A 2% improvement on a single year is small and may partly depend on that year.

## Data source and licence

Data: **Elia Transmission Belgium**, [Open Data Platform](https://opendata.elia.be), dataset `ods134` (imbalance prices per quarter-hour), licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://www.elia.be/en/grid-data/elia-open-data-license).

The data were transformed for this project: renamed, converted to Belgian local time, aggregated by hour, day and season, and enriched with derived columns. The Power BI file contains a snapshot of these aggregated data.

## Author

Built by [EG-Cloud](https://github.com/EG-Cloud) as a data analytics portfolio project.
