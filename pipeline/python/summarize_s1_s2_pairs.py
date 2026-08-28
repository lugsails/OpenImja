#!/usr/bin/env python3
"""Summarize retained Sentinel-1/Sentinel-2 pairs without declaring validation success."""
from __future__ import annotations
import csv, json
from pathlib import Path
from pairing import summarize_pairs

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "data/validation/s1-s2-pairs.csv"
OUT = ROOT / "data/validation/s1-s2-summary.json"

def cast(row: dict) -> dict:
    for key in ["sentinel2_area_km2", "sentinel1_area_km2", "temporal_separation_hours", "temporal_separation_days", "absolute_area_difference_km2", "percentage_area_difference", "signed_area_difference_km2"]:
        row[key] = float(row[key]) if row.get(key) not in {None, ""} else None
    return row

def main() -> None:
    rows = [cast(row) for row in csv.DictReader(CSV.open())]
    summary = summarize_pairs(rows); OUT.write_text(json.dumps(summary, indent=2) + "\n"); print(json.dumps(summary, indent=2))

if __name__ == "__main__": main()
