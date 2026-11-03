# Belgian Imbalance Prices

Automated pipeline and analysis of Belgian electricity imbalance prices (Elia Open Data).

> **Status:** Phase 1 (automated collection) complete. Phase 2 (SQL modelling) in progress.
> See [docs/feasibility_note.md](docs/feasibility_note.md) for the full project scope.

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
| SQL modelling *(Phase 2)* | Raw, clean and analytics layers, with data quality tests |
| Analysis and forecasting *(Phase 3)* | Price profiles, extreme prices, forecast evaluated against a simple baseline |

## Architecture

```mermaid
flowchart LR
    A[Elia Open Data API<br/>dataset ods134] -->|requests, one call per day| B[Python pipeline<br/>src/]
    C[GitHub Actions<br/>daily schedule] -->|runs| B
    B -->|upsert| D[(Neon PostgreSQL<br/>raw.imbalance_prices)]
    D --> E[SQL layers<br/>clean / analytics]
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

## Project structure

```
elia_belgian_imbalance_prices/
├── .github/workflows/
│   └── daily.yml          # GitHub Actions: daily scheduled run
├── docs/
│   └── feasibility_note.md
├── exploration/
│   └── explore_api.py     # first API exploration script
├── sql/
│   └── 01_create_raw_table.sql
├── src/
│   ├── extract.py         # Elia API: fetch_day, fetch_range (with retries)
│   ├── db.py              # Neon: connection, SQL file runner, upsert
│   └── pipeline.py        # entry point: load_period, run_daily, run_history
├── tests/
├── .env.example           # secrets needed, without their values
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

### 3. Create the raw table

```bash
python src/db.py
```

This runs `sql/01_create_raw_table.sql`, which creates the `raw` schema and the `raw.imbalance_prices` table. The script can be run several times safely (`IF NOT EXISTS`).

### 4. Load the data

```bash
# One-off: full history since 22 May 2024 (about 900 API calls, 10 to 15 minutes)
python src/pipeline.py history

# Daily update: reload the last 50 days
python src/pipeline.py daily
```

## Automation

The workflow [`.github/workflows/daily.yml`](.github/workflows/daily.yml) runs `python src/pipeline.py daily` every day at **06:17 UTC**, on a fresh GitHub-hosted machine:

1. check out the repository
2. set up Python
3. install the dependencies from `requirements.txt`
4. run the daily pipeline, with `DATABASE_URL` provided by a **GitHub repository secret**

It can also be started by hand from the **Actions** tab, with **Run workflow**.

To use it on your own fork, add a repository secret named `DATABASE_URL` in **Settings → Secrets and variables → Actions**.

## Data quality notes

* **Provisional values.** Recent rows are `NotValidated` or `DataIssue` until Elia validates them. The 50-day window replaces them automatically.
* **Incomplete latest day.** The most recent UTC day can miss its last quarter-hours: they belong to the next Belgian day, which is not published yet (for example, 23:00 to 23:45 UTC in winter). They are completed by the next daily run.
* **Belgian month boundaries.** In summer, 22:00 UTC on the last day of a month is already midnight of the next month in Brussels. Monthly aggregates must therefore be computed in Belgian time.
* **Empty values.** `alpha_prime` is null at the start of the dataset and 0 afterwards (this component was neutralised with the MARI go-live).
* **Units.** System imbalance is an average power (MW) over 15 minutes. The matching energy is MW × 0.25 h, to be used when computing costs.

## Roadmap

- [x] **Phase 0** · Feasibility: API exploration, data understanding, [feasibility note](docs/feasibility_note.md)
- [x] **Phase 1** · Automated collection: extraction, Neon database, idempotent upsert, history load, daily GitHub Actions run, logging and retries
- [ ] **Phase 2** · SQL modelling: clean and analytics layers, data quality tests
- [ ] **Phase 3** · Analysis and forecasting: price profiles, extreme prices, forecast evaluated against a simple baseline
- [ ] **Phase 4** · Reporting: Power BI report, final documentation and limitations

## Limitations

* About two and a half years of history since the MARI go-live: enough for daily and seasonal patterns, limited for long-term trends.
* Analysis is based on public, aggregated system data. It does not include the position of any specific BRP.
* The reuse terms of the Elia Open Data portal are to be confirmed before any public reuse of the data.

## Author

Built by [EG-Cloud](https://github.com/EG-Cloud) as a data analytics portfolio project.
