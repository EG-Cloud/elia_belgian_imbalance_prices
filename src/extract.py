import requests
import time
from datetime import date, timedelta


# Elia Open Data endpoint for imbalance prices per quarter-hour (dataset ods134)
API_URL = "https://opendata.elia.be/api/explore/v2.1/catalog/datasets/ods134/records"


def fetch_day(day):
    """
    Fetch all quarter-hour imbalance price records for one UTC day.

    Args:
        day (date): the UTC day to fetch, e.g. date(2026, 10, 24).

    Returns:
        list[dict]: one dict per quarter-hour (up to 96), exactly as returned
        by the API in "results".

    Raises:
        requests.HTTPError: if the API returns an error status.
    """

    # 1. Compute the next day (upper bound, excluded)
    next_day = day + timedelta(days=1)

    # 2. Build the query parameters
    params = {
        "limit": 100,
        "order_by": "datetime",
        "where": f"datetime >= date'{day}' AND datetime < date'{next_day}'",
    }

    # 3. Send the request
    response = requests.get(API_URL, params=params, timeout=15)

    # 4. Stop if the API returned an error
    response.raise_for_status()

    # 5. Return the list of records
    data = response.json()
    records = data["results"]
    return records

# if __name__ == "__main__":
#     records = fetch_day(date.today())
#     print(len(records))

def fetch_range(start_date, end_date):
    """
    Fetch all quarter-hour imbalance price records between two UTC days.

    Calls fetch_day once per day, with a short pause between calls.

    Args:
        start_date (date): first day to fetch (included).
        end_date (date): last day to fetch (included).

    Returns:
        list[dict]: all records of the period, in chronological order.
        Same 10 keys as fetch_day. Empty list if start_date > end_date.
    """

    # 1. Create an empty list for all records
    all_records = []

    # 2. Start from the first day
    current_day = start_date

    # 3. Loop while the current day is in the range (end_date included)
    while current_day <= end_date:

        # a. Fetch the records of the current day
        records = fetch_day(current_day)

        # b. Add them to the list
        all_records.extend(records)

        # c. Show progress (temporary, logging comes later)
        print(f"{current_day}: {len(records)} rows")

        # d. Pause between two calls to be polite with the API
        time.sleep(0.5)

        # e. Move to the next day
        current_day = current_day + timedelta(days=1)

    # 4. Return the list
    return all_records

if __name__ == "__main__":
    records = fetch_range(date(2026, 10, 22), date(2026, 10, 24))
    print(len(records))