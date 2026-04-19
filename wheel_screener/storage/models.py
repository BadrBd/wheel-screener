"""Dataclass mirroring a row in the screens table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ScreenRecord:
    id: int
    ticker: str
    screened_at: datetime  # UTC
    verdict: str           # e.g. "STRONG CANDIDATE"
    price: float | None
    iv_rank: float | None
    market_cap: float | None
    payload_json: str      # full serialized ScreenResult
