-- Analytics layer: average imbalance price per Belgian day and hour.
-- Input of the forecast (src/forecast.py). One row per date_local x hour_local.
-- On the autumn clock change, hour 2 averages 8 quarter-hours; on the spring
-- clock change, hour 2 does not exist.
-- Safe to run several times.

CREATE OR REPLACE VIEW analytics.hourly_prices AS
SELECT
    p.date_local,
    p.hour_local,
    c.day_type,
    ROUND(AVG(p.imbalance_price_eur_mwh), 2) AS avg_price_eur_mwh,
    BOOL_AND(p.is_validated)                 AS is_validated
FROM clean.imbalance_prices AS p
JOIN analytics.calendar AS c
    ON c.date_local = p.date_local
GROUP BY
    p.date_local,
    p.hour_local,
    c.day_type;
