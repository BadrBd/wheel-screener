"""Streamlit UI for Wheel Screener with persistent history.

Run with:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from wheel_screener.scoring import ScreenResult, Verdict, run_screen
from wheel_screener.checks.base import Status
from wheel_screener.storage import ScreenRecord, ScreenRepository
from wheel_screener.storage.db import DEFAULT_DB_PATH

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Wheel Screener",
    page_icon=":wheel_of_dharma:",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Shared singleton repository
# ---------------------------------------------------------------------------


@st.cache_resource
def get_repo() -> ScreenRepository:
    return ScreenRepository(DEFAULT_DB_PATH)


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------


def _init_state() -> None:
    if "view" not in st.session_state:
        st.session_state.view = "new_screen"
    if "selected_screen_id" not in st.session_state:
        st.session_state.selected_screen_id = None
    # Sync from URL on first load
    if "screen_id" in st.query_params:
        try:
            st.session_state.selected_screen_id = int(st.query_params["screen_id"])
            st.session_state.view = "history"
        except (ValueError, KeyError):
            pass


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

_VERDICT_COLOR = {
    Verdict.STRONG: "green",
    Verdict.ACCEPTABLE: "orange",
    Verdict.DO_NOT_WHEEL: "red",
}

_STATUS_ICON = {
    Status.PASS: ":white_check_mark:",
    Status.CAUTION: ":warning:",
    Status.FAIL: ":x:",
}

_STATUS_COLOR = {
    Status.PASS: "green",
    Status.CAUTION: "orange",
    Status.FAIL: "red",
}


def render_report(result: ScreenResult) -> None:
    """Render a ScreenResult — shared by both fresh screens and cached results."""
    if result.error:
        st.error(f"Screener error: {result.error}")
        return

    # Verdict banner
    color = _VERDICT_COLOR.get(result.verdict, "gray")
    st.markdown(
        f"### :{color}[{result.symbol} — {result.verdict.value}]"
    )

    # Quick stats row
    col1, col2, col3 = st.columns(3)
    if result.stock_price is not None:
        col1.metric("Price", f"${result.stock_price:,.2f}")
    if result.ivr_value is not None:
        col2.metric("IV Rank", f"{result.ivr_value:.1f}%")
    if result.trend is not None:
        col3.metric("Trend", result.trend.capitalize())

    st.divider()

    # Checks table
    st.subheader("Checklist")
    for check in result.checks:
        icon = _STATUS_ICON.get(check.status, "?")
        c_color = _STATUS_COLOR.get(check.status, "gray")
        with st.container():
            left, right = st.columns([3, 1])
            with left:
                st.markdown(
                    f"{icon} **{check.name}** &nbsp; "
                    f"<span style='color:gray;font-size:0.85em'>{check.note}</span>",
                    unsafe_allow_html=True,
                )
            with right:
                st.markdown(
                    f"<span style='color:{c_color};font-weight:600'>{check.value}</span>",
                    unsafe_allow_html=True,
                )

    # Suggested trade
    if result.verdict != Verdict.DO_NOT_WHEEL and result.trade_expiration:
        st.divider()
        st.subheader("Suggested Trade")
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Expiration", result.trade_expiration)
        t2.metric("DTE", str(result.trade_dte))
        t3.metric("Strike", f"${result.trade_strike:.2f}" if result.trade_strike else "—")
        t4.metric("Delta", f"{result.trade_delta:.2f}" if result.trade_delta else "—")
        if result.trade_min_premium is not None:
            st.caption(f"Min premium to accept: ${result.trade_min_premium:.2f} (1% of strike)")

    # DO_NOT_WHEEL failure summary
    if result.verdict == Verdict.DO_NOT_WHEEL:
        st.divider()
        fails = [c for c in result.checks if c.status == Status.FAIL]
        if fails:
            st.error("**Disqualified because:**\n" + "\n".join(f"- {f.name}: {f.note}" for f in fails))

    # Risk note
    st.divider()
    st.caption(
        "Assignment is possible on any cash-secured put. Only run this strategy on stocks "
        "you are comfortable holding 100 shares of at the strike price. "
        "**This tool is not financial advice.**"
    )


# ---------------------------------------------------------------------------
# Staleness banner
# ---------------------------------------------------------------------------


def _staleness_banner(screened_at: datetime) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = now - screened_at
    total_seconds = delta.total_seconds()
    total_minutes = int(total_seconds // 60)
    total_hours = int(total_seconds // 3600)
    total_days = delta.days

    if total_seconds < 3600:
        color, msg = "green", f"Screened {max(total_minutes, 1)} minute{'s' if total_minutes != 1 else ''} ago"
    elif total_seconds < 86400:
        color, msg = "orange", f"Screened {total_hours} hour{'s' if total_hours != 1 else ''} ago"
    elif total_days < 7:
        color, msg = "orange", f"Screened {total_days} day{'s' if total_days != 1 else ''} ago — consider updating"
    else:
        color, msg = "red", f"Screened {total_days} days ago — data likely stale"

    st.markdown(
        f"<div style='background:{'#d4edda' if color=='green' else '#fff3cd' if color=='orange' else '#f8d7da'};"
        f"border:1px solid {'#28a745' if color=='green' else '#ffc107' if color=='orange' else '#dc3545'};"
        f"border-radius:6px;padding:10px 14px;margin-bottom:12px;font-size:0.9em;'>"
        f"&#128337; {msg}"
        f"</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Safe deserialization
# ---------------------------------------------------------------------------


def _deserialize_safe(record: ScreenRecord) -> ScreenResult | None:
    try:
        return ScreenResult.from_dict(json.loads(record.payload_json))
    except Exception as exc:
        st.error(
            f"This screen's cached data is corrupt and cannot be displayed. "
            f"(Error: {exc})"
        )
        if st.button("Re-screen this ticker", key=f"rescreen_corrupt_{record.id}"):
            _switch_to_new_screen(record.ticker)
            st.rerun()
        return None


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def _switch_to_new_screen(prefill: str = "") -> None:
    st.session_state.view = "new_screen"
    st.session_state.selected_screen_id = None
    st.session_state["_ticker_prefill"] = prefill
    st.query_params.clear()


def _select_screen(screen_id: int) -> None:
    st.session_state.selected_screen_id = screen_id
    st.session_state.view = "history"
    st.query_params["screen_id"] = str(screen_id)


# ---------------------------------------------------------------------------
# Relative time helper for sidebar labels
# ---------------------------------------------------------------------------


def _rel_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.rstrip("Z"))
        delta = datetime.now(timezone.utc).replace(tzinfo=None) - dt
        s = delta.total_seconds()
        if s < 3600:
            m = max(int(s // 60), 1)
            return f"{m}m ago"
        elif s < 86400:
            return f"{int(s // 3600)}h ago"
        elif delta.days < 7:
            return f"{delta.days}d ago"
        else:
            return f"{delta.days // 7}w ago"
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _render_sidebar(repo: ScreenRepository) -> None:
    with st.sidebar:
        st.title("Wheel Screener")
        st.divider()

        # Mode selector
        mode = st.radio(
            "Mode",
            ["New Screen", "History"],
            index=0 if st.session_state.view == "new_screen" else 1,
            label_visibility="collapsed",
        )
        if mode == "New Screen" and st.session_state.view != "new_screen":
            _switch_to_new_screen()
            st.rerun()
        elif mode == "History" and st.session_state.view != "history":
            st.session_state.view = "history"
            st.rerun()

        # History ticker list (only in history mode)
        if st.session_state.view == "history":
            st.divider()
            tickers = repo.list_tickers_with_counts()

            if not tickers:
                st.caption("No screens yet.")
            else:
                search = st.text_input("Search tickers", placeholder="AAPL…", label_visibility="collapsed")
                filtered = [t for t in tickers if search.upper() in t[0]] if search else tickers

                for ticker, count, latest_ts in filtered:
                    rel = _rel_time(latest_ts)
                    label = f"**{ticker}** ({count} · {rel})"
                    with st.expander(label, expanded=False):
                        rows = repo.list_history(ticker=ticker)
                        for rec in rows:
                            ts_str = rec.screened_at.strftime("%Y-%m-%d %H:%M UTC")
                            verdict_short = {
                                "STRONG CANDIDATE": "STRONG",
                                "ACCEPTABLE": "OK",
                                "DO NOT WHEEL": "NO",
                            }.get(rec.verdict, rec.verdict)

                            btn_label = f"{ts_str} — {verdict_short}"
                            is_selected = st.session_state.selected_screen_id == rec.id
                            if st.button(
                                btn_label,
                                key=f"hist_{rec.id}",
                                type="primary" if is_selected else "secondary",
                                use_container_width=True,
                            ):
                                _select_screen(rec.id)
                                st.rerun()

        # Clear history button
        if st.session_state.view == "history":
            st.divider()
            with st.popover("Clear history", use_container_width=True):
                st.warning("This will permanently delete all screen history.")
                if st.button("Confirm — delete all", type="primary", use_container_width=True):
                    deleted = repo.clear_all()
                    st.session_state.selected_screen_id = None
                    st.query_params.clear()
                    st.toast(f"Deleted {deleted} screen{'s' if deleted != 1 else ''}.")
                    st.rerun()


# ---------------------------------------------------------------------------
# New Screen view
# ---------------------------------------------------------------------------


def _new_screen_view(repo: ScreenRepository) -> None:
    st.header("Screen a Ticker")

    prefill = st.session_state.pop("_ticker_prefill", "")
    ticker_input = st.text_input(
        "Ticker symbol",
        value=prefill,
        placeholder="e.g. AAPL",
        max_chars=10,
        key="new_screen_ticker",
    ).strip().upper()

    if st.button("Screen", type="primary", disabled=not ticker_input):
        with st.spinner(f"Screening {ticker_input}…"):
            try:
                result = run_screen(ticker_input)
            except Exception as exc:
                st.error(f"Screener failed: {exc}")
                return

        new_id = repo.save(result)
        _select_screen(new_id)
        st.toast(f"Saved to history.")
        st.session_state.view = "history"
        st.rerun()


# ---------------------------------------------------------------------------
# History view
# ---------------------------------------------------------------------------


def _history_view(repo: ScreenRepository) -> None:
    selected_id = st.session_state.selected_screen_id

    # ── No screen selected: show overview table ──────────────────────────
    if selected_id is None:
        st.header("Screen History")
        rows = repo.list_history(limit=200)

        if not rows:
            st.info("No screens yet.")
            if st.button("Screen your first ticker"):
                _switch_to_new_screen()
                st.rerun()
            return

        import pandas as pd

        data = []
        for rec in rows:
            data.append({
                "id": rec.id,
                "Ticker": rec.ticker,
                "Verdict": rec.verdict,
                "Price": f"${rec.price:,.2f}" if rec.price else "—",
                "IVR": f"{rec.iv_rank:.1f}%" if rec.iv_rank else "—",
                "Screened": rec.screened_at.strftime("%Y-%m-%d %H:%M UTC"),
            })
        df = pd.DataFrame(data)

        st.dataframe(
            df.drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Click a row in the sidebar to load a cached screen.")
        return

    # ── Screen selected: show cached result ─────────────────────────────
    record = repo.get_by_id(selected_id)
    if record is None:
        st.error(f"Screen id={selected_id} not found.")
        st.session_state.selected_screen_id = None
        return

    # Staleness banner + Update button side by side
    banner_col, btn_col = st.columns([5, 1])
    with banner_col:
        _staleness_banner(record.screened_at)
    with btn_col:
        update_clicked = st.button("Update with live data", type="primary", use_container_width=True)

    if update_clicked:
        with st.spinner(f"Re-screening {record.ticker}…"):
            try:
                fresh = run_screen(record.ticker)
            except Exception as exc:
                st.error(f"Update failed: {exc}")
            else:
                new_id = repo.save(fresh)
                _select_screen(new_id)
                st.toast("Updated — new screen saved to history.")
                st.rerun()

    result = _deserialize_safe(record)
    if result is not None:
        render_report(result)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    _init_state()
    repo = get_repo()
    _render_sidebar(repo)

    if st.session_state.view == "new_screen":
        _new_screen_view(repo)
    else:
        _history_view(repo)


if __name__ == "__main__":
    main()
else:
    main()
