-- Test: each quarter-hour appears only once in the raw table.
-- Returns the duplicated datetimes (0 rows = test passed).

SELECT
    datetime,
    COUNT(*) AS nb_rows
FROM raw.imbalance_prices
GROUP BY datetime
HAVING COUNT(*) > 1;
