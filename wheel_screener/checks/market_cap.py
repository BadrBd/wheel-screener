"""Check #1 — Market cap."""

from __future__ import annotations

from typing import Any

from .base import CheckResult, Status


def check_market_cap(
    market_cap: float | None,
    config: dict[str, Any],
) -> CheckResult:
    cfg = config["market_cap"]
    pass_min: float = cfg["pass_min"]
    caution_min: float = cfg["caution_min"]

    if market_cap is None:
        return CheckResult(
            name="Market cap",
            status=Status.CAUTION,
            value="unavailable",
            threshold=f"> ${pass_min / 1e9:.0f}B required",
            note="Market cap data unavailable — manual check recommended",
        )

    if market_cap >= pass_min:
        label = _fmt(market_cap)
        return CheckResult(
            name="Market cap",
            status=Status.PASS,
            value=label,
            threshold=f"> ${pass_min / 1e9:.0f}B required",
            note=f"Large-cap stock — adequate liquidity expected",
        )
    elif market_cap >= caution_min:
        label = _fmt(market_cap)
        return CheckResult(
            name="Market cap",
            status=Status.CAUTION,
            value=label,
            threshold=f"> ${pass_min / 1e9:.0f}B preferred",
            note=f"Mid-cap — options liquidity may be thinner",
        )
    else:
        label = _fmt(market_cap)
        return CheckResult(
            name="Market cap",
            status=Status.FAIL,
            value=label,
            threshold=f"> ${caution_min / 1e9:.0f}B minimum",
            note=f"Small-cap — options likely illiquid or wide spreads",
        )


def _fmt(cap: float) -> str:
    if cap >= 1e12:
        return f"${cap / 1e12:.2f}T"
    if cap >= 1e9:
        return f"${cap / 1e9:.1f}B"
    return f"${cap / 1e6:.0f}M"
