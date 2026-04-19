"""Check #7 — Premium yield at 0.25–0.30 delta put, 30–45 DTE."""

from __future__ import annotations

import datetime
from typing import Any

from .base import CheckResult, Status


def _dte(expiration_str: str) -> int:
    """Return days to expiration from today."""
    exp = datetime.date.fromisoformat(expiration_str)
    return (exp - datetime.date.today()).days


def find_target_expiration(
    expirations: list[str],
    dte_min: int,
    dte_max: int,
) -> str | None:
    """Return the expiration date string closest to the midpoint of the DTE range."""
    target_dte = (dte_min + dte_max) / 2
    candidates = [e for e in expirations if dte_min <= _dte(e) <= dte_max]
    if not candidates:
        return None
    return min(candidates, key=lambda e: abs(_dte(e) - target_dte))


def find_target_put(
    chain: list[dict[str, Any]],
    target_delta: float,
    delta_tolerance: float,
) -> dict[str, Any] | None:
    """Find the put contract whose delta is closest to *target_delta* (negative).

    Tradier Greeks expose delta as a signed float (puts are negative).
    We compare absolute values.
    """
    puts = [
        c for c in chain
        if c.get("option_type") == "put"
        and c.get("greeks") is not None
        and c["greeks"].get("delta") is not None
    ]
    if not puts:
        return None

    # Sort by how close abs(delta) is to target_delta
    def dist(c: dict[str, Any]) -> float:
        d = abs(c["greeks"]["delta"])
        return abs(d - target_delta)

    best = min(puts, key=dist)
    best_delta = abs(best["greeks"]["delta"])

    # Reject if outside the tolerance band
    if abs(best_delta - target_delta) > delta_tolerance:
        return None

    return best


def check_premium_yield(
    expirations: list[str],
    option_chain_fn: Any,   # callable(expiration: str) -> list[dict]
    config: dict[str, Any],
) -> CheckResult:
    """Find the 0.25–0.30Δ put in the 30–45 DTE window and evaluate premium yield.

    *option_chain_fn* is a callable that accepts an expiration date string and
    returns a list of option contract dicts (avoids importing the API client here).
    """
    cfg = config["premium_yield"]
    target_delta: float = cfg["target_delta"]
    delta_tol: float = cfg["delta_tolerance"]
    dte_min: int = cfg["dte_min"]
    dte_max: int = cfg["dte_max"]
    pass_yield: float = cfg["pass_yield"]

    # --- find target expiration ---
    target_exp = find_target_expiration(expirations, dte_min, dte_max)
    if target_exp is None:
        return CheckResult(
            name="Premium yield",
            status=Status.CAUTION,
            value="no expiration in range",
            threshold=f"≥ {pass_yield * 100:.0f}% of strike",
            note=f"No expiration found in {dte_min}–{dte_max} DTE window — check manually",
        )

    dte = _dte(target_exp)

    # --- fetch option chain ---
    try:
        chain = option_chain_fn(target_exp)
    except Exception as exc:
        return CheckResult(
            name="Premium yield",
            status=Status.CAUTION,
            value="chain unavailable",
            threshold=f"≥ {pass_yield * 100:.0f}% of strike",
            note=f"Could not fetch options chain for {target_exp}: {exc}",
        )

    # --- find target put ---
    contract = find_target_put(chain, target_delta, delta_tol)
    if contract is None:
        return CheckResult(
            name="Premium yield",
            status=Status.CAUTION,
            value="no suitable put found",
            threshold=f"≥ {pass_yield * 100:.0f}% of strike",
            note=(
                f"No put with delta ≈ {target_delta:.2f} found in {target_exp} chain "
                f"(tolerance ±{delta_tol:.2f}) — check manually"
            ),
        )

    bid = contract.get("bid", 0) or 0
    ask = contract.get("ask", 0) or 0
    strike = contract.get("strike", 0) or 0
    actual_delta = abs(contract["greeks"]["delta"])

    if strike == 0:
        return CheckResult(
            name="Premium yield",
            status=Status.CAUTION,
            value="invalid contract data",
            threshold=f"≥ {pass_yield * 100:.0f}% of strike",
            note="Strike price is zero in API response — data error",
        )

    premium = (bid + ask) / 2
    yield_pct = premium / strike
    yield_fmt = f"{yield_pct * 100:.2f}%"

    # Store trade details on the result for the report to use
    result = CheckResult(
        name="Premium yield",
        status=Status.PASS if yield_pct >= pass_yield else Status.FAIL,
        value=f"{yield_fmt} of strike (${premium:.2f} mid, Δ{actual_delta:.2f}, {dte} DTE)",
        threshold=f"≥ {pass_yield * 100:.0f}% of strike",
        note=(
            f"{'Meets' if yield_pct >= pass_yield else 'Below'} minimum yield. "
            f"Strike ${strike:.2f}, exp {target_exp}"
        ),
    )

    # Attach trade metadata as extra attributes for the report
    result.trade_expiration = target_exp          # type: ignore[attr-defined]
    result.trade_strike = strike                  # type: ignore[attr-defined]
    result.trade_delta = actual_delta             # type: ignore[attr-defined]
    result.trade_dte = dte                        # type: ignore[attr-defined]
    result.trade_premium = premium                # type: ignore[attr-defined]
    result.trade_min_premium = strike * pass_yield  # type: ignore[attr-defined]

    return result
