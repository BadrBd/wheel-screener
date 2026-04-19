"""Check #5 — Earnings window."""

from __future__ import annotations

import datetime
from typing import Any

from .base import CheckResult, Status


def check_earnings_window(
    earnings_date: datetime.date | None,
    config: dict[str, Any],
) -> CheckResult:
    cfg = config["earnings_window"]
    min_days: int = cfg["pass_min_days"]

    if earnings_date is None:
        return CheckResult(
            name="Earnings window",
            status=Status.CAUTION,
            value="unavailable",
            threshold=f"> {min_days} days away",
            note="Earnings date unavailable — verify manually before selling puts",
        )

    today = datetime.date.today()
    days_away = (earnings_date - today).days

    if days_away < 0:
        # Earnings date in the past — next date unknown
        return CheckResult(
            name="Earnings window",
            status=Status.CAUTION,
            value=f"{earnings_date} (past)",
            threshold=f"> {min_days} days away",
            note="Most recent earnings date is in the past — next date not confirmed",
        )
    elif days_away <= min_days:
        return CheckResult(
            name="Earnings window",
            status=Status.FAIL,
            value=f"{days_away} days away ({earnings_date})",
            threshold=f"> {min_days} days away",
            note=(
                f"Earnings in {days_away} days — IV crush risk and gap risk. "
                "Wait until after the announcement."
            ),
        )
    else:
        return CheckResult(
            name="Earnings window",
            status=Status.PASS,
            value=f"{days_away} days away ({earnings_date})",
            threshold=f"> {min_days} days away",
            note="Earnings far enough away — no immediate catalyst risk",
        )
