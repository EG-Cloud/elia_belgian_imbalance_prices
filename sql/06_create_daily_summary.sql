-- Analytics layer: one row per Belgian calendar day.
-- nb_quarter_hours is normally 96, 92 on the spring clock change, 100 on the
-- autumn clock change, and lower on the first and last (incomplete) days.
-- Safe to run several times.

CREATE OR REPLACE VIEW analytics.daily_summary AS
SELECT
    p.date_local,
    c.day_type,
    c.season,
    c.season_label,
    COUNT(*) AS nb_quarter_hours,

    ROUND(AVG(p.imbalance_price_eur_mwh), 2)          AS avg_price_eur_mwh,
    MIN(p.imbalance_price_eur_mwh)                    AS min_price_eur_mwh,
    MAX(p.imbalance_price_eur_mwh)                    AS max_price_eur_mwh,
    ROUND(STDDEV_SAMP(p.imbalance_price_eur_mwh), 2)  AS stddev_price_eur_mwh,

    SUM(CASE WHEN p.imbalance_price_eur_mwh < t.negative_threshold_eur_mwh THEN 1 ELSE 0 END) AS nb_negative_prices,
    SUM(CASE WHEN p.imbalance_price_eur_mwh > t.high_threshold_eur_mwh THEN 1 ELSE 0 END)     AS nb_high_prices,
    ROUND(100.0 * AVG(CASE WHEN p.system_state = 'short' THEN 1 ELSE 0 END), 1)               AS pct_short_system,

    BOOL_AND(p.is_validated) AS is_fully_validated
FROM clean.imbalance_prices AS p
JOIN analytics.calendar AS c
    ON c.date_local = p.date_local
CROSS JOIN analytics.price_thresholds AS t
GROUP BY
    p.date_local,
    c.day_type,
    c.season,
    c.season_label;
