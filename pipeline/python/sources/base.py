"""Minimal contract for future ground-observation adapters (not active in v0.1)."""
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass(frozen=True)
class SourceRecord:
    source: str
    observed_at: str
    variable: str
    value: float | None
    unit: str | None
    source_url: str | None
    raw_reference: str | None
    quality_flags: list[str]
    metadata: dict[str, Any]

class SourceAdapter(Protocol):
    """Implement fetch/normalize only after endpoint and permissions are documented."""
    def fetch(self, start: str, end: str) -> list[SourceRecord]: ...
