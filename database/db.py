"""
Shared PostgreSQL connection helper for Colonel's Bakery and Restaurant POS.

Both the Streamlit dashboard and the FastAPI backend (used by the till PWA)
import this module so there is exactly one definition of "where the database
lives" and "how a connection is configured."

Originally this was a local SQLite file (see git history) so the whole
system could run offline on one laptop with zero setup. It was migrated to
Postgres to support hosting the backend/dashboard on Render, where the
filesystem is not reliably persistent across deploys/restarts. The
connection URL now comes from the DATABASE_URL environment variable —
Render injects this automatically when a Postgres instance is attached to
a service; for local development, set it in a .env file or your shell.

`DictConnection` below adds a thin `.execute()` convenience method that
mimics sqlite3.Connection's — it's what lets the rest of the codebase keep
writing `conn.execute(sql, params).fetchone()["col"]` almost unchanged
across the SQLite -> Postgres migration.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extensions
import psycopg2.extras
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"

# Local dev convenience only — Render sets real environment variables
# directly, it does not read a .env file. Safe no-op if the file is absent.
load_dotenv(BASE_DIR.parent / ".env")

# Single physical location, single timezone, no DST in Nigeria — store and
# display timestamps in local time directly rather than converting from UTC
# at every read site.
LAGOS_TZ = ZoneInfo("Africa/Lagos")

VAT_RATE = 0.075  # Nigerian VAT, 7.5%


class DictConnection(psycopg2.extensions.connection):
    """psycopg2 connection whose .execute() mirrors sqlite3.Connection.execute()
    — creates a cursor, runs the query, and returns it — so call sites written
    against sqlite3 (conn.execute(sql, params).fetchone()["col"]) keep working.
    Rows are dict-like (RealDictRow) so column-name access (`row["col"]`)
    behaves the same as sqlite3.Row did.
    """

    def execute(self, sql, params=None):
        cur = self.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return cur

    def executescript(self, sql: str):
        # Postgres has no sqlite-style executescript, but a plain (unparameterized)
        # multi-statement string works fine through a single cursor.execute() call —
        # used only for running schema.sql, which takes no parameters.
        cur = self.cursor()
        cur.execute(sql)
        return cur


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Set it to a Postgres connection string "
            "(Render injects this automatically when a database is attached "
            "to this service; for local dev, set it in your shell or a .env file)."
        )
    # Render (and some other hosts) hand out "postgres://" URLs; psycopg2
    # accepts both, but normalize for clarity in logs/errors.
    return url.replace("postgres://", "postgresql://", 1)


def get_connection() -> DictConnection:
    """Open a connection with sane defaults. Callers are responsible for closing it."""
    conn = psycopg2.connect(_database_url(), connection_factory=DictConnection)
    conn.autocommit = False
    return conn


def init_db() -> None:
    """Create all tables if they do not already exist. Safe to call repeatedly."""
    conn = get_connection()
    try:
        with open(SCHEMA_PATH, "r") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def now_local() -> datetime:
    return datetime.now(LAGOS_TZ)


def now_iso() -> str:
    """Timestamp string used for all *_at / timestamp columns."""
    return now_local().strftime("%Y-%m-%dT%H:%M:%S")


def today_str() -> str:
    """Date string ('YYYY-MM-DD') used for all *date* columns."""
    return now_local().strftime("%Y-%m-%d")


if __name__ == "__main__":
    init_db()
    print("Database initialized (Postgres).")
