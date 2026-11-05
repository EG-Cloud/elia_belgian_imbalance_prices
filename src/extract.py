import logging
import time
from datetime import date, timedelta

import requests

# One logger for this file, named "extract"
logger = logging.getLogger(__name__)

# Elia Open Data endpoint for imbalance prices per quarter-hour (dataset ods134)
API_URL = "https://opendata.elia.be/api/explore/v2.1/catalog/datasets/ods134/records"

MAX_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 5

def fetch_day(day):
    """
    Fetch all quarter-hour imbalance price records for one UTC day.

    Temporary errors (network problems, server errors 5xx) are retried
    up to MAX_ATTEMPTS times, with a pause of RETRY_WAIT_SECONDS between
    attempts. Errors caused by the request itself (4xx) are not retried.

    Args:
        day (date): the UTC day to fetch, e.g. date(2026, 10, 24).

    Returns:
        list[dict]: one dict per quarter-hour (up to 96), exactly as returned
        by the API in "results".

    Raises:
        requests.HTTPError: if the API rejects the request (4xx).
        RuntimeError: if the day still fails after MAX_ATTEMPTS attempts.
    """

    # 1. Compute the next day (upper bound, excluded)
    next_day = day + timedelta(days=1)

    # 2. Build the query parameters
    params = {
        "limit": 100,
        "order_by": "datetime",
        "where": f"datetime >= date'{day}' AND datetime < date'{next_day}'",
    }

    # 3. Send the request, with up to MAX_ATTEMPTS attempts
    attempt = 1

    while attempt <= MAX_ATTEMPTS:

        try:
            response = requests.get(API_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data["results"]          # success: leaves the function

        except (requests.Timeout, requests.ConnectionError):
            # Network problem: always temporary, worth retrying
            reason = "network problem"

        except requests.HTTPError as error:
            status = error.response.status_code
            if status < 500:
                # 4xx: our request is wrong, retrying would fail the same way
                raise
            # 5xx: server problem, worth retrying
            reason = f"server error {status}"

        # 4. Only reached after a temporary error: give up or try again
        if attempt == MAX_ATTEMPTS:
            logger.error(f"{day}: giving up after {MAX_ATTEMPTS} attempts ({reason})")
            raise RuntimeError(f"Could not fetch {day} after {MAX_ATTEMPTS} attempts ({reason})")

        logger.warning(
            f"{day}: attempt {attempt} failed ({reason}), "
            f"retrying in {RETRY_WAIT_SECONDS}s"
        )
        time.sleep(RETRY_WAIT_SECONDS)
        attempt = attempt + 1


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

        # c. Log the progress
        logger.info(f"{current_day}: {len(records)} rows")

        # d. Pause between two calls to be polite with the API
        time.sleep(0.5)

        # e. Move to the next day
        current_day = current_day + timedelta(days=1)

    # 4. Return the list
    return all_records