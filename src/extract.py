import requests
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

if __name__ == "__main__":
    records = fetch_day(date.today())
    print(len(records))


    

    


