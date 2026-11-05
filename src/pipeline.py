import logging
import sys
from datetime import date, timedelta

from db import upsert_records
from extract import fetch_range

# One logger for this file ("__main__" when run directly, "pipeline" if imported)
logger = logging.getLogger(__name__)

# First day of the dataset (Belgian go-live on the MARI platform)
HISTORY_START = date(2024, 5, 22)

# Number of recent days re-fetched every day. Elia validates month M after
# the 15th of month M+1, so a value can change up to about 45 days later.
DAILY_WINDOW_DAYS = 50


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

        # d. Log the progress of the batch
        logger.info(f"Batch {batch_start} to {batch_end}: {import_size} rows saved")

        # e. Next batch starts the day after this batch ends
        batch_start = batch_end + timedelta(days=1)

    # 3. Return the total
    return records_imported


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
    logger.info(f"Daily run: {window_start} to {window_end}")
    return load_period(window_start, window_end)


def run_history():
    """
    Full load: fetch every day from HISTORY_START up to yesterday.

    Use it once to fill an empty database, or to rebuild it from scratch.
    Thanks to the upsert, running it on a filled database creates no duplicates,
    but it is slow (about 900 API calls): use run_daily for the daily update.

    Returns:
        int: number of records sent to the database.
    """

    # 1. End: yesterday (today is not published yet)
    yesterday = date.today() - timedelta(days=1)

    # 2. Load the whole history and return the number of rows
    logger.info(f"History run: {HISTORY_START} to {yesterday}")
    return load_period(HISTORY_START, yesterday)


if __name__ == "__main__":
    # Usage: python src/pipeline.py [daily|history]

    # 0. Configure logging once, for this file and all the imported ones
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # 1. No mode given: show the usage and stop
    if len(sys.argv) < 2:
        print("Usage: python src/pipeline.py [daily|history]")
        sys.exit(1)

    try:

        # 2. Read the mode typed after the file name
        mode = sys.argv[1]

        # 3. Run the matching function (unknown mode: show the usage and stop)
        if mode == "daily":
            imported_records = run_daily()
        elif mode == "history":
            imported_records = run_history()
        else:
            print("Usage: python src/pipeline.py [daily|history]")
            sys.exit(1)

        # 4. Only reached by "daily" and "history": the else branch has stopped the program
        logger.info(f"Run finished: {imported_records} records sent to the database")

    except Exception:

        logger.exception(f"The {mode} run did not succeed")
        sys.exit(1)