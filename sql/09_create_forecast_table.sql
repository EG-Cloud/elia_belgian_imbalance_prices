-- Forecast layer: backtest results written by src/forecast.py.
-- One row per model and forecast hour. Each run of a model replaces its rows.
-- Safe to run several times.

CREATE SCHEMA IF NOT EXISTS forecast;

CREATE TABLE IF NOT EXISTS forecast.backtest_results (
    model_name           TEXT        NOT NULL,
    date_local           DATE        NOT NULL,
    hour_local           INTEGER     NOT NULL,
    day_type             TEXT        NOT NULL,
    actual_eur_mwh       NUMERIC     NOT NULL,
    forecast_eur_mwh     NUMERIC     NOT NULL,
    abs_error_eur_mwh    NUMERIC     NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (model_name, date_local, hour_local)
);
