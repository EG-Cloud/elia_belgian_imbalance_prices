-- Test: the public holiday list covers the latest year of data.
-- Fails when the data reaches a year missing from analytics.public_holidays:
-- the holidays of that year must then be added to sql/03_create_calendar.sql.
-- Returns one row if the list must be extended (0 rows = test passed).

SELECT
    (SELECT MAX(date_local) FROM clean.imbalance_prices)          AS last_data_date,
    (SELECT MAX(holiday_date) FROM analytics.public_holidays)     AS last_holiday_date
WHERE EXTRACT(YEAR FROM (SELECT MAX(date_local) FROM clean.imbalance_prices))
    > EXTRACT(YEAR FROM (SELECT MAX(holiday_date) FROM analytics.public_holidays));
