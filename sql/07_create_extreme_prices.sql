-- Analytics layer: detailed list of extreme quarter-hours (negative or high price).
-- Thresholds come from analytics.price_thresholds.
-- Safe to run several times.

CREATE OR REPLACE VIEW analytics.extreme_prices AS
SELECT
    p.datetime_utc,
    p.datetime_local,
    p.date_local,
    p.hour_local,
    c.day_type,
    c.season,
    c.season_label,
    CASE
        WHEN p.imbalance_price_eur_mwh < t.negative_threshold_eur_mwh THEN 'negative'
        ELSE 'high'
    END AS extreme_type,
    p.imbalance_price_eur_mwh,
    p.system_imbalance_mw,
    p.system_state,
    p.is_validated
FROM clean.imbalance_prices AS p
JOIN analytics.calendar AS c
    ON c.date_local = p.date_local
CROSS JOIN analytics.price_thresholds AS t
WHERE p.imbalance_price_eur_mwh < t.negative_threshold_eur_mwh
   OR p.imbalance_price_eur_mwh > t.high_threshold_eur_mwh;
