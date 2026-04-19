#!/usr/bin/env python3
"""Flask web interface for the wheel strategy screener."""

from __future__ import annotations

import sys
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/screen", methods=["POST"])
def screen():
    data = request.get_json(force=True)
    ticker = (data.get("ticker") or "").strip().upper()

    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400

    try:
        from wheel_screener.scoring import run_screen, Verdict
        from wheel_screener.checks.base import Status
    except ImportError as exc:
        return jsonify({"error": f"Missing dependency: {exc}"}), 500

    try:
        result = run_screen(ticker)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    checks_out = []
    for c in result.checks:
        checks_out.append({
            "name": c.name,
            "status": c.status.value,   # "PASS" | "CAUTION" | "FAIL"
            "value": str(c.value),
            "threshold": c.threshold,
            "note": c.note,
        })

    trade = None
    if result.verdict != Verdict.DO_NOT_WHEEL and result.trade_expiration:
        trade = {
            "expiration": result.trade_expiration,
            "dte": result.trade_dte,
            "strike": result.trade_strike,
            "delta": result.trade_delta,
            "premium": result.trade_premium,
            "min_premium": result.trade_min_premium,
        }

    return jsonify({
        "symbol": result.symbol,
        "verdict": result.verdict.value,
        "checks": checks_out,
        "trade": trade,
        "error": result.error,
        "stock_price": result.stock_price,
        "ivr": result.ivr_value,
        "trend": result.trend,
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=9000)
