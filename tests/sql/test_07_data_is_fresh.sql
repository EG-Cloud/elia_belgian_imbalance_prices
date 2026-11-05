-- Test: the most recent quarter-hour is less than 2 days old.
-- A failure means the daily run stopped loading new data.
-- Returns one row if the data is stale (0 rows = test passed).

SELECT
    MAX(datetime) AS last_datetime
FROM raw.imbalance_prices
HAVING MAX(datetime) < now() - INTERVAL '2 days';
