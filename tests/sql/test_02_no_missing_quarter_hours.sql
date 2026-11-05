-- Test: no quarter-hour is missing between the first and the last loaded one.
-- generate_series builds the full list of expected quarter-hours (UTC),
-- then the LEFT JOIN keeps those that are not in the raw table.
-- Returns the missing quarter-hours (0 rows = test passed).

SELECT
    expected.datetime AS missing_datetime
FROM generate_series(
    (SELECT MIN(datetime) FROM raw.imbalance_prices),
    (SELECT MAX(datetime) FROM raw.imbalance_prices),
    INTERVAL '15 minutes'
) AS expected(datetime)
LEFT JOIN raw.imbalance_prices AS r
    ON r.datetime = expected.datetime
WHERE r.datetime IS NULL;
