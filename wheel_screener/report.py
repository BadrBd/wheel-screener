"""Render a ScreenResult to the terminal using rich."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from .checks.base import Status
from .scoring import ScreenResult, Verdict

console = Console()

_STATUS_STYLE = {
    Status.PASS: "bold green",
    Status.CAUTION: "bold yellow",
    Status.FAIL: "bold red",
}

_VERDICT_STYLE = {
    Verdict.STRONG: "bold green",
    Verdict.ACCEPTABLE: "bold yellow",
    Verdict.DO_NOT_WHEEL: "bold red",
}

_STATUS_LABEL = {
    Status.PASS: "PASS    ",
    Status.CAUTION: "CAUTION ",
    Status.FAIL: "FAIL    ",
}


def print_report(result: ScreenResult) -> None:
    """Print the full wheel screener report to stdout."""

    if result.error:
        console.print(f"\n[bold red]Error:[/bold red] {result.error}\n")
        return

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    verdict_text = Text(result.verdict.value, style=_VERDICT_STYLE[result.verdict])
    console.print()
    console.print(f"[bold]Ticker:[/bold] {result.symbol}")
    console.print(Text.assemble("Overall verdict: ", verdict_text))
    console.print()

    # ------------------------------------------------------------------
    # Checks table
    # ------------------------------------------------------------------
    table = Table(
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 1),
    )
    table.add_column("Status", style="", no_wrap=True, min_width=10)
    table.add_column("Check", style="bold", no_wrap=True, min_width=20)
    table.add_column("Value", no_wrap=False, min_width=30)
    table.add_column("Note", no_wrap=False)

    for check in result.checks:
        style = _STATUS_STYLE[check.status]
        label = _STATUS_LABEL[check.status]
        table.add_row(
            Text(f"[{label.strip()}]", style=style),
            check.name,
            str(check.value),
            check.note,
        )

    console.print("Checks:")
    console.print(table)

    # ------------------------------------------------------------------
    # Suggested trade (only if not DO_NOT_WHEEL and trade data available)
    # ------------------------------------------------------------------
    if result.verdict != Verdict.DO_NOT_WHEEL and result.trade_expiration:
        console.print("Suggested trade:")
        console.print(f"  Expiration:            {result.trade_expiration} ({result.trade_dte} DTE)")
        console.print(f"  Strike:                ${result.trade_strike:.2f} (≈ {result.trade_delta:.2f} delta put)")
        if result.trade_min_premium is not None:
            console.print(
                f"  Min premium to accept: ${result.trade_min_premium:.2f} "
                f"(1.0% of strike)"
            )
        console.print()

    # ------------------------------------------------------------------
    # Disqualified section (only if DO_NOT_WHEEL)
    # ------------------------------------------------------------------
    if result.verdict == Verdict.DO_NOT_WHEEL:
        fails = [c for c in result.checks if c.status == Status.FAIL]
        console.print("[bold red]Disqualified because:[/bold red]")
        for f in fails:
            console.print(f"  • [red]{f.name}[/red] — {f.note}")
        console.print()

    # ------------------------------------------------------------------
    # Risk note (always shown)
    # ------------------------------------------------------------------
    risk = Panel(
        "Assignment is possible on any cash-secured put. Only run this\n"
        "strategy on stocks you are comfortable holding 100 shares of at\n"
        "the strike price. [bold]This tool is not financial advice.[/bold]",
        title="Risk note",
        border_style="dim",
        expand=False,
    )
    console.print(risk)
    console.print()
