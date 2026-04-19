"""Tests for ScreenResult / CheckResult serialization round-trips."""

from __future__ import annotations

import json

import pytest

from wheel_screener.checks.base import CheckResult, Status
from wheel_screener.scoring import ScreenResult, Verdict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_check(status: Status = Status.PASS) -> CheckResult:
    return CheckResult(
        name="Market cap",
        status=status,
        value="$3.0T",
        threshold="> $5B required",
        note="Passes minimum market cap",
    )


def _make_result(
    verdict: Verdict = Verdict.ACCEPTABLE,
    with_trade: bool = True,
) -> ScreenResult:
    checks = [_make_check(Status.PASS), _make_check(Status.CAUTION), _make_check(Status.FAIL)]
    return ScreenResult(
        symbol="AAPL",
        verdict=verdict,
        checks=checks,
        error=None,
        trade_expiration="2026-05-16" if with_trade else None,
        trade_strike=170.0 if with_trade else None,
        trade_delta=0.28 if with_trade else None,
        trade_dte=37 if with_trade else None,
        trade_premium=2.5 if with_trade else None,
        trade_min_premium=1.7 if with_trade else None,
        stock_price=178.23,
        ivr_value=45.0,
        trend="bullish",
        market_cap=3_000_000_000_000.0,
    )


# ---------------------------------------------------------------------------
# CheckResult serialization
# ---------------------------------------------------------------------------


class TestCheckResultSerialization:
    @pytest.mark.parametrize("status", list(Status))
    def test_round_trip_all_statuses(self, status: Status) -> None:
        original = _make_check(status)
        restored = CheckResult.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.status == original.status
        assert restored.value == str(original.value)
        assert restored.threshold == original.threshold
        assert restored.note == original.note

    def test_to_dict_status_is_string(self) -> None:
        d = _make_check(Status.PASS).to_dict()
        assert d["status"] == "PASS"
        assert isinstance(d["status"], str)

    def test_from_dict_invalid_status_raises(self) -> None:
        d = _make_check().to_dict()
        d["status"] = "INVALID"
        with pytest.raises(ValueError):
            CheckResult.from_dict(d)


# ---------------------------------------------------------------------------
# ScreenResult serialization
# ---------------------------------------------------------------------------


class TestScreenResultSerialization:
    @pytest.mark.parametrize("verdict", list(Verdict))
    def test_round_trip_all_verdicts(self, verdict: Verdict) -> None:
        original = _make_result(verdict=verdict)
        restored = ScreenResult.from_dict(original.to_dict())

        assert restored.symbol == original.symbol
        assert restored.verdict == original.verdict
        assert len(restored.checks) == len(original.checks)
        assert restored.stock_price == original.stock_price
        assert restored.ivr_value == original.ivr_value
        assert restored.trend == original.trend
        assert restored.market_cap == original.market_cap

    def test_round_trip_with_trade(self) -> None:
        original = _make_result(with_trade=True)
        restored = ScreenResult.from_dict(original.to_dict())

        assert restored.trade_expiration == original.trade_expiration
        assert restored.trade_strike == original.trade_strike
        assert restored.trade_delta == original.trade_delta
        assert restored.trade_dte == original.trade_dte
        assert restored.trade_premium == original.trade_premium
        assert restored.trade_min_premium == original.trade_min_premium

    def test_round_trip_no_trade(self) -> None:
        original = _make_result(with_trade=False)
        restored = ScreenResult.from_dict(original.to_dict())

        assert restored.trade_expiration is None
        assert restored.trade_strike is None
        assert restored.trade_delta is None
        assert restored.trade_dte is None
        assert restored.trade_premium is None
        assert restored.trade_min_premium is None

    def test_verdict_serialized_as_string(self) -> None:
        d = _make_result(Verdict.STRONG).to_dict()
        assert d["verdict"] == "STRONG CANDIDATE"
        assert isinstance(d["verdict"], str)

    def test_checks_order_preserved(self) -> None:
        original = _make_result()
        restored = ScreenResult.from_dict(original.to_dict())
        for orig_c, rest_c in zip(original.checks, restored.checks):
            assert orig_c.status == rest_c.status

    def test_json_dumps_roundtrip(self) -> None:
        """Verify the dict is JSON-serializable (no datetime objects etc.)."""
        original = _make_result()
        as_json = json.dumps(original.to_dict())
        restored = ScreenResult.from_dict(json.loads(as_json))
        assert restored.symbol == original.symbol
        assert restored.verdict == original.verdict

    def test_round_trip_with_error(self) -> None:
        result = ScreenResult(
            symbol="ERR",
            verdict=Verdict.DO_NOT_WHEEL,
            checks=[],
            error="API timeout",
        )
        restored = ScreenResult.from_dict(result.to_dict())
        assert restored.error == "API timeout"
        assert restored.checks == []

    def test_missing_optional_fields_default_none(self) -> None:
        """from_dict should tolerate missing optional keys (forward-compat)."""
        minimal = {
            "symbol": "XYZ",
            "verdict": "DO NOT WHEEL",
            "checks": [],
        }
        restored = ScreenResult.from_dict(minimal)
        assert restored.symbol == "XYZ"
        assert restored.market_cap is None
        assert restored.trend is None
