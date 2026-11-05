import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Load the variables from .env into the environment
load_dotenv()

# project root, two levels above this file (src/db.py -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

UPSERT_QUERY = """
    INSERT INTO 
        raw.imbalance_prices (datetime, resolutioncode, qualitystatus, ace, systemimbalance, alpha, 
        alpha_prime, marginalincrementalprice, marginaldecrementalprice, imbalanceprice)
    VALUES 
        (%(datetime)s,%(resolutioncode)s,%(qualitystatus)s,%(ace)s,%(systemimbalance)s,
        %(alpha)s,%(alpha_prime)s,%(marginalincrementalprice)s,%(marginaldecrementalprice)s,%(imbalanceprice)s)
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
    (loaded from .env locally, or provided by GitHub Actions later).

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
    sql_path = PROJECT_ROOT / "sql" / file_name

    # 2. Read the file as text
    sql_text = sql_path.read_text(encoding="utf-8")

    # 3. Execute the SQL (the connection "with" commits automatically at the end)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)


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

    if not records:
        return 0

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(UPSERT_QUERY, records)

    return len(records)

# if __name__ == "__main__":
#     # Create the raw schema and table (safe to run several times)
#     run_sql_file("01_create_raw_table.sql")
#     print("Raw table ready")

if __name__ == "__main__":
    # Create the raw schema and table (safe to run several times)
    run_sql_file("02_create_clean_view.sql")
    print("Clean table ready")