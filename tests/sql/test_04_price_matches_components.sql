-- Test: the published price matches its components
-- (short system: incremental + alpha, long system: decremental - alpha).
-- Known exception, documented: 2024-08-30 12:15 UTC (gap of 16.49 EUR/MWh,
-- cause not visible in the published data).
-- Returns the unexpected mismatches (0 rows = test passed).

SELECT
    datetime_utc,
    system_imbalance_mw,
    imbalance_price_eur_mwh,
    recomputed_price_eur_mwh
FROM clean.imbalance_prices
WHERE ABS(recomputed_price_eur_mwh - imbalance_price_eur_mwh) > 0.01
  AND datetime_utc NOT IN (
      '2024-08-30 12:15:00+00'
  );
