"""ScreenRepository — CRUD operations against the screens table."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db import DEFAULT_DB_PATH, get_connection
from .models import ScreenRecord


class ScreenRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        return get_connection(self._db_path)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ScreenRecord:
        raw_ts = row["screened_at"]
        # Parse ISO 8601 with optional trailing 'Z'
        screened_at = datetime.fromisoformat(raw_ts.rstrip("Z"))
        return ScreenRecord(
            id=row["id"],
            ticker=row["ticker"],
            screened_at=screened_at,
            verdict=row["verdict"],
            price=row["price"],
            iv_rank=row["iv_rank"],
            market_cap=row["market_cap"],
            payload_json=row["payload_json"],
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, result) -> int:  # result: ScreenResult (avoid circular import)
        """Serialize and insert a new screen row. Returns the new row id."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = json.dumps(result.to_dict())
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO screens
                    (ticker, screened_at, verdict, price, iv_rank, market_cap, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.symbol.upper(),
                    now,
                    result.verdict.value,
                    result.stock_price,
                    result.ivr_value,
                    result.market_cap,
                    payload,
                ),
            )
            conn.commit()
            return cur.lastrowid

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, screen_id: int) -> ScreenRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM screens WHERE id = ?", (screen_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def get_latest_for_ticker(self, ticker: str) -> ScreenRecord | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM screens WHERE ticker = ? ORDER BY screened_at DESC, id DESC LIMIT 1",
                (ticker.upper(),),
            ).fetchone()
        return self._row_to_record(row) if row else None

    def list_history(
        self,
        ticker: str | None = None,
        limit: int = 200,
    ) -> list[ScreenRecord]:
        """Return rows ordered by screened_at DESC. Optionally filter by ticker."""
        if ticker is not None:
            sql = (
                "SELECT * FROM screens WHERE ticker = ? "
                "ORDER BY screened_at DESC LIMIT ?"
            )
            params: tuple = (ticker.upper(), limit)
        else:
            sql = "SELECT * FROM screens ORDER BY screened_at DESC LIMIT ?"
            params = (limit,)

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_tickers_with_counts(self) -> list[tuple[str, int, str]]:
        """Return (ticker, screen_count, latest_screened_at) sorted by latest DESC."""
        sql = """
            SELECT ticker,
                   COUNT(*)            AS screen_count,
                   MAX(screened_at)    AS latest_screened_at
            FROM screens
            GROUP BY ticker
            ORDER BY latest_screened_at DESC
        """
        with self._conn() as conn:
            rows = conn.execute(sql).fetchall()
        return [(r["ticker"], r["screen_count"], r["latest_screened_at"]) for r in rows]

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def clear_all(self) -> int:
        """Delete all rows. Returns number of rows deleted."""
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM screens")
            conn.commit()
            return cur.rowcount
