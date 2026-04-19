"""Check #2 — Stock price range."""

from __future__ import annotations

from typing import Any

from .base import CheckResult, Status


def check_price_range(
    price: float | None,
    config: dict[str, Any],
) -> CheckResult:
    cfg = config["stock_price"]
    low: float = cfg["pass_min"]
    high: float = cfg["pass_max"]

    if price is None:
        return CheckResult(
            name="Stock price",
            status=Status.CAUTION,
            value="unavailable",
            threshold=f"${low:.0f}–${high:.0f}",
            note="Price data unavailable — manual check recommended",
        )

    fmt = f"${price:.2f}"

    if low <= price <= high:
        return CheckResult(
            name="Stock price",
            status=Status.PASS,
            value=fmt,
            threshold=f"${low:.0f}–${high:.0f}",
            note="Price in target range for cash-secured puts",
        )
    elif price < low:
        return CheckResult(
            name="Stock price",
            status=Status.CAUTION,
            value=fmt,
            threshold=f"${low:.0f}–${high:.0f}",
            note=f"Below ${low:.0f} — small premium per contract, high assignment risk",
        )
    else:
        return CheckResult(
            name="Stock price",
            status=Status.CAUTION,
            value=fmt,
            threshold=f"${low:.0f}–${high:.0f}",
            note=f"Above ${high:.0f} — high capital requirement per contract (100 shares)",
        )
