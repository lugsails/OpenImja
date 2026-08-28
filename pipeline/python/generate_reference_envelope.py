#!/usr/bin/env python3
"""Generate a non-publishing optical boundary candidate for QA-envelope review."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import ee
import google.auth

from process_sentinel2 import choose_image, mask_s2

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config/lakes/imja-tsho.json"
OUT = ROOT / "data/processed/imja-tsho/reference-candidates"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True); parser.add_argument("--window-days", type=int, default=45)
    parser.add_argument("--ndwi-threshold", type=float, default=.10); parser.add_argument("--min-valid-fraction", type=float, default=.20)
    parser.add_argument("--project", required=True); args = parser.parse_args()
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/earthengine", "https://www.googleapis.com/auth/cloud-platform"])
    ee.Initialize(credentials=credentials, project=args.project)
    config = json.loads(CONFIG.read_text()); aoi = ee.Geometry(config["geometry"]); seed = ee.Geometry(config["seed_point"])
    image = choose_image(aoi, args.date, args.window_days, args.min_valid_fraction)
    water = mask_s2(image).normalizedDifference(["B3", "B8"]).gte(args.ndwi_threshold).selfMask().clip(aoi)
    components = water.reduceToVectors(geometry=aoi, scale=10, geometryType="polygon", eightConnected=True, labelProperty="water", reducer=ee.Reducer.countEvery(), maxPixels=100_000_000).filterBounds(seed).map(lambda f: f.set("area_m2", f.geometry().area(1))).sort("area_m2", False)
    if components.size().getInfo() == 0: raise RuntimeError("No candidate component contains the seed point.")
    feature = ee.Feature(components.first()); props = image.toDictionary(["system:index", "system:time_start"]).getInfo()
    observed = datetime.fromtimestamp(props["system:time_start"] / 1000, timezone.utc).isoformat().replace("+00:00", "Z")
    image_id = f"COPERNICUS/S2_SR_HARMONIZED/{props['system:index']}"
    feature = feature.set({"lake_id": config["id"], "observed_at": observed, "image_id": image_id, "reference_candidate": True, "ndwi_threshold": args.ndwi_threshold})
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{observed[:10]}_{props['system:index']}_expanded-aoi.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [feature.getInfo()]}, indent=2) + "\n")
    print(json.dumps({"path": str(path.relative_to(ROOT)), "area_km2": round(feature.geometry().area(1).getInfo()/1_000_000, 6), "source_product": image_id}, indent=2))

if __name__ == "__main__": main()
