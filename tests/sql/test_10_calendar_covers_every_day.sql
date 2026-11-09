-- Test: every Belgian day of the data has exactly one row in the calendar.
-- Returns the days missing from the calendar (0 rows = test passed).

SELECT DISTINCT
    p.date_local
FROM clean.imbalance_prices AS p
LEFT JOIN analytics.calendar AS c
    ON c.date_local = p.date_local
WHERE c.date_local IS NULL;
