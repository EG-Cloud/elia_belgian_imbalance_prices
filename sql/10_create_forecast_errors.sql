-- Forecast layer: error summaries of the backtest results.
-- MAE is the main metric; RMSE is given for reference, it is dominated by a
-- few extreme hours.
-- Safe to run several times.

-- One row per model
CREATE OR REPLACE VIEW forecast.model_summary AS
SELECT
    model_name,
    MIN(date_local)                                   AS first_day,
    MAX(date_local)                                   AS last_day,
    COUNT(*)                                          AS nb_hours,
    ROUND(AVG(abs_error_eur_mwh), 2)                  AS mae_eur_mwh,
    ROUND(SQRT(AVG(abs_error_eur_mwh ^ 2)), 2)        AS rmse_eur_mwh
FROM forecast.backtest_results
GROUP BY model_name;

-- One row per model x Belgian hour x season
CREATE OR REPLACE VIEW forecast.error_by_hour_season AS
SELECT
    r.model_name,
    r.hour_local,
    c.season,
    COUNT(*)                                          AS nb_hours,
    ROUND(AVG(r.abs_error_eur_mwh), 2)                AS mae_eur_mwh,
    ROUND(AVG(r.actual_eur_mwh), 2)                   AS avg_actual_eur_mwh,
    ROUND(AVG(r.forecast_eur_mwh), 2)                 AS avg_forecast_eur_mwh
FROM forecast.backtest_results AS r
JOIN analytics.calendar AS c
    ON c.date_local = r.date_local
GROUP BY
    r.model_name,
    r.hour_local,
    c.season;
