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

if __name__ == "__main__":
    # Test on a short period with small batches
    total = load_period(date(2026, 10, 1), date(2026, 10, 24), batch_days=7)
    print(f"Total: {total} rows saved")