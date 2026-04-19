"""SQLite connection factory and schema migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

# Default DB location: <repo_root>/data/screens.db
_DEFAULT_DB = Path(__file__).parent.parent.parent / "data" / "screens.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS screens (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker        TEXT NOT NULL,
    screened_at   TEXT NOT NULL,
    verdict       TEXT NOT NULL,
    price         REAL,
    iv_rank       REAL,
    market_cap    REAL,
    payload_json  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_screens_ticker_time
    ON screens (ticker, screened_at DESC);
CREATE INDEX IF NOT EXISTS idx_screens_time
    ON screens (screened_at DESC);
"""


def get_connection(db_path: Path = _DEFAULT_DB) -> sqlite3.Connection:
    """Return an open connection with row_factory set, running migrations on first use."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


DEFAULT_DB_PATH = _DEFAULT_DB
