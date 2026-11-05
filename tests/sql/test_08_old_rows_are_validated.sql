-- Test: rows older than the 50-day daily window are all validated.
-- Elia validates month M after the 15th of month M+1. Older rows are no longer
-- reloaded by the daily run, so a non-validated one would stay provisional forever.
-- Returns the old non-validated rows (0 rows = test passed).

SELECT
    datetime,
    qualitystatus
FROM raw.imbalance_prices
WHERE qualitystatus <> 'Validated'
  AND datetime < now() - INTERVAL '50 days';
