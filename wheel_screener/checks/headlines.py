"""Check #6 — Recent headlines (v1 stub).

V1: pull yfinance.news titles (top 5) and return Pass with a manual-review
note listing those titles.  No sentiment analysis — that is a v2 feature.

TODO (v2): integrate a sentiment model or keyword list to auto-flag
terms like "SEC investigation", "bankruptcy", "fraud", "recall", etc.
"""

from __future__ import annotations

from typing import Any

from .base import CheckResult, Status


def check_headlines(
    news_items: list[dict[str, Any]],
    config: dict[str, Any],  # unused in v1, kept for signature consistency
) -> CheckResult:
    if not news_items:
        return CheckResult(
            name="Headlines",
            status=Status.PASS,
            value="no recent news",
            threshold="no concerning items",
            note="No recent headlines found — manual review recommended",
        )

    titles = [item.get("title", "(no title)") for item in news_items]
    titles_str = " | ".join(titles)

    return CheckResult(
        name="Headlines",
        status=Status.PASS,
        value=f"{len(titles)} recent items",
        threshold="no concerning items",
        note=f"Manual review recommended — titles: {titles_str}",
    )
