"""yfinance wrapper — fundamentals, price history, earnings dates, headlines.

All public functions return None (or an empty list) on failure so that the
check layer can report "unavailable" rather than crashing the whole run.
"""

from __future__ import annotations

import datetime
from typing import Any

import pandas as pd
import yfinance as yf


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _ticker(symbol: str) -> yf.Ticker:
    return yf.Ticker(symbol.upper())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_fundamentals(symbol: str) -> dict[str, Any] | None:
    """Return a dict with market_cap, sector, forward_pe.

    Returns None if the ticker is invalid or yfinance fails completely.
    Missing individual fields are represented as None inside the dict.
    """
    try:
        info = _ticker(symbol).info
        if not info or info.get("trailingPegRatio") is None and info.get("marketCap") is None:
            # yfinance sometimes returns a skeleton dict for unknown tickers
            pass
        return {
            "market_cap": info.get("marketCap"),
            "sector": info.get("sector"),
            "forward_pe": info.get("forwardPE"),
            "short_name": info.get("shortName"),
        }
    except Exception:
        return None


def get_price_history(
    symbol: str, period: str = "1y"
) -> pd.DataFrame | None:
    """Return a DataFrame of OHLCV data for the given period.

    Index is a DatetimeIndex.  Returns None on failure.
    """
    try:
        hist = _ticker(symbol).history(period=period)
        if hist.empty:
            return None
        return hist
    except Exception:
        return None


def get_earnings_date(symbol: str) -> datetime.date | None:
    """Return the next earnings date, or None if not available."""
    try:
        t = _ticker(symbol)
        # Prefer calendar (returns a dict with 'Earnings Date' key)
        cal = t.calendar
        if cal is not None:
            # calendar can be a dict or a DataFrame depending on yfinance version
            if isinstance(cal, dict):
                raw = cal.get("Earnings Date")
                if raw:
                    if isinstance(raw, (list, tuple)):
                        raw = raw[0]
                    if hasattr(raw, "date"):
                        return raw.date()
                    return pd.Timestamp(raw).date()
            elif isinstance(cal, pd.DataFrame) and not cal.empty:
                # Older yfinance returns transposed DataFrame
                try:
                    raw = cal.loc["Earnings Date"].iloc[0]
                    return pd.Timestamp(raw).date()
                except Exception:
                    pass

        # Fallback: get_earnings_dates() returns a DataFrame with upcoming dates
        dates_df = t.get_earnings_dates(limit=4)
        if dates_df is not None and not dates_df.empty:
            today = datetime.date.today()
            for ts in dates_df.index:
                d = ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()
                if d >= today:
                    return d
    except Exception:
        pass
    return None


def get_recent_headlines(symbol: str, n: int = 5) -> list[dict[str, Any]]:
    """Return up to *n* recent news items from yfinance.

    Each item is a dict with at least a 'title' key.
    Returns an empty list on failure — the headlines check handles missing data.
    """
    try:
        news = _ticker(symbol).news
        if not news:
            return []
        return news[:n]
    except Exception:
        return []
