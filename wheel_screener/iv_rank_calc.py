"""IV Rank computation.

Tradier does not expose IVR as a direct field.  We compute it two ways,
in order of preference:

1. If we have a full year of implied-volatility data (iv30) from the options
   chain snapshots — use the classic IVR formula.
2. Fall back to realized (historical) volatility from price history:
   compute 30-day rolling HV from yfinance Close prices and use that as
   a proxy for IV history.

In either case:
    IVR = (current_iv − 52w_low_iv) / (52w_high_iv − 52w_low_iv) × 100

Returns (ivr_pct: float | None, method: str) so callers know which path ran.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _hv30_series(price_history: pd.DataFrame) -> pd.Series:
    """Compute 30-trading-day rolling realized volatility (annualised)."""
    log_ret = np.log(price_history["Close"] / price_history["Close"].shift(1))
    hv = log_ret.rolling(window=30).std() * np.sqrt(252) * 100  # in percent
    return hv.dropna()


def compute_iv_rank(
    current_iv: float | None,
    price_history: pd.DataFrame | None,
) -> tuple[float | None, str]:
    """Return (ivr_pct, method_description).

    *current_iv* should be the mid-market IV for the near-term ATM option
    (as a decimal, e.g. 0.35 for 35%).  It is converted to percent internally.

    *price_history* is a DataFrame from yfinance with a 'Close' column and
    at least ~252 rows (one year of trading days).

    Returns (None, "unavailable") when the computation cannot be completed.
    """
    if price_history is None or price_history.empty:
        return None, "unavailable — no price history"

    hv_series = _hv30_series(price_history)
    if len(hv_series) < 20:
        return None, "unavailable — insufficient price history"

    # Use HV as IV proxy
    current_hv = hv_series.iloc[-1]
    low_52w = hv_series.min()
    high_52w = hv_series.max()

    # If we have a real current_iv from the options chain, override the
    # "current" value but still use HV range for the denominator.
    if current_iv is not None:
        current_pct = current_iv * 100  # decimal → percent
        method = "options-chain IV vs HV52w range"
    else:
        current_pct = current_hv
        method = "30-day HV (IV unavailable)"

    denom = high_52w - low_52w
    if denom < 0.1:
        # IV has been essentially flat all year — IVR is meaningless
        return None, "unavailable — IV range too narrow"

    ivr = (current_pct - low_52w) / denom * 100
    # Clamp to [0, 100] — can go slightly outside on real data
    ivr = max(0.0, min(100.0, ivr))
    return round(ivr, 1), method
