"""Unit tests for each check function.  No network calls — all data is synthetic."""

from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from wheel_screener.checks.base import Status
from wheel_screener.checks.earnings_window import check_earnings_window
from wheel_screener.checks.headlines import check_headlines
from wheel_screener.checks.iv_rank import check_iv_rank
from wheel_screener.checks.market_cap import check_market_cap
from wheel_screener.checks.premium_yield import (
    check_premium_yield,
    find_target_expiration,
    find_target_put,
)
from wheel_screener.checks.price_range import check_price_range
from wheel_screener.checks.sma_trend import check_sma_trend
from wheel_screener.config import load_config

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def config():
    return load_config()


# ---------------------------------------------------------------------------
# Check 1 — Market cap
# ---------------------------------------------------------------------------

class TestMarketCap:
    def test_pass_large_cap(self, config):
        r = check_market_cap(10e9, config)
        assert r.status == Status.PASS

    def test_caution_mid_cap(self, config):
        r = check_market_cap(3e9, config)
        assert r.status == Status.CAUTION

    def test_fail_small_cap(self, config):
        r = check_market_cap(500e6, config)
        assert r.status == Status.FAIL

    def test_caution_none(self, config):
        r = check_market_cap(None, config)
        assert r.status == Status.CAUTION

    def test_boundary_exactly_5b(self, config):
        r = check_market_cap(5e9, config)
        assert r.status == Status.PASS


# ---------------------------------------------------------------------------
# Check 2 — Stock price
# ---------------------------------------------------------------------------

class TestPriceRange:
    def test_pass_in_range(self, config):
        r = check_price_range(75.0, config)
        assert r.status == Status.PASS

    def test_caution_below_range(self, config):
        r = check_price_range(5.0, config)
        assert r.status == Status.CAUTION

    def test_caution_above_range(self, config):
        r = check_price_range(500.0, config)
        assert r.status == Status.CAUTION

    def test_caution_none(self, config):
        r = check_price_range(None, config)
        assert r.status == Status.CAUTION

    def test_pass_at_boundary_low(self, config):
        r = check_price_range(20.0, config)
        assert r.status == Status.PASS

    def test_pass_at_boundary_high(self, config):
        r = check_price_range(150.0, config)
        assert r.status == Status.PASS


# ---------------------------------------------------------------------------
# Check 3 — IV Rank
# ---------------------------------------------------------------------------

class TestIVRank:
    def test_pass_in_range(self, config):
        r = check_iv_rank(45.0, "hv-proxy", config)
        assert r.status == Status.PASS

    def test_caution_above_60(self, config):
        r = check_iv_rank(65.0, "hv-proxy", config)
        assert r.status == Status.CAUTION

    def test_caution_above_70(self, config):
        r = check_iv_rank(80.0, "hv-proxy", config)
        assert r.status == Status.CAUTION

    def test_fail_below_threshold(self, config):
        r = check_iv_rank(10.0, "hv-proxy", config)
        assert r.status == Status.FAIL

    def test_caution_none(self, config):
        r = check_iv_rank(None, "unavailable", config)
        assert r.status == Status.CAUTION


# ---------------------------------------------------------------------------
# Check 4 — SMA trend
# ---------------------------------------------------------------------------

def _make_history(prices: list[float]) -> pd.DataFrame:
    """Build a minimal yfinance-like price history DataFrame."""
    # Generate enough business days then trim to match the price list length,
    # avoiding off-by-one errors when today falls on a weekend/holiday.
    dates = pd.bdate_range(end=pd.Timestamp.today(), periods=len(prices) + 5)
    dates = dates[-len(prices):]
    return pd.DataFrame({"Close": prices}, index=dates)


class TestSMATrend:
    def test_pass_above_rising_sma(self, config):
        # Steadily rising prices — price above SMA, SMA rising
        prices = list(np.linspace(100, 150, 252))
        hist = _make_history(prices)
        r = check_sma_trend(hist, 150.0, config)
        assert r.status == Status.PASS

    def test_fail_below_declining_sma(self, config):
        # Steadily declining prices — price below SMA, SMA declining
        prices = list(np.linspace(150, 50, 252))
        hist = _make_history(prices)
        r = check_sma_trend(hist, 50.0, config)
        assert r.status == Status.FAIL

    def test_caution_below_flat_sma(self, config):
        # Flat price history → flat SMA; pass a current price below SMA via arg.
        # SMA slope ≈ 0, price is below it → CAUTION (not declining).
        prices = [100.0] * 252
        hist = _make_history(prices)
        r = check_sma_trend(hist, 90.0, config)  # explicitly below SMA
        assert r.status == Status.CAUTION

    def test_caution_no_history(self, config):
        r = check_sma_trend(None, 100.0, config)
        assert r.status == Status.CAUTION

    def test_caution_insufficient_history(self, config):
        hist = _make_history([100.0] * 30)
        r = check_sma_trend(hist, 100.0, config)
        assert r.status == Status.CAUTION


