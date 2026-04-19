"""Check #3 — IV Rank."""

from __future__ import annotations

from typing import Any

from .base import CheckResult, Status


def check_iv_rank(
    ivr: float | None,
    method: str,
    config: dict[str, Any],
) -> CheckResult:
    cfg = config["iv_rank"]
    pass_min: float = cfg["pass_min"]
    pass_max: float = cfg["pass_max"]
    caution_max: float = cfg["caution_max"]
    fail_below: float = cfg["fail_below"]

    if ivr is None:
        return CheckResult(
            name="IV Rank",
            status=Status.CAUTION,
            value="unavailable",
            threshold=f"{pass_min:.0f}–{pass_max:.0f}%",
            note=(
                f"IVR unavailable ({method}) — manual check recommended. "
                "See https://www.barchart.com/stocks/quotes/SYMBOL/volatility-greeks"
            ),
        )

    fmt = f"{ivr:.1f}%"
    threshold_str = f"{pass_min:.0f}–{pass_max:.0f}%"

    if pass_min <= ivr <= pass_max:
        return CheckResult(
            name="IV Rank",
            status=Status.PASS,
            value=fmt,
            threshold=threshold_str,
            note="IV Rank in the sweet spot — premiums are elevated but not alarming",
        )
    elif pass_max < ivr <= caution_max:
        return CheckResult(
            name="IV Rank",
            status=Status.CAUTION,
            value=fmt,
            threshold=threshold_str,
            note=f"Above {pass_max:.0f}% — IV elevated, check for upcoming catalyst",
        )
    elif ivr > caution_max:
        return CheckResult(
            name="IV Rank",
            status=Status.CAUTION,
            value=fmt,
            threshold=threshold_str,
            note=f"Above {caution_max:.0f}% — unusually high IV, something may be wrong",
        )
    else:  # ivr < fail_below
        return CheckResult(
            name="IV Rank",
            status=Status.FAIL,
            value=fmt,
            threshold=threshold_str,
            note=f"Below {fail_below:.0f}% — premiums too thin to justify wheel strategy",
        )
