"""Check #4 — Price vs 50-day SMA trend."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .base import CheckResult, Status


def check_sma_trend(
    price_history: pd.DataFrame | None,
    current_price: float | None,
    config: dict[str, Any],
) -> CheckResult:
    cfg = config["sma_trend"]
    lookback: int = cfg["lookback_days"]
    slope_window: int = cfg["slope_window"]

    if price_history is None or price_history.empty:
        return CheckResult(
            name="50-day SMA trend",
            status=Status.CAUTION,
            value="unavailable",
            threshold="price above SMA",
            note="Price history unavailable — manual check recommended",
        )

    closes = price_history["Close"].dropna()
    if len(closes) < lookback:
        return CheckResult(
            name="50-day SMA trend",
            status=Status.CAUTION,
            value="insufficient data",
            threshold="price above SMA",
            note=f"Only {len(closes)} trading days of history — need {lookback}",
        )

    sma = closes.rolling(window=lookback).mean()
    current_sma = sma.iloc[-1]

    price = current_price if current_price is not None else closes.iloc[-1]
    above_sma = price >= current_sma

    # Slope: linear regression over last *slope_window* SMA values
    recent_sma = sma.dropna().iloc[-slope_window:]
    if len(recent_sma) >= slope_window:
        x = np.arange(len(recent_sma))
        slope = float(np.polyfit(x, recent_sma.values, 1)[0])
        declining = slope < 0
    else:
        slope = 0.0
        declining = False

    sma_fmt = f"${current_sma:.2f}"
    price_fmt = f"${price:.2f}"

    if above_sma:
        trend = "rising" if slope > 0 else "flat"
        return CheckResult(
            name="50-day SMA trend",
            status=Status.PASS,
            value=f"above SMA ({sma_fmt}), {trend}",
            threshold="price above 50-day SMA",
            note=f"Price {price_fmt} is above the 50-day SMA — bullish context for CSPs",
        )
    else:
        # Below SMA
        if declining:
            return CheckResult(
                name="50-day SMA trend",
                status=Status.FAIL,
                value=f"below SMA ({sma_fmt}), declining",
                threshold="price above 50-day SMA",
                note=(
                    f"Price {price_fmt} is below 50-day SMA and SMA is declining — "
                    "unfavourable trend for wheel strategy"
                ),
            )
        else:
            # Below but not declining — could be consolidating
            return CheckResult(
                name="50-day SMA trend",
                status=Status.CAUTION,
                value=f"below SMA ({sma_fmt}), flat",
                threshold="price above 50-day SMA",
                note=(
                    f"Price {price_fmt} is below 50-day SMA but SMA is not declining — "
                    "possible consolidation, watch closely"
                ),
            )
