import logging
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Load the variables from .env into the environment
load_dotenv()

# One logger for this file, named "db"
logger = logging.getLogger(__name__)

# Project root, two levels above this file (src/db.py -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Folder with the setup SQL files (tables and views), run in name order
SQL_FOLDER = PROJECT_ROOT / "sql"

# Folder with the data quality tests: each file returns the rows that FAIL the test
TESTS_FOLDER = PROJECT_ROOT / "tests" / "sql"

# Insert a new quarter-hour, or update it if its datetime already exists
UPSERT_QUERY = """
    INSERT INTO raw.imbalance_prices (
        datetime,
        resolutioncode,
        qualitystatus,
        ace,
        systemimbalance,
        alpha,
        alpha_prime,
        marginalincrementalprice,
        marginaldecrementalprice,
        imbalanceprice
    )
    VALUES (
        %(datetime)s,
        %(resolutioncode)s,
        %(qualitystatus)s,
        %(ace)s,
        %(systemimbalance)s,
        %(alpha)s,
        %(alpha_prime)s,
        %(marginalincrementalprice)s,
        %(marginaldecrementalprice)s,
        %(imbalanceprice)s
    )
    ON CONFLICT (datetime) DO UPDATE SET
        resolutioncode = EXCLUDED.resolutioncode,
        qualitystatus = EXCLUDED.qualitystatus,
        ace = EXCLUDED.ace,
        systemimbalance = EXCLUDED.systemimbalance,
        alpha = EXCLUDED.alpha,
        alpha_prime = EXCLUDED.alpha_prime,
        marginalincrementalprice = EXCLUDED.marginalincrementalprice,
        marginaldecrementalprice = EXCLUDED.marginaldecrementalprice,
        imbalanceprice = EXCLUDED.imbalanceprice,
        loaded_at = now();
"""


def get_connection():
    """
    Open a connection to the Neon PostgreSQL database.

    Reads the connection string from the DATABASE_URL environment variable
    (loaded from .env locally, or provided by GitHub Actions).

    Returns:
        psycopg.Connection: an open connection. The caller is responsible
        for closing it, ideally with a "with" block.

    Raises:
        ValueError: if DATABASE_URL is missing or empty.
        psycopg.OperationalError: if the database cannot be reached.
    """

    # 1. Read the connection string from the environment
    database_url = os.getenv("DATABASE_URL")

    # 2. Stop with a clear message if it is missing or empty
    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing or empty. "
            "Check that the .env file exists at the project root "
            "and contains a line DATABASE_URL=..."
        )

    # 3. Open the connection and return it (no "with" here: the caller closes it)
    conn = psycopg.connect(database_url)
    return conn


def run_sql_file(file_name):
    """
    Execute a SQL file from the sql/ folder on the Neon database.

    The whole file runs in one transaction: it is committed at the end
    if everything succeeds, and rolled back if an error occurs.

    Args:
        file_name (str): name of the file in the sql/ folder,
            e.g. "01_create_raw_table.sql".

    Returns:
        None

    Raises:
        FileNotFoundError: if the file does not exist in sql/.
        psycopg.Error: if the SQL fails on the database.
    """

    # 1. Build the path to the file in the sql/ folder
    sql_path = SQL_FOLDER / file_name

    # 2. Read the file as text
    sql_text = sql_path.read_text(encoding="utf-8")

    # 3. Execute the SQL (the connection "with" commits automatically at the end)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)


def run_all_sql_files():
    """
    Run every SQL file of the sql/ folder, in name order (01_, 02_, ...).

    All setup files use IF NOT EXISTS or OR REPLACE, so this can be run
    several times safely.

    Returns:
        int: number of SQL files executed.
    """

    # 1. Find all .sql files of the sql/ folder, sorted by name
    sql_files = sorted(SQL_FOLDER.glob("*.sql"))

    # 2. Run them one by one
    for sql_file in sql_files:
        run_sql_file(sql_file.name)
        logger.info(f"Executed {sql_file.name}")

    return len(sql_files)


def upsert_records(records):
    """
    Insert or update imbalance price records in raw.imbalance_prices.

    Each record is matched on its datetime (primary key):
    a new datetime is inserted, an existing one is updated with the
    new values, and its loaded_at is set to the current time.
    Running it several times with the same records never creates duplicates.

    Args:
        records (list[dict]): records as returned by fetch_day or fetch_range,
            with the 10 API keys (datetime, resolutioncode, qualitystatus, ...).

    Returns:
        int: number of records sent to the database (0 if the list is empty).
    """

    # 1. Nothing to send: do not open a connection
    if not records:
        return 0

    # 2. Send all records in one transaction
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(UPSERT_QUERY, records)

    # 3. Return the number of records sent
    return len(records)


def run_quality_tests():
    """
    Run every data quality test of the tests/sql/ folder.

    Each test file is a SELECT that returns the rows that FAIL the test:
    0 rows means the test passed.

    Returns:
        int: number of tests that passed (all of them, if no error is raised).

    Raises:
        RuntimeError: if at least one test returned rows.
    """

    # 1. Find all test files, sorted by name
    test_files = sorted(TESTS_FOLDER.glob("*.sql"))

    # Stop if no test was found: an empty test suite must never look like a success
    if len(test_files) == 0:
        raise RuntimeError(f"No quality test found in {TESTS_FOLDER}")

    # 2. Run each test and count the failures
    failed_tests = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            for test_file in test_files:
                sql_text = test_file.read_text(encoding="utf-8")
                cur.execute(sql_text)
                failing_rows = cur.fetchall()

                if len(failing_rows) == 0:
                    logger.info(f"PASSED  {test_file.name}")
                else:
                    logger.error(
                        f"FAILED  {test_file.name}: {len(failing_rows)} failing rows, "
                        f"first one: {failing_rows[0]}"
                    )
                    failed_tests.append(test_file.name)

    # 3. Stop the run if any test failed
    if len(failed_tests) > 0:
        raise RuntimeError(f"{len(failed_tests)} quality test(s) failed: {failed_tests}")

    return len(test_files)


if __name__ == "__main__":
    # Setup and checks: python src/db.py
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # 1. Create or update the tables and views
    run_all_sql_files()

    # 2. Check the data
    run_quality_tests()