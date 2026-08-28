"""Freshness labels describe observation age only; they never describe hazard."""
from __future__ import annotations

from datetime import datetime, timezone

CURRENT_DAYS = 14
AGING_DAYS = 45
STALE_DAYS = 180


def classify(observed_at: datetime, evaluated_at: datetime | None = None) -> dict:
    """Return a portable freshness payload, using UTC and whole elapsed days."""
    evaluated_at = evaluated_at or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        return {"status": "UNKNOWN", "age_days": None, "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z")}
    age_days = max(0, int((evaluated_at - observed_at).total_seconds() // 86400))
    if age_days <= CURRENT_DAYS:
        status = "CURRENT"
    elif age_days <= AGING_DAYS:
        status = "AGING"
    elif age_days <= STALE_DAYS:
        status = "STALE"
    else:
        status = "HISTORICAL"
    return {"status": status, "age_days": age_days, "evaluated_at": evaluated_at.isoformat().replace("+00:00", "Z")}
