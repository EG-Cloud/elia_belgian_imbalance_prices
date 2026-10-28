import os

import psycopg
from dotenv import load_dotenv

# Load the variables from .env into the environment
load_dotenv()


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


if __name__ == "__main__":
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            result = cur.fetchone()
            print(result[0])