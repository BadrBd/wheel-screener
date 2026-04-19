"""Tradier sandbox API client.

Reads TRADIER_API_TOKEN from the environment (via .env).
All requests target the sandbox base URL.  One automatic retry on 5xx.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

_BASE_URL = "https://sandbox.tradier.com/v1"
_TIMEOUT = 15  # seconds


class TradierError(Exception):
    """Raised when the Tradier API returns an unexpected response."""


class TradierClient:
    def __init__(self, token: str | None = None, base_url: str = _BASE_URL) -> None:
        self._token = token or os.environ.get("TRADIER_API_TOKEN")
        if not self._token:
            raise TradierError(
                "TRADIER_API_TOKEN is not set.  "
                "Copy .env.example to .env and add your sandbox token."
            )
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            }
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET with one automatic retry on 5xx."""
        url = f"{self._base_url}/{path.lstrip('/')}"
        for attempt in range(2):
            resp = self._session.get(url, params=params, timeout=_TIMEOUT)
            if resp.status_code < 500 or attempt == 1:
                break
            time.sleep(1)

        if not resp.ok:
            raise TradierError(
                f"Tradier API error {resp.status_code} for {url}: {resp.text[:200]}"
            )
        return resp.json()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_quote(self, symbol: str) -> dict[str, Any]:
        """Return the quote dict for *symbol*.

        Tradier returns:
          {"quotes": {"quote": {...}}}   — single symbol
          {"quotes": {"quote": [...]}}   — multiple symbols (won't happen here)
        """
        data = self._get("/markets/quotes", params={"symbols": symbol.upper()})
        quote = data.get("quotes", {}).get("quote")
        if quote is None:
            raise TradierError(f"No quote returned for {symbol}")
        # Normalise — always return a single dict even if list
        if isinstance(quote, list):
            quote = quote[0]
        return quote

    def get_expirations(self, symbol: str) -> list[str]:
        """Return a sorted list of option expiration date strings (YYYY-MM-DD)."""
        data = self._get(
            "/markets/options/expirations",
            params={"symbol": symbol.upper(), "includeAllRoots": "true"},
        )
        expirations = data.get("expirations", {}).get("date", [])
        if expirations is None:
            return []
        if isinstance(expirations, str):
            expirations = [expirations]
        return sorted(expirations)

    def get_option_chain(
        self, symbol: str, expiration: str
    ) -> list[dict[str, Any]]:
        """Return the full options chain for *symbol* on *expiration* (YYYY-MM-DD).

        Each element is an option contract dict with Greeks included.
        Returns an empty list if Tradier has no data for that expiration.
        """
        data = self._get(
            "/markets/options/chains",
            params={
                "symbol": symbol.upper(),
                "expiration": expiration,
                "greeks": "true",
            },
        )
        options = data.get("options", {}).get("option", [])
        if options is None:
            return []
        if isinstance(options, dict):
            options = [options]
        return options
