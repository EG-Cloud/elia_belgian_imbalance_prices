from datetime import date, timedelta

from extract import fetch_range
from db import upsert_records

# First day of the dataset (Belgian go-live on the MARI platform)
HISTORY_START = date(2024, 5, 22)


def load_period(start_date, end_date, batch_days=30):
    """
    Fetch and save all records between two UTC days, batch by batch.

    The period is split into batches of batch_days days. Each batch is
    fetched from the API and saved in the database right away, so a crash
    only loses the current batch. Thanks to the upsert, the function can
    simply be run again to resume, without creating duplicates.

    Args:
        start_date (date): first day to load (included).
        end_date (date): last day to load (included).
        batch_days (int): number of days per batch. Default: 30.

    Returns:
        int: total number of records sent to the database.
    """

    # 1. Start with a total of 0 and the first batch at start_date
    records_imported = 0
    batch_start = start_date

    # 2. Loop while the batch starts inside the period (end_date included)
    while batch_start <= end_date:

        # a. Batch end: batch_days - 1 days later, but never after end_date
        batch_end = batch_start + timedelta(days=batch_days - 1)
        batch_end = min(batch_end, end_date)

        # b. Fetch the records of the batch
        records = fetch_range(batch_start, batch_end)

        # c. Save them in the database and add them to the total
        import_size = upsert_records(records)
        records_imported = records_imported + import_size

        # d. Show progress (temporary, logging comes later)
        print(f"Batch {batch_start} to {batch_end}: {import_size} rows saved")

        # e. Next batch starts the day after this batch ends
        batch_start = batch_end + timedelta(days=1)

    # 3. Return the total
    return records_imported

# if __name__ == "__main__":
#     # One-off historical load: from the first day of the dataset to yesterday
#     yesterday = date.today() - timedelta(days=1)
#     total = load_period(HISTORY_START, yesterday)
#     print(f"Total: {total} rows saved")


# Number of recent days re-fetched every day. Elia validates month M after
# the 15th of month M+1, so a value can change up to about 45 days later.
DAILY_WINDOW_DAYS = 50

def run_daily():
    """
    Daily run: re-load the last DAILY_WINDOW_DAYS days, up to yesterday.

    New days are inserted, recent days are updated (provisional values
    replaced by validated ones). Missed runs are caught up automatically,
    as long as they fall inside the window.

    Returns:
        int: number of records sent to the database.
    """

    # 1. End of the window: yesterday (today is not published yet)
    window_end = date.today() - timedelta(days=1)

    # 2. Start of the window: DAILY_WINDOW_DAYS days in total, yesterday included
    window_start = window_end - timedelta(days=DAILY_WINDOW_DAYS - 1)

    # 3. Load the window batch by batch, and return the number of rows
    return load_period(window_start, window_end)

if __name__ == "__main__":
    total = run_daily()
    print(f"Total: {total} rows saved")