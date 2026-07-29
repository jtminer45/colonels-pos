"""
Shared SQLite connection helper for Colonel's Bakery and Restaurant POS.

Both the Streamlit dashboard and the FastAPI backend (used by the till PWA)
import this module so there is exactly one definition of "where the database
lives" and "how a connection is configured." When this moves to a networked
Raspberry Pi deployment later, only the FastAPI backend needs to run on the
Pi — this module does not change.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "colonels_pos.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

# Single physical location, single timezone, no DST in Nigeria — store and
# display timestamps in local time directly rather than converting from UTC
# at every read site.
LAGOS_TZ = ZoneInfo("Africa/Lagos")

VAT_RATE = 0.075  # Nigerian VAT, 7.5%


def get_connection() -> sqlite3.Connection:
    """Open a connection with sane defaults. Callers are responsible for closing it."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL allows the dashboard (reader) and till backend (writer) to access
    # the same file concurrently without blocking each other.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
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
    print(f"Database initialized at {DB_PATH}")
