"""Pure, conservative QA policy for experimental SAR lake candidates."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SarQaDecision:
    state: str
    rejection_reasons: list[str]


def assess_sar_scene(*, lake_envelope_valid_fraction: float | None, lake_area_km2: float | None, policy: dict) -> SarQaDecision:
    reasons: list[str] = []
    if lake_envelope_valid_fraction is None or lake_envelope_valid_fraction < policy["minimum_lake_envelope_valid_fraction"]:
        reasons.append("LOW_LAKE_ENVELOPE_OBSERVABILITY")
    if lake_area_km2 is None:
        reasons.append("NO_LAKE_COMPONENT_AT_SEED")
    elif lake_area_km2 < policy["minimum_component_area_km2"]:
        reasons.append("SAR_COMPONENT_BELOW_MINIMUM_AREA")
    return SarQaDecision("rejected" if reasons else "processed", reasons)
