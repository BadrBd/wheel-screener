"""Load and expose scoring thresholds from thresholds.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "thresholds.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load thresholds YAML.  Falls back to the bundled config/thresholds.yaml."""
    resolved = Path(path) if path else _DEFAULT_CONFIG_PATH
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {resolved}")
    with resolved.open() as fh:
        return yaml.safe_load(fh)
