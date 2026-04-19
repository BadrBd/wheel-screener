# Wheel Strategy Stock Screener

A Python CLI tool that evaluates whether a single stock ticker is a good candidate for the wheel options strategy.

## Usage

```bash
python wheel.py AAPL
python wheel.py F --config config/thresholds.yaml
```

**Exit codes:**
- `0` — Strong Candidate or Acceptable
- `1` — Do Not Wheel
- `2` — Error (bad ticker, API failure, etc.)

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a Tradier sandbox token

1. Sign up at https://developer.tradier.com/
2. Generate a sandbox API token from your developer dashboard
3. Copy `.env.example` to `.env` and paste your token:

```bash
cp .env.example .env
# edit .env and replace the placeholder with your token
```

### 3. Run it

```bash
python wheel.py AAPL
```

## Configuration

All scoring thresholds live in `config/thresholds.yaml`. Edit them without touching code.

You can point to a custom config file:

```bash
python wheel.py TSLA --config /path/to/my_thresholds.yaml
```

## Checks performed

| # | Check | Pass | Caution | Fail |
|---|---|---|---|---|
| 1 | Market cap | > $5B | $2B–$5B | < $2B |
| 2 | Stock price | $20–$150 | outside range | — |
| 3 | IV Rank | 30–60% | > 60% | < 20% |
| 4 | Price vs 50-day SMA | above SMA, or flat | — | below SMA and declining |
| 5 | Earnings window | > 30 days away | — | within 30 days |
| 6 | Negative headlines | none concerning | concerning present | severe |
| 7 | Premium yield (0.25–0.30Δ put, 30–45 DTE) | ≥ 1% of strike | — | < 1% |

## Data sources

- **Tradier sandbox API** — options chains, IV, Greeks, quotes
- **yfinance** — market cap, price history, earnings dates, recent headlines

## Disclaimer

This tool is not financial advice. Assignment is possible on any cash-secured put. Only run the wheel strategy on stocks you are comfortable holding 100 shares of at the strike price.

## Streamlit web app

A full web UI with persistent screen history:

```bash
streamlit run streamlit_app.py
```

Opens at **http://localhost:8501**. Two modes switchable from the sidebar:

- **New Screen** — enter a ticker, run the screener, result is saved automatically
- **History** — browse all past screens grouped by ticker; click any entry to load the cached result instantly (no API calls). A staleness banner shows how old the data is.

An **Update** button re-runs the screener against live data and appends a new history entry. History is stored in `data/screens.db` (SQLite, auto-created on first run).

## Running tests

```bash
pytest tests/ -v
```
