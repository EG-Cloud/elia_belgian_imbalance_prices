-- Raw layer: exact copy of the Elia API (dataset ods134), one row per quarter-hour.
-- Safe to run several times (IF NOT EXISTS).

-- 1. Create the schema
CREATE SCHEMA IF NOT EXISTS raw;

-- 2. Create the table
CREATE TABLE IF NOT EXISTS raw.imbalance_prices (
    datetime                  TIMESTAMPTZ PRIMARY KEY,
    resolutioncode            TEXT NOT NULL,
    qualitystatus             TEXT NOT NULL,
    ace                       NUMERIC,
    systemimbalance           NUMERIC,
    alpha                     NUMERIC,
    alpha_prime               NUMERIC,
    marginalincrementalprice  NUMERIC,
    marginaldecrementalprice  NUMERIC,
    imbalanceprice            NUMERIC,
    loaded_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);