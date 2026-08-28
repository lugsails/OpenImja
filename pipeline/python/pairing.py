"""Family-separated Sentinel-1/Sentinel-2 pairing and summary helpers."""
from __future__ import annotations

from datetime import datetime
from statistics import median


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def observation_pairs(optical_records: list[dict], sar_records: list[dict], window_days: float) -> list[dict]:
    pairs = []
    for optical in optical_records:
        if optical.get("measurement_family") != "optical" or optical.get("observation_state") not in {"reviewed", "published"}:
            continue
        for sar in sar_records:
            if sar.get("measurement_family") != "sar":
                continue
            separation_hours = (parse_time(sar["observed_at"]) - parse_time(optical["observed_at"])).total_seconds() / 3600
            if abs(separation_hours) > window_days * 24:
                continue
            difference = None if sar.get("value") is None or optical.get("value") is None else sar["value"] - optical["value"]
            pairs.append({"sentinel2_observed_at": optical["observed_at"], "sentinel2_area_km2": optical.get("value"), "sentinel2_product_id": optical["source_product"], "sentinel1_observed_at": sar["observed_at"], "sentinel1_area_km2": sar.get("value"), "sentinel1_product_id": sar["source_product"], "temporal_separation_hours": separation_hours, "temporal_separation_days": separation_hours / 24, "absolute_area_difference_km2": abs(difference) if difference is not None else None, "percentage_area_difference": (abs(difference) / optical["value"] * 100) if difference is not None and optical["value"] else None, "signed_area_difference_km2": difference, "sentinel1_orbit_pass": sar.get("provenance", {}).get("orbit_pass"), "sentinel2_quality_flags": ";".join(optical.get("quality_flags", [])), "sentinel1_quality_flags": ";".join(sar.get("quality_flags", [])), "sentinel1_state": sar.get("observation_state")})
    return sorted(pairs, key=lambda row: (row["sentinel2_observed_at"], abs(row["temporal_separation_hours"])))


def season(value: str) -> str:
    month = parse_time(value).month
    return "winter" if month in {12, 1, 2} else "pre_monsoon" if month in {3, 4, 5} else "monsoon" if month in {6, 7, 8, 9} else "post_monsoon"


def summarize_pairs(rows: list[dict]) -> dict:
    valid = [row for row in rows if row["signed_area_difference_km2"] is not None]
    def group(items: list[dict]) -> dict:
        if not items: return {"count": 0, "median_absolute_difference_km2": None, "median_absolute_percentage_difference": None, "mean_signed_difference_km2": None, "maximum_absolute_difference_km2": None}
        return {"count": len(items), "median_absolute_difference_km2": median(x["absolute_area_difference_km2"] for x in items), "median_absolute_percentage_difference": median(x["percentage_area_difference"] for x in items), "mean_signed_difference_km2": sum(x["signed_area_difference_km2"] for x in items) / len(items), "maximum_absolute_difference_km2": max(x["absolute_area_difference_km2"] for x in items)}
    by_orbit = {key: group([row for row in valid if row["sentinel1_orbit_pass"] == key]) for key in sorted({row["sentinel1_orbit_pass"] for row in valid})}
    by_season = {key: group([row for row in valid if season(row["sentinel2_observed_at"]) == key]) for key in sorted({season(row["sentinel2_observed_at"]) for row in valid})}
    return {"pair_count": len(rows), "quantified_pair_count": len(valid), "overall": group(valid), "by_orbit_pass": by_orbit, "by_season": by_season, "interpretation": "Insufficient evidence for validation success" if len(valid) < 5 else "Descriptive statistics only; families remain separate pending scientific review."}
