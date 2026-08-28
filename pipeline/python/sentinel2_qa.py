"""Pure QA policy for Sentinel-2 lake-area candidates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class QaDecision:
    state: str
    rejection_reasons: list[str]
    relative_area_change: float | None
    outlier_reference_observation: str | None


def nearest_reference(observed_at: datetime, records: list[dict], max_age_days: int, minimum_elapsed_days: int) -> dict | None:
    candidates = []
    for record in records:
        if record.get("observation_state") not in {"reviewed", "published"} and record.get("publication_status") != "published":
            continue
        if record.get("value") is None:
            continue
        date = datetime.fromisoformat(record["observed_at"].replace("Z", "+00:00"))
        days = abs((observed_at - date).total_seconds()) / 86400
        if minimum_elapsed_days <= days <= max_age_days:
            candidates.append((days, record))
    return min(candidates, default=(None, None), key=lambda item: item[0])[1]


def assess_scene(*, aoi_valid_fraction: float | None, lake_envelope_valid_fraction: float | None,
                 lake_area_km2: float | None, observed_at: datetime, reference_records: list[dict],
                 policy: dict) -> QaDecision:
    reasons: list[str] = []
    if aoi_valid_fraction is None or aoi_valid_fraction < policy["minimum_aoi_valid_fraction"]:
        reasons.append("LOW_AOI_OBSERVABILITY")
    if lake_envelope_valid_fraction is None or lake_envelope_valid_fraction < policy["minimum_lake_envelope_valid_fraction"]:
        reasons.append("LOW_LAKE_ENVELOPE_OBSERVABILITY")
    if lake_area_km2 is None:
        reasons.append("NO_LAKE_COMPONENT_AT_SEED")
    reference = None
    relative_change = None
    if lake_area_km2 is not None:
        reference = nearest_reference(observed_at, reference_records, policy["outlier_comparison_max_age_days"], policy["outlier_minimum_elapsed_days"])
        if reference and reference["value"] > 0:
            relative_change = (lake_area_km2 - reference["value"]) / reference["value"]
            if abs(relative_change) > policy["outlier_max_relative_area_change"]:
                reasons.append("TEMPORAL_AREA_CHANGE_OUTLIER")
    return QaDecision("rejected" if reasons else "processed", reasons, relative_change, reference.get("source_product") if reference else None)
