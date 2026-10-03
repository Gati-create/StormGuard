"""SQLite access layer. Thread-safe connection factory + schema bootstrap."""
import os
import sqlite3

DB_PATH = os.environ.get(
    "RIDESHIELD_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rideshield.db"),
)
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(path=None):
    conn = connect(path)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        conn.executescript(fh.read())
    conn.commit()
    return conn
