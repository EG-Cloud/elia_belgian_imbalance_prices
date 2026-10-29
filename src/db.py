import os
from pathlib import Path  # NEW: built into Python, so in the first group

import psycopg
from dotenv import load_dotenv

# Load the variables from .env into the environment
load_dotenv()

# project root, two levels above this file (src/db.py -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


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


if __name__ == "__main__":
    run_sql_file("01_create_raw_table.sql")
    print("SQL file executed")