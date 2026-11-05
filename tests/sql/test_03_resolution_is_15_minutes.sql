-- Test: every row has a 15-minute resolution.
-- Returns the rows with another resolution (0 rows = test passed).

SELECT
    datetime,
    resolutioncode
FROM raw.imbalance_prices
WHERE resolutioncode <> 'PT15M';
