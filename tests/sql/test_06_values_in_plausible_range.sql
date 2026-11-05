-- Test: prices and imbalances stay within plausible bounds.
-- Prices: -15000 to +15000 EUR/MWh. Prices at exactly -15000 were observed
-- (2026-04-06, 13:45 to 14:45 Belgian time, long system, decremental offer
-- at the same value): most likely a technical price limit (to confirm).
-- Imbalance: -5000 to +5000 MW, a wide sanity bound chosen by us.
-- Returns the rows outside the bounds (0 rows = test passed).

SELECT
    datetime,
    systemimbalance,
    imbalanceprice
FROM raw.imbalance_prices
WHERE imbalanceprice NOT BETWEEN -15000 AND 15000
   OR systemimbalance NOT BETWEEN -5000 AND 5000;