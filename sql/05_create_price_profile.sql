-- Analytics layer: imbalance price profile by Belgian hour, day type and season.
-- One row per hour (0-23) x day type (weekday, weekend, holiday) x season.
-- Median and percentiles describe a typical slot; the mean includes extreme
-- prices and reflects the cost over the period.
-- A short BRP is exposed to high prices, a long BRP to low or negative prices.
-- Safe to run several times.

CREATE OR REPLACE VIEW analytics.price_profile AS
SELECT
    p.hour_local,
    c.day_type,
    c.season,
    COUNT(*) AS nb_quarter_hours,

    ROUND(AVG(p.imbalance_price_eur_mwh), 2) AS avg_price_eur_mwh,
    ROUND((PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY p.imbalance_price_eur_mwh))::numeric, 2) AS median_price_eur_mwh,
    ROUND((PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY p.imbalance_price_eur_mwh))::numeric, 2) AS p05_price_eur_mwh,
    ROUND((PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY p.imbalance_price_eur_mwh))::numeric, 2) AS p95_price_eur_mwh,
    ROUND(STDDEV_SAMP(p.imbalance_price_eur_mwh), 2) AS stddev_price_eur_mwh,

    ROUND(100.0 * AVG(CASE WHEN p.imbalance_price_eur_mwh < t.negative_threshold_eur_mwh THEN 1 ELSE 0 END), 1) AS pct_negative_price,
    ROUND(100.0 * AVG(CASE WHEN p.imbalance_price_eur_mwh > t.high_threshold_eur_mwh THEN 1 ELSE 0 END), 1)     AS pct_high_price,
    ROUND(100.0 * AVG(CASE WHEN p.system_state = 'short' THEN 1 ELSE 0 END), 1)                                  AS pct_short_system
FROM clean.imbalance_prices AS p
JOIN analytics.calendar AS c
    ON c.date_local = p.date_local
CROSS JOIN analytics.price_thresholds AS t
GROUP BY
    p.hour_local,
    c.day_type,
    c.season;
