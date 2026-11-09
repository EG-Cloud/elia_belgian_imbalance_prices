-- Analytics layer: thresholds that define an extreme price.
-- One row. Computed on the full history, so values move slightly as data grows.
-- negative price: below 0 EUR/MWh
-- high price: above the 95th percentile of all published prices
-- Safe to run several times.

CREATE OR REPLACE VIEW analytics.price_thresholds AS
SELECT
    0::numeric AS negative_threshold_eur_mwh,
    ROUND(
        (PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY imbalance_price_eur_mwh))::numeric,
        2
    ) AS high_threshold_eur_mwh
FROM clean.imbalance_prices;
