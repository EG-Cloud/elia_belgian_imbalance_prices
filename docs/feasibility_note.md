# Feasibility Note: Belgian Imbalance Prices (Elia Open Data)

*Date: 26 October 2026. Status: Phase 0 complete. Verdict: feasible.*

## 1. Objective

A Balance Responsible Party (BRP) can use this analysis to identify the time slots (hour, day, season) where an imbalance costs the most, and focus its forecasting efforts there.

Analysis questions:

1. At which hours, days and seasons is the imbalance price highest, or most volatile?
2. How often do extreme prices occur (both high and negative), and when?
3. Can these time slots be anticipated better than with a simple hourly average?

## 2. Data source

| Item | Value |
|---|---|
| Publisher | Elia Transmission Belgium (Open Data portal, opendata.elia.be) |
| Dataset | `ods134`, imbalance prices per quarter-hour (historical data) |
| Coverage | From 22/05/2024 (Belgian go-live on the European MARI platform) |
| Granularity | 15 minutes, 96 rows per UTC day |
| Volume | 84,864 rows on 23/10/2026 (884 full days) |
| Refresh | Daily |

The dataset starts at the MARI go-live because the price calculation method changed on that date. Data before 22/05/2024 (`ods047`) has a different structure and is out of scope.

### Columns (API names)

| Column | Type | Unit | Meaning |
|---|---|---|---|
| `datetime` | timestamp (ISO 8601, UTC) | | Quarter-hour timestamp |
| `resolutioncode` | text | | Time resolution, always `PT15M` |
| `qualitystatus` | text | | `NotValidated`, `DataIssue` or `Validated` |
| `ace` | number | MW | Area Control Error: imbalance remaining after Elia's corrections |
| `systemimbalance` | number | MW | System imbalance (SI) before correction. Negative: short system. Positive: long system |
| `alpha` | number | EUR/MWh | Penalty component added when the grid has been under stress |
| `alpha_prime` | number | EUR/MWh | Reserve-sharing component, neutralised since MARI (null early on, then 0) |
| `marginalincrementalprice` | number | EUR/MWh | Price of the last upward activation |
| `marginaldecrementalprice` | number | EUR/MWh | Price of the last downward activation (can be negative) |
| `imbalanceprice` | number | EUR/MWh | **Target variable**: final imbalance price |

Price logic, verified on sample rows: short system, price = incremental price + alpha; long system, price = decremental price − alpha. Example (11/04/2025 10:15 UTC): SI = −151.8 MW, 176 + 6.409 = 182.409 EUR/MWh, identical to the published value.

## 3. Access

* Endpoint: `GET https://opendata.elia.be/api/explore/v2.1/catalog/datasets/ods134/records`
* Platform: Opendatasoft Explore API v2.1. JSON response with `total_count` (int) and `results` (list of records).
* Authentication: none required.
* Limits (tested): maximum 100 records per call (`limit=101` returns HTTP 400); `offset + limit` must not exceed 10,000.
* Quota (from response headers, observed 26/10/2026): 100,000,000 calls per day, reset at midnight UTC, apparently shared across all anonymous users.
* Filtering by date works with `where`, e.g. `datetime >= date'2026-10-24' AND datetime < date'2026-10-25'`.

## 4. Collection strategy

**One day per call.** A UTC day holds 96 rows, below the 100-record limit, so one filtered call retrieves a full day without pagination.

* **Historical load:** loop over every day since 22/05/2024 (about 884 calls).
* **Daily run:** re-fetch the **last 50 days** and update existing rows. Values are validated after the 15th of the following month, so up to about 45 days later; 50 days adds a margin.
* **Same function for both**, which keeps a single collection logic tested on hundreds of days before automation.
* **Idempotent writes:** a unique key on `datetime` and an upsert (`INSERT ... ON CONFLICT ... DO UPDATE`), so re-running never creates duplicates and validated values replace provisional ones.
* **Courtesy:** short pause between calls, explicit sorting (`order_by`), timeout on every request.

Alternative considered: the `exports` endpoint returns the whole dataset in one call. It was not chosen, to keep one collection logic for history and incremental loads.

## 5. Data quality risks

| Risk | Observation | Handling |
|---|---|---|
| Provisional values | Recent rows are `NotValidated` or `DataIssue` | Re-fetch 50-day window, keep `qualitystatus`, flag in analysis |
| Incomplete latest day | 25/10/2026 had 92 rows on 26/10: the 4 last UTC quarter-hours belong to the Belgian day not yet published | Never treat the latest day as final; covered by the 50-day re-fetch |
| Daylight saving time | Timestamps are UTC, so no duplicated or missing quarter-hours (verified: 24/10/2026 has 96 rows) | Store in UTC (`TIMESTAMPTZ`), convert to `Europe/Brussels` only for analysis |
| Default order | Records come back unsorted without `order_by` | Always sort explicitly |
| Types | `datetime` arrives as text in pandas | Convert with `pd.to_datetime(..., utc=True)` |
| Two kinds of "empty" | `alpha_prime` is null early on, 0 later | Harmonise during cleaning and document |
| Units | SI is in MW (average power), prices in EUR/MWh | Energy = MW × 0.25 h per quarter-hour when computing costs |
| Price consistency | Components should rebuild the final price | Quality test: recompute and compare with `imbalanceprice` |
| Market regime | Only about 2.5 years of history since MARI | Limits forecasting depth; stated in the limitations |

## 6. Open questions

* **Licence and reuse terms** of the Elia Open Data portal: not confirmed. To check before publishing the repository.
* **Exact alpha formula**: the inputs are known (measured and estimated SI), not the full calculation. Not needed for the analysis.
* **Publication time** of the daily refresh: to observe once collection runs.
* **API stability**: the version used (Explore API v2.1) will be documented in the README.

## 7. Planned architecture

Scheduled Python collection (GitHub Actions) → hosted PostgreSQL (Supabase or Neon, free tier, to be decided in Phase 1) → SQL layers (raw, clean, analytics) with quality tests → Power BI report and spreadsheet summary.

## 8. Verdict

**Feasible.** The data is public, free, documented by its schema, reachable without a key, and the quota is far above our needs (about 50 calls per day). The main risks (provisional values, incomplete latest day, time zones) are known and handled by design. Remaining blocker before publication: confirm the licence.
