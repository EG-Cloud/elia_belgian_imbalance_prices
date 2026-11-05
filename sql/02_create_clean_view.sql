-- Clean layer: readable names, harmonised empty values, Belgian local time,
-- and business columns. Built on raw.imbalance_prices.
-- Safe to run several times (IF NOT EXISTS, OR REPLACE).

-- 1. Create the schema
CREATE SCHEMA IF NOT EXISTS clean;

-- 2. Create the view
CREATE OR REPLACE VIEW clean.imbalance_prices AS
SELECT
    -- Family 1: raw columns, renamed (resolutioncode excluded: always PT15M)
    datetime                    AS datetime_utc,
    qualitystatus               AS quality_status,
    ace                         AS ace_mw,
    systemimbalance             AS system_imbalance_mw,
    alpha                       AS alpha_eur_mwh,
    marginalincrementalprice    AS marginal_incremental_price_eur_mwh,
    marginaldecrementalprice    AS marginal_decremental_price_eur_mwh,
    imbalanceprice              AS imbalance_price_eur_mwh,
    loaded_at,

    -- Family 2: empty values harmonised (NULL early in the dataset, 0 since MARI)
    COALESCE(alpha_prime, 0)    AS alpha_prime_eur_mwh,

    -- Family 3: Belgian local time (daylight saving time handled by PostgreSQL)
    datetime AT TIME ZONE 'Europe/Brussels'                              AS datetime_local,
    (datetime AT TIME ZONE 'Europe/Brussels')::date                      AS date_local,
    EXTRACT(HOUR   FROM datetime AT TIME ZONE 'Europe/Brussels')::int    AS hour_local,
    EXTRACT(ISODOW FROM datetime AT TIME ZONE 'Europe/Brussels')::int    AS weekday_local,
    EXTRACT(MONTH  FROM datetime AT TIME ZONE 'Europe/Brussels')::int    AS month_local,
    CASE
        WHEN EXTRACT(MONTH FROM datetime AT TIME ZONE 'Europe/Brussels') IN (12, 1, 2)  THEN 'winter'
        WHEN EXTRACT(MONTH FROM datetime AT TIME ZONE 'Europe/Brussels') IN (3, 4, 5)   THEN 'spring'
        WHEN EXTRACT(MONTH FROM datetime AT TIME ZONE 'Europe/Brussels') IN (6, 7, 8)   THEN 'summer'
        ELSE 'autumn'
    END                                                                  AS season,

    -- Family 4: business columns
    CASE
        WHEN systemimbalance < 0 THEN 'short'
        ELSE 'long'
    END                                         AS system_state,
    qualitystatus = 'Validated'                 AS is_validated,
    systemimbalance * 0.25                      AS imbalance_energy_mwh,
    CASE
        WHEN systemimbalance < 0 THEN marginalincrementalprice + alpha
        ELSE marginaldecrementalprice - alpha
    END                                         AS recomputed_price_eur_mwh

FROM raw.imbalance_prices;