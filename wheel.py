#!/usr/bin/env python3
"""Wheel strategy stock screener — CLI entrypoint.

Usage:
    python wheel.py AAPL
    python wheel.py F --config config/thresholds.yaml

Exit codes:
    0 — STRONG CANDIDATE or ACCEPTABLE
    1 — DO NOT WHEEL
    2 — Error (bad ticker, API failure, missing token, etc.)
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="wheel",
        description="Evaluate a stock ticker as a wheel strategy candidate.",
    )
    parser.add_argument(
        "ticker",
        help="Stock ticker symbol (e.g. AAPL, F, GME)",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Path to a custom thresholds.yaml (default: config/thresholds.yaml)",
    )
    args = parser.parse_args()

    # Import here so CLI startup is fast even before deps are verified
    try:
        from wheel_screener.scoring import run_screen, Verdict
        from wheel_screener.report import print_report
    except ImportError as exc:
        print(f"Error: missing dependency — {exc}", file=sys.stderr)
        print("Run:  pip install -r requirements.txt", file=sys.stderr)
        return 2

    try:
        result = run_screen(args.ticker, config_path=args.config)
    except Exception as exc:
        print(f"Error during screening: {exc}", file=sys.stderr)
        return 2

    print_report(result)

    if result.error:
        return 2

    from wheel_screener.scoring import Verdict
    if result.verdict == Verdict.DO_NOT_WHEEL:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
