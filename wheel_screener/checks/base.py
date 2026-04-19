"""Base types for wheel screener checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Status(str, Enum):
    PASS = "PASS"
    CAUTION = "CAUTION"
    FAIL = "FAIL"


@dataclass
class CheckResult:
    name: str
    status: Status
    value: Any          # what was measured (human-readable string or number)
    threshold: str      # what was required (human-readable)
    note: str           # one-line explanation

    def __str__(self) -> str:
        return f"[{self.status.value}] {self.name}: {self.value} ({self.threshold}) — {self.note}"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "value": str(self.value),
            "threshold": self.threshold,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CheckResult":
        return cls(
            name=d["name"],
            status=Status(d["status"]),
            value=d["value"],
            threshold=d["threshold"],
            note=d["note"],
        )
