-- Test: the key columns used by the analysis are never empty.
-- Returns the rows with an empty key value (0 rows = test passed).

SELECT
    datetime,
    systemimbalance,
    imbalanceprice
FROM raw.imbalance_prices
WHERE systemimbalance IS NULL
   OR imbalanceprice IS NULL
   OR marginalincrementalprice IS NULL
   OR marginaldecrementalprice IS NULL;
