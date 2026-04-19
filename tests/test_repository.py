"""Tests for ScreenRepository — all use a temp SQLite file via tmp_path."""

from __future__ import annotations

from pathlib import Path

import pytest

from wheel_screener.checks.base import CheckResult, Status
from wheel_screener.scoring import ScreenResult, Verdict
from wheel_screener.storage.repository import ScreenRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    symbol: str = "AAPL",
    verdict: Verdict = Verdict.ACCEPTABLE,
    stock_price: float = 178.23,
    ivr_value: float = 45.0,
    market_cap: float = 3_000_000_000_000.0,
) -> ScreenResult:
    checks = [
        CheckResult(name="Market cap", status=Status.PASS, value="$3.0T", threshold="> $5B", note="Passes"),
        CheckResult(name="Price range", status=Status.CAUTION, value="$178.23", threshold="$20–$150", note="Above range"),
    ]
    return ScreenResult(
        symbol=symbol,
        verdict=verdict,
        checks=checks,
        stock_price=stock_price,
        ivr_value=ivr_value,
        market_cap=market_cap,
        trade_expiration="2026-05-16",
        trade_strike=170.0,
        trade_delta=0.28,
        trade_dte=37,
        trade_premium=2.5,
        trade_min_premium=1.7,
        trend="bullish",
    )


@pytest.fixture
def repo(tmp_path: Path) -> ScreenRepository:
    return ScreenRepository(db_path=tmp_path / "test_screens.db")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_save_returns_id(repo: ScreenRepository) -> None:
    result = _make_result()
    row_id = repo.save(result)
    assert isinstance(row_id, int)
    assert row_id >= 1


def test_get_by_id_round_trip(repo: ScreenRepository) -> None:
    result = _make_result(symbol="TSLA", verdict=Verdict.STRONG)
    row_id = repo.save(result)

    record = repo.get_by_id(row_id)
    assert record is not None
    assert record.ticker == "TSLA"
    assert record.verdict == Verdict.STRONG.value
    assert record.price == result.stock_price
    assert record.iv_rank == result.ivr_value
    assert record.market_cap == result.market_cap

    # Deserialize and compare
    import json
    deserialized = ScreenResult.from_dict(json.loads(record.payload_json))
    assert deserialized.symbol == "TSLA"
    assert deserialized.verdict == Verdict.STRONG
    assert len(deserialized.checks) == 2
    assert deserialized.trade_expiration == "2026-05-16"
    assert deserialized.trend == "bullish"


def test_get_by_id_missing(repo: ScreenRepository) -> None:
    assert repo.get_by_id(9999) is None


def test_list_history_by_ticker(repo: ScreenRepository) -> None:
    repo.save(_make_result(symbol="AAPL"))
    repo.save(_make_result(symbol="F", verdict=Verdict.DO_NOT_WHEEL))
    repo.save(_make_result(symbol="AAPL"))  # second AAPL

    rows = repo.list_history(ticker="AAPL")
    assert len(rows) == 2
    assert all(r.ticker == "AAPL" for r in rows)
    # newest first
    assert rows[0].screened_at >= rows[1].screened_at


def test_list_history_all(repo: ScreenRepository) -> None:
    repo.save(_make_result(symbol="AAPL"))
    repo.save(_make_result(symbol="F"))
    repo.save(_make_result(symbol="GME"))

    rows = repo.list_history()
    assert len(rows) == 3
    # newest first
    for i in range(len(rows) - 1):
        assert rows[i].screened_at >= rows[i + 1].screened_at


def test_list_history_limit(repo: ScreenRepository) -> None:
    for _ in range(5):
        repo.save(_make_result())
    rows = repo.list_history(limit=3)
    assert len(rows) == 3


def test_list_tickers_with_counts(repo: ScreenRepository) -> None:
    repo.save(_make_result(symbol="AAPL"))
    repo.save(_make_result(symbol="AAPL"))
    repo.save(_make_result(symbol="AAPL"))
    repo.save(_make_result(symbol="F"))
    repo.save(_make_result(symbol="GME"))
    repo.save(_make_result(symbol="GME"))

    summary = repo.list_tickers_with_counts()
    counts = {ticker: cnt for ticker, cnt, _ in summary}
    assert counts["AAPL"] == 3
    assert counts["F"] == 1
    assert counts["GME"] == 2


def test_get_latest_for_ticker(repo: ScreenRepository) -> None:
    repo.save(_make_result(symbol="AAPL", verdict=Verdict.ACCEPTABLE))
    id2 = repo.save(_make_result(symbol="AAPL", verdict=Verdict.STRONG))

    record = repo.get_latest_for_ticker("AAPL")
    assert record is not None
    assert record.id == id2


def test_get_latest_for_ticker_missing(repo: ScreenRepository) -> None:
    assert repo.get_latest_for_ticker("ZZZZ") is None


def test_clear_all(repo: ScreenRepository) -> None:
    repo.save(_make_result())
    repo.save(_make_result())
    deleted = repo.clear_all()
    assert deleted == 2
    assert repo.list_history() == []


def test_ticker_normalized_to_uppercase(repo: ScreenRepository) -> None:
    result = _make_result(symbol="aapl")  # lowercase
    row_id = repo.save(result)
    record = repo.get_by_id(row_id)
    assert record.ticker == "AAPL"
