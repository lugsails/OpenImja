#!/usr/bin/env python3
"""Pair reviewed/published optical records with all nearby SAR candidates."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from pairing import observation_pairs

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/validation/s1-s2-pairs.csv"

def records(folder: Path) -> list[dict]:
    return [json.loads(path.read_text()) for path in folder.glob("*.json")]

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--window-days", type=float, default=3); args = parser.parse_args()
    optical = records(ROOT / "data/processed/imja-tsho/scenes") + records(ROOT / "data/processed/imja-tsho")
    sar = records(ROOT / "data/processed/imja-tsho/sar-scenes")
    rows = observation_pairs(optical, sar, args.window_days)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["sentinel2_observed_at", "sentinel2_area_km2", "sentinel2_product_id", "sentinel1_observed_at", "sentinel1_area_km2", "sentinel1_product_id", "temporal_separation_hours", "temporal_separation_days", "absolute_area_difference_km2", "percentage_area_difference", "signed_area_difference_km2", "sentinel1_orbit_pass", "sentinel2_quality_flags", "sentinel1_quality_flags", "sentinel1_state"]
    with OUT.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"pairs": len(rows), "output": str(OUT.relative_to(ROOT))}, indent=2))

if __name__ == "__main__": main()