# ---------------------------------------------------------------------------
# Check 5 — Earnings window
# ---------------------------------------------------------------------------

class TestEarningsWindow:
    def test_pass_far_away(self, config):
        future = datetime.date.today() + datetime.timedelta(days=60)
        r = check_earnings_window(future, config)
        assert r.status == Status.PASS

    def test_fail_within_30_days(self, config):
        soon = datetime.date.today() + datetime.timedelta(days=15)
        r = check_earnings_window(soon, config)
        assert r.status == Status.FAIL

    def test_fail_exactly_30_days(self, config):
        exact = datetime.date.today() + datetime.timedelta(days=30)
        r = check_earnings_window(exact, config)
        assert r.status == Status.FAIL

    def test_caution_none(self, config):
        r = check_earnings_window(None, config)
        assert r.status == Status.CAUTION

    def test_caution_past_date(self, config):
        past = datetime.date.today() - datetime.timedelta(days=5)
        r = check_earnings_window(past, config)
        assert r.status == Status.CAUTION


# ---------------------------------------------------------------------------
# Check 6 — Headlines
# ---------------------------------------------------------------------------

class TestHeadlines:
    def test_pass_with_news(self, config):
        news = [{"title": "Apple reports record earnings"}, {"title": "New iPhone launch"}]
        r = check_headlines(news, config)
        assert r.status == Status.PASS

    def test_pass_no_news(self, config):
        r = check_headlines([], config)
        assert r.status == Status.PASS

    def test_titles_in_note(self, config):
        news = [{"title": "Big headline"}]
        r = check_headlines(news, config)
        assert "Big headline" in r.note


# ---------------------------------------------------------------------------
# Check 7 — Premium yield
# ---------------------------------------------------------------------------

class TestPremiumYield:
    def _make_chain(self, strike: float, bid: float, ask: float, delta: float) -> list[dict]:
        return [
            {
                "option_type": "put",
                "strike": strike,
                "bid": bid,
                "ask": ask,
                "greeks": {"delta": -abs(delta)},
            }
        ]

    def test_pass_adequate_yield(self, config):
        # $170 strike, $2.50 mid → 1.47% yield → PASS
        chain = self._make_chain(170.0, 2.40, 2.60, 0.28)
        expirations = [
            (datetime.date.today() + datetime.timedelta(days=38)).isoformat()
        ]
        r = check_premium_yield(expirations, lambda _: chain, config)
        assert r.status == Status.PASS

    def test_fail_thin_yield(self, config):
        # $170 strike, $0.80 mid → 0.47% yield → FAIL
        chain = self._make_chain(170.0, 0.75, 0.85, 0.27)
        expirations = [
            (datetime.date.today() + datetime.timedelta(days=38)).isoformat()
        ]
        r = check_premium_yield(expirations, lambda _: chain, config)
        assert r.status == Status.FAIL

    def test_caution_no_expiration_in_window(self, config):
        # Expiration is 60 DTE — outside 30-45 window
        expirations = [
            (datetime.date.today() + datetime.timedelta(days=60)).isoformat()
        ]
        r = check_premium_yield(expirations, lambda _: [], config)
        assert r.status == Status.CAUTION

    def test_caution_no_puts_in_chain(self, config):
        expirations = [
            (datetime.date.today() + datetime.timedelta(days=38)).isoformat()
        ]
        r = check_premium_yield(expirations, lambda _: [], config)
        assert r.status == Status.CAUTION

    def test_find_target_expiration_picks_closest_to_midpoint(self):
        today = datetime.date.today()
        exps = [
            (today + datetime.timedelta(days=32)).isoformat(),
            (today + datetime.timedelta(days=37)).isoformat(),  # closest to midpoint 37.5
            (today + datetime.timedelta(days=44)).isoformat(),
        ]
        result = find_target_expiration(exps, 30, 45)
        assert result == exps[1]

    def test_find_target_put_picks_closest_delta(self):
        chain = [
            {"option_type": "put", "strike": 160.0, "bid": 1.0, "ask": 1.2, "greeks": {"delta": -0.20}},
            {"option_type": "put", "strike": 165.0, "bid": 1.5, "ask": 1.7, "greeks": {"delta": -0.27}},
            {"option_type": "put", "strike": 170.0, "bid": 2.0, "ask": 2.2, "greeks": {"delta": -0.35}},
        ]
        result = find_target_put(chain, 0.275, 0.10)
        assert result is not None
        assert result["strike"] == 165.0
