-- Analytics layer: Belgian public holidays and a daily calendar (Belgian local time).
-- The calendar covers every day present in clean.imbalance_prices.
-- Safe to run several times.
-- Maintenance: extend the holiday list before the data reaches a new year
-- (checked by tests/sql/test_09_holidays_cover_data.sql).

CREATE SCHEMA IF NOT EXISTS analytics;

-- Belgian national public holidays. Movable dates follow Easter:
-- Easter Monday (+1 day), Ascension Day (+39 days), Whit Monday (+50 days).
CREATE OR REPLACE VIEW analytics.public_holidays AS
SELECT
    holiday_date::date AS holiday_date,
    holiday_name
FROM (
    VALUES
        ('2024-01-01', 'New Year''s Day'),
        ('2024-04-01', 'Easter Monday'),
        ('2024-05-01', 'Labour Day'),
        ('2024-05-09', 'Ascension Day'),
        ('2024-05-20', 'Whit Monday'),
        ('2024-07-21', 'National Day'),
        ('2024-08-15', 'Assumption Day'),
        ('2024-11-01', 'All Saints'' Day'),
        ('2024-11-11', 'Armistice Day'),
        ('2024-12-25', 'Christmas Day'),

        ('2025-01-01', 'New Year''s Day'),
        ('2025-04-21', 'Easter Monday'),
        ('2025-05-01', 'Labour Day'),
        ('2025-05-29', 'Ascension Day'),
        ('2025-06-09', 'Whit Monday'),
        ('2025-07-21', 'National Day'),
        ('2025-08-15', 'Assumption Day'),
        ('2025-11-01', 'All Saints'' Day'),
        ('2025-11-11', 'Armistice Day'),
        ('2025-12-25', 'Christmas Day'),

        ('2026-01-01', 'New Year''s Day'),
        ('2026-04-06', 'Easter Monday'),
        ('2026-05-01', 'Labour Day'),
        ('2026-05-14', 'Ascension Day'),
        ('2026-05-25', 'Whit Monday'),
        ('2026-07-21', 'National Day'),
        ('2026-08-15', 'Assumption Day'),
        ('2026-11-01', 'All Saints'' Day'),
        ('2026-11-11', 'Armistice Day'),
        ('2026-12-25', 'Christmas Day'),

        ('2027-01-01', 'New Year''s Day'),
        ('2027-03-29', 'Easter Monday'),
        ('2027-05-01', 'Labour Day'),
        ('2027-05-06', 'Ascension Day'),
        ('2027-05-17', 'Whit Monday'),
        ('2027-07-21', 'National Day'),
        ('2027-08-15', 'Assumption Day'),
        ('2027-11-01', 'All Saints'' Day'),
        ('2027-11-11', 'Armistice Day'),
        ('2027-12-25', 'Christmas Day')
) AS holidays(holiday_date, holiday_name);

-- One row per Belgian calendar day. Used as the date table in Power BI.
-- day_type: a public holiday counts as 'holiday' even when it falls on a weekend.
-- season: meteorological seasons (whole months). season_label groups December
-- with the following January and February (e.g. 'winter 2025-2026').
CREATE OR REPLACE VIEW analytics.calendar AS
WITH days AS (
    SELECT day::date AS date_local
    FROM generate_series(
        (SELECT MIN(date_local) FROM clean.imbalance_prices),
        (SELECT MAX(date_local) FROM clean.imbalance_prices),
        INTERVAL '1 day'
    ) AS day
),

days_with_parts AS (
    SELECT
        date_local,
        EXTRACT(YEAR FROM date_local)::int   AS year,
        EXTRACT(MONTH FROM date_local)::int  AS month,
        EXTRACT(ISODOW FROM date_local)::int AS weekday
    FROM days
)

SELECT
    d.date_local,
    d.year,
    d.month,
    TO_CHAR(d.date_local, 'FMMonth')  AS month_name,
    d.weekday,
    TO_CHAR(d.date_local, 'FMDay')    AS weekday_name,
    d.weekday IN (6, 7)               AS is_weekend,
    h.holiday_date IS NOT NULL        AS is_holiday,
    h.holiday_name,
    CASE
        WHEN h.holiday_date IS NOT NULL THEN 'holiday'
        WHEN d.weekday IN (6, 7)        THEN 'weekend'
        ELSE 'weekday'
    END                               AS day_type,
    CASE
        WHEN d.month IN (12, 1, 2) THEN 'winter'
        WHEN d.month IN (3, 4, 5)  THEN 'spring'
        WHEN d.month IN (6, 7, 8)  THEN 'summer'
        ELSE 'autumn'
    END                               AS season,
    CASE
        WHEN d.month = 12      THEN 'winter ' || d.year || '-' || (d.year + 1)
        WHEN d.month IN (1, 2) THEN 'winter ' || (d.year - 1) || '-' || d.year
        WHEN d.month IN (3, 4, 5) THEN 'spring ' || d.year
        WHEN d.month IN (6, 7, 8) THEN 'summer ' || d.year
        ELSE 'autumn ' || d.year
    END                               AS season_label
FROM days_with_parts AS d
LEFT JOIN analytics.public_holidays AS h
    ON h.holiday_date = d.date_local;
