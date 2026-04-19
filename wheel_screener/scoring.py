"""Orchestrates data fetching, runs all checks, aggregates to a verdict.

This is the main entry point called by the CLI.  It returns a `ScreenResult`
pydantic model that the report module renders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .checks.base import CheckResult, Status
from .checks.earnings_window import check_earnings_window
from .checks.headlines import check_headlines
from .checks.iv_rank import check_iv_rank
from .checks.market_cap import check_market_cap
from .checks.premium_yield import check_premium_yield
from .checks.price_range import check_price_range
from .checks.sma_trend import check_sma_trend
from .config import load_config
from .data import tradier as tradier_mod
from .data import yfin
from .iv_rank_calc import compute_iv_rank


class Verdict(str, Enum):
    STRONG = "STRONG CANDIDATE"
    ACCEPTABLE = "ACCEPTABLE"
    DO_NOT_WHEEL = "DO NOT WHEEL"


@dataclass
class ScreenResult:
    symbol: str
    verdict: Verdict
    checks: list[CheckResult]
    error: str | None = None

    # Populated if a suitable trade was identified (premium_yield check passed/cautioned)
    trade_expiration: str | None = None
    trade_strike: float | None = None
    trade_delta: float | None = None
    trade_dte: int | None = None
    trade_premium: float | None = None
    trade_min_premium: float | None = None

    # Inputs for the delta/strike recommendation engine
    stock_price: float | None = None
    ivr_value: float | None = None   # 0–100
    trend: str | None = None          # "bullish" | "neutral" | "bearish"
    market_cap: float | None = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "verdict": self.verdict.value,
            "checks": [c.to_dict() for c in self.checks],
            "error": self.error,
            "trade_expiration": self.trade_expiration,
            "trade_strike": self.trade_strike,
            "trade_delta": self.trade_delta,
            "trade_dte": self.trade_dte,
            "trade_premium": self.trade_premium,
            "trade_min_premium": self.trade_min_premium,
            "stock_price": self.stock_price,
            "ivr_value": self.ivr_value,
            "trend": self.trend,
            "market_cap": self.market_cap,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScreenResult":
        from .checks.base import CheckResult
        return cls(
            symbol=d["symbol"],
            verdict=Verdict(d["verdict"]),
            checks=[CheckResult.from_dict(c) for c in d.get("checks", [])],
            error=d.get("error"),
            trade_expiration=d.get("trade_expiration"),
            trade_strike=d.get("trade_strike"),
            trade_delta=d.get("trade_delta"),
            trade_dte=d.get("trade_dte"),
            trade_premium=d.get("trade_premium"),
            trade_min_premium=d.get("trade_min_premium"),
            stock_price=d.get("stock_price"),
            ivr_value=d.get("ivr_value"),
            trend=d.get("trend"),
            market_cap=d.get("market_cap"),
        )


def _extract_current_iv(chain: list[dict[str, Any]]) -> float | None:
    """Pull mid-market IV from the ATM put closest to 0.50 delta."""
    puts = [
        c for c in chain
        if c.get("option_type") == "put"
        and c.get("greeks") is not None
        and c["greeks"].get("mid_iv") is not None
    ]
    if not puts:
        # Fall back to iv field on the contract itself
        all_puts = [c for c in chain if c.get("option_type") == "put" and c.get("iv")]
        if all_puts:
            atm = min(all_puts, key=lambda c: abs(abs(c.get("greeks", {}).get("delta", 0) or 0) - 0.5))
            return atm.get("iv")
        return None

    atm = min(puts, key=lambda c: abs(abs(c["greeks"].get("delta", 0) or 0) - 0.5))
    return atm["greeks"]["mid_iv"]


def run_screen(
    symbol: str,
    config_path: str | None = None,
    tradier_client: Any = None,
) -> ScreenResult:
    """Fetch all data once, run all checks, return a ScreenResult.

    *tradier_client* may be injected (e.g. a mock in tests).
    """
    config = load_config(config_path)
    symbol = symbol.upper()

    # ------------------------------------------------------------------
    # Initialise Tradier client
    # ------------------------------------------------------------------
    if tradier_client is None:
        try:
            tradier_client = tradier_mod.TradierClient()
        except tradier_mod.TradierError as exc:
            return ScreenResult(
                symbol=symbol,
                verdict=Verdict.DO_NOT_WHEEL,
                checks=[],
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Fetch data — each call wrapped so one failure doesn't kill the run
    # ------------------------------------------------------------------

    # Tradier quote
    tradier_price: float | None = None
    try:
        quote = tradier_client.get_quote(symbol)
        tradier_price = quote.get("last") or quote.get("close")
    except Exception:
        pass

    # yfinance fundamentals
    fundamentals = yfin.get_fundamentals(symbol)

    # Price history (1 year)
    price_history = yfin.get_price_history(symbol, period="1y")

    # Earnings date
    earnings_date = yfin.get_earnings_date(symbol)

    # Recent headlines
    headlines = yfin.get_recent_headlines(symbol)

    # Tradier expirations
    expirations: list[str] = []
    try:
        expirations = tradier_client.get_expirations(symbol)
    except Exception:
        pass

    # IV from near-term chain (for IVR computation)
    current_iv: float | None = None
    if expirations:
        # Use the nearest expiration for IV sampling
        try:
            near_chain = tradier_client.get_option_chain(symbol, expirations[0])
            current_iv = _extract_current_iv(near_chain)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Resolve price: prefer Tradier live quote, fall back to yfinance close
    # ------------------------------------------------------------------
    price: float | None = tradier_price
    if price is None and price_history is not None and not price_history.empty:
        price = float(price_history["Close"].iloc[-1])

    market_cap: float | None = fundamentals.get("market_cap") if fundamentals else None

    # ------------------------------------------------------------------
    # Run checks
    # ------------------------------------------------------------------
    checks: list[CheckResult] = []

    checks.append(check_market_cap(market_cap, config))
    checks.append(check_price_range(price, config))

    ivr, ivr_method = compute_iv_rank(current_iv, price_history)
    checks.append(check_iv_rank(ivr, ivr_method, config))

    checks.append(check_sma_trend(price_history, price, config))

    # Compute trend label for the recommendation engine
    trend: str | None = None
    if price is not None and price_history is not None and not price_history.empty:
        closes = price_history["Close"].dropna()
        if len(closes) >= 50:
            sma50 = float(closes.rolling(window=50).mean().iloc[-1])
            if price > sma50 * 1.02:
                trend = "bullish"
            elif price < sma50 * 0.98:
                trend = "bearish"
            else:
                trend = "neutral"

    checks.append(check_earnings_window(earnings_date, config))
    checks.append(check_headlines(headlines, config))

    # Premium yield — pass a lambda so check doesn't import the API client
    def fetch_chain(exp: str) -> list[dict[str, Any]]:
        return tradier_client.get_option_chain(symbol, exp)

    premium_result = check_premium_yield(expirations, fetch_chain, config)
    checks.append(premium_result)

    # ------------------------------------------------------------------
    # Aggregate verdict
    # ------------------------------------------------------------------
    statuses = {c.status for c in checks}

    if Status.FAIL in statuses:
        verdict = Verdict.DO_NOT_WHEEL
    elif Status.CAUTION in statuses:
        verdict = Verdict.ACCEPTABLE
    else:
        verdict = Verdict.STRONG

    # ------------------------------------------------------------------
    # Extract trade metadata if premium check has it
    # ------------------------------------------------------------------
    result = ScreenResult(
        symbol=symbol,
        verdict=verdict,
        checks=checks,
        stock_price=price,
        ivr_value=ivr,
        trend=trend,
        market_cap=market_cap,
    )

    if hasattr(premium_result, "trade_expiration"):
        result.trade_expiration = getattr(premium_result, "trade_expiration", None)
        result.trade_strike = getattr(premium_result, "trade_strike", None)
        result.trade_delta = getattr(premium_result, "trade_delta", None)
        result.trade_dte = getattr(premium_result, "trade_dte", None)
        result.trade_premium = getattr(premium_result, "trade_premium", None)
        result.trade_min_premium = getattr(premium_result, "trade_min_premium", None)

    return result
