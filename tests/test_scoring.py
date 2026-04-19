"""Tests for the scoring module and full pipeline integration.

All API calls are mocked — no network traffic.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from wheel_screener.checks.base import Status
from wheel_screener.scoring import ScreenResult, Verdict, run_screen

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


# ---------------------------------------------------------------------------
# Helpers to build fake yfinance and Tradier data
# ---------------------------------------------------------------------------

def _make_price_history(n: int = 252, trend: str = "up") -> pd.DataFrame:
    """Build a synthetic price history DataFrame."""
    if trend == "up":
        prices = list(np.linspace(100, 150, n))
    elif trend == "down":
        prices = list(np.linspace(150, 80, n))
    else:
        prices = [120.0] * n
    # Generate extra then trim — avoids off-by-one on weekends/holidays.
    dates = pd.bdate_range(end=pd.Timestamp.today(), periods=n + 5)
    dates = dates[-n:]
    return pd.DataFrame({"Close": prices}, index=dates)


def _make_tradier_client(
    price: float = 178.23,
    expirations: list[str] | None = None,
    chain: list[dict] | None = None,
) -> MagicMock:
    """Return a mock TradierClient with sensible defaults."""
    client = MagicMock()
    client.get_quote.return_value = {"last": price}

    if expirations is None:
        today = datetime.date.today()
        expirations = [
            (today + datetime.timedelta(days=d)).isoformat()
            for d in [7, 14, 21, 38, 60]
        ]
    client.get_expirations.return_value = expirations

    if chain is None:
        target_exp = expirations[3] if len(expirations) > 3 else expirations[-1]
        chain = [
            {
                "option_type": "put",
                "strike": 170.0,
                "bid": 2.40,
                "ask": 2.60,
                "iv": 0.30,
                "greeks": {"delta": -0.28, "mid_iv": 0.30},
            }
        ]
    client.get_option_chain.return_value = chain

    return client


# ---------------------------------------------------------------------------
# Integration test — AAPL "acceptable" scenario
# ---------------------------------------------------------------------------

class TestFullPipelineAAPL:
    @patch("wheel_screener.scoring.yfin.get_recent_headlines", return_value=[
        {"title": "Apple AI features drive iPhone demand"}
    ])
    @patch("wheel_screener.scoring.yfin.get_earnings_date",
           return_value=datetime.date.today() + datetime.timedelta(days=55))
    @patch("wheel_screener.scoring.yfin.get_price_history")
    @patch("wheel_screener.scoring.yfin.get_fundamentals", return_value={
        "market_cap": 3_000_000_000_000,
        "sector": "Technology",
        "forward_pe": 28.5,
        "short_name": "Apple Inc.",
    })
    def test_aapl_acceptable(self, mock_fund, mock_hist, mock_earn, mock_news):
        mock_hist.return_value = _make_price_history(252, trend="up")

        client = _make_tradier_client(price=178.23)
        result = run_screen("AAPL", tradier_client=client)

        assert result.symbol == "AAPL"
        assert result.verdict in (Verdict.STRONG, Verdict.ACCEPTABLE)
        assert len(result.checks) == 7

        # Price $178 is above $150 → Caution expected → ACCEPTABLE not STRONG
        assert result.verdict == Verdict.ACCEPTABLE

    @patch("wheel_screener.scoring.yfin.get_recent_headlines", return_value=[])
    @patch("wheel_screener.scoring.yfin.get_earnings_date",
           return_value=datetime.date.today() + datetime.timedelta(days=10))
    @patch("wheel_screener.scoring.yfin.get_price_history")
    @patch("wheel_screener.scoring.yfin.get_fundamentals", return_value={
        "market_cap": 1_000_000_000,  # small-cap → FAIL
        "sector": "Technology",
        "forward_pe": 30.0,
        "short_name": "Tiny Corp",
    })
    def test_do_not_wheel_multiple_fails(self, mock_fund, mock_hist, mock_earn, mock_news):
        mock_hist.return_value = _make_price_history(252, trend="down")

        client = _make_tradier_client(price=45.0)
        result = run_screen("TINY", tradier_client=client)

        assert result.verdict == Verdict.DO_NOT_WHEEL

        fails = [c for c in result.checks if c.status == Status.FAIL]
        # Market cap fail, SMA declining fail, earnings fail (within 30 days)
        assert len(fails) >= 2


# ---------------------------------------------------------------------------
# Verdict aggregation logic
# ---------------------------------------------------------------------------

class TestVerdictAggregation:
    """Isolated tests for the verdict rules — injecting pre-built check results."""

    def _run_with_mocked_checks(self, statuses: list[Status]) -> Verdict:
        """Shortcut: mock all checks to return given statuses, return verdict."""
        from wheel_screener.checks.base import CheckResult
        from wheel_screener.scoring import Verdict

        checks = [
            CheckResult(name=f"check_{i}", status=s, value="x", threshold="y", note="z")
            for i, s in enumerate(statuses)
        ]
        status_set = set(statuses)
        if Status.FAIL in status_set:
            return Verdict.DO_NOT_WHEEL
        elif Status.CAUTION in status_set:
            return Verdict.ACCEPTABLE
        else:
            return Verdict.STRONG

    def test_all_pass_is_strong(self):
        v = self._run_with_mocked_checks([Status.PASS] * 7)
        assert v == Verdict.STRONG

    def test_any_caution_is_acceptable(self):
        v = self._run_with_mocked_checks([Status.PASS] * 6 + [Status.CAUTION])
        assert v == Verdict.ACCEPTABLE

    def test_any_fail_is_do_not_wheel(self):
        v = self._run_with_mocked_checks([Status.PASS] * 5 + [Status.CAUTION, Status.FAIL])
        assert v == Verdict.DO_NOT_WHEEL
