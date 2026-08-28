#!/usr/bin/env python3
"""Derive one Imja Tsho water-area estimate from Sentinel-2 L2A in Earth Engine.

This program is an experimental measurement workflow, not a warning system.
It deliberately fails closed when there is no acceptable image or no lake component
containing the configured seed point. Inspect every generated boundary before release.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ee
import google.auth

from freshness import classify

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config/lakes/imja-tsho.json"
CSV_PATH = ROOT / "data/processed/imja-tsho/lake-area.csv"
LATEST_PATH = ROOT / "data/latest/imja-tsho.json"
BOUNDARY_DIR = ROOT / "data/processed/imja-tsho/boundaries"
METHOD = "sentinel2_s2sr_qa60_scl_ndwi_connected_component"
METHOD_VERSION = "0.1.0"


def utc_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def git_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def mask_s2(image: ee.Image) -> ee.Image:
    """Mask QA60 clouds/cirrus and SCL cloud/shadow/snow/no-data classes."""
    qa = image.select("QA60")
    qa_clear = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    scl = image.select("SCL")
    scl_clear = scl.neq(0).And(scl.neq(1)).And(scl.neq(3)).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(11))
    return image.updateMask(qa_clear.And(scl_clear))


def choose_image(aoi: ee.Geometry, start: str, window_days: int, min_valid_fraction: float) -> ee.Image:
    end = (datetime.fromisoformat(start) + timedelta(days=window_days + 1)).date().isoformat()
    collection = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi).filterDate(start, end).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 80))
        .map(mask_s2))

    def annotate(image: ee.Image) -> ee.Image:
        valid_fraction = image.select("B3").mask().reduceRegion(
            reducer=ee.Reducer.mean(), geometry=aoi, scale=20, maxPixels=10_000_000
        ).get("B3")
        return image.set("openimja_valid_fraction", valid_fraction)

    candidates = collection.map(annotate).filter(ee.Filter.gte("openimja_valid_fraction", min_valid_fraction)).sort("CLOUDY_PIXEL_PERCENTAGE")
    if candidates.size().getInfo() == 0:
        raise RuntimeError("No Sentinel-2 image met cloud/AOI validity criteria. Do not publish an estimate.")
    return ee.Image(candidates.first())


def process(args: argparse.Namespace) -> dict:
    config = json.loads(CONFIG_PATH.read_text())
    aoi = ee.Geometry(config["geometry"])
    seed = ee.Geometry(config["seed_point"])
    image = choose_image(aoi, args.date, args.window_days, args.min_valid_fraction)
    masked = mask_s2(image)
    ndwi = masked.normalizedDifference(["B3", "B8"]).rename("ndwi")
    water = ndwi.gte(args.ndwi_threshold).selfMask().clip(aoi)
    vectors = water.reduceToVectors(
        geometry=aoi, scale=10, geometryType="polygon", eightConnected=True,
        labelProperty="water", reducer=ee.Reducer.countEvery(), maxPixels=100_000_000
    ).map(lambda feature: feature.set("area_m2", feature.geometry().area(1)))
    selected_candidates = vectors.filterBounds(seed).sort("area_m2", False)
    if selected_candidates.size().getInfo() == 0:
        raise RuntimeError("No thresholded water component contains the seed point. Review AOI/threshold; no output written.")
    selected = ee.Feature(selected_candidates.first())
    area_m2 = selected.geometry().area(1).getInfo()
    properties = image.toDictionary(["system:index", "system:time_start", "CLOUDY_PIXEL_PERCENTAGE", "openimja_valid_fraction"]).getInfo()
    observed = datetime.fromtimestamp(properties["system:time_start"] / 1000, timezone.utc)
    image_id = f"COPERNICUS/S2_SR_HARMONIZED/{properties['system:index']}"
    flags = ["DRAFT_AOI_REQUIRES_VISUAL_VALIDATION", "OPTICAL_WATER_CLASSIFICATION"]
    valid_fraction = properties.get("openimja_valid_fraction")
    if valid_fraction is None or valid_fraction < 0.9:
        flags.append("PARTIALLY_MASKED_AOI")
    boundary_name = f"{observed.date().isoformat()}_{properties['system:index']}.geojson"
    boundary_path = BOUNDARY_DIR / boundary_name
    BOUNDARY_DIR.mkdir(parents=True, exist_ok=True)
    boundary = selected.set({"lake_id": config["id"], "observed_at": utc_z(observed), "image_id": image_id}).getInfo()
    boundary_path.write_text(json.dumps({"type": "FeatureCollection", "features": [boundary]}, indent=2) + "\n")
    processed = datetime.now(timezone.utc)
    relative_boundary = str(boundary_path.relative_to(ROOT)).replace("\\", "/")
    observation = {
        "lake_id": config["id"], "variable": "lake_area", "value": round(area_m2 / 1_000_000, 6), "unit": "km2",
        "observed_at": utc_z(observed), "processed_at": utc_z(processed), "source": "Sentinel-2",
        "source_product": image_id, "source_url": "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED",
        "method": METHOD, "method_version": METHOD_VERSION,
        "parameters": {"index": "NDWI=(B3-B8)/(B3+B8)", "ndwi_threshold": args.ndwi_threshold, "cloud_mask": "QA60 cloud/cirrus bits plus SCL cloud-shadow/snow classes", "aoi_valid_fraction_minimum": args.min_valid_fraction, "aoi_status": config["aoi_status"], "scale_m": 10},
        "confidence": None, "quality_flags": flags, "freshness": classify(observed, processed),
        "boundary_geojson_url": relative_boundary,
        "provenance": {"code_version": git_revision(), "config_path": "config/lakes/imja-tsho.json", "image_id": image_id, "earth_engine_collection": "COPERNICUS/S2_SR_HARMONIZED", "scene_cloud_cover_percent": properties.get("CLOUDY_PIXEL_PERCENTAGE"), "aoi_valid_fraction": valid_fraction}
    }
    return observation


def publish(observation: dict, promote_latest: bool = False) -> None:
    observation = {**observation, "publication_status": "published" if promote_latest else "candidate"}
    observation_path = ROOT / "data/processed/imja-tsho" / f"{observation['observed_at'][:10]}.json"
    observation_path.write_text(json.dumps(observation, indent=2) + "\n")
    fields = ["date", "lake_area_km2", "source", "source_product", "cloud_cover", "method", "method_version", "quality_flag", "publication_status"]
    row = {"date": observation["observed_at"][:10], "lake_area_km2": observation["value"], "source": observation["source"], "source_product": observation["source_product"], "cloud_cover": observation["provenance"]["scene_cloud_cover_percent"], "method": observation["method"], "method_version": observation["method_version"], "quality_flag": ";".join(observation["quality_flags"]), "publication_status": observation["publication_status"]}
    with CSV_PATH.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows = [existing for existing in rows if existing["source_product"] != row["source_product"]]
    rows.append(row)
    rows.sort(key=lambda item: (item["date"], item["source_product"]))
    with CSV_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    existing_latest = json.loads(LATEST_PATH.read_text()) if LATEST_PATH.exists() else {}
    existing_observation = existing_latest.get("latest_observation") or {}
    existing_is_published = existing_observation.get("publication_status") == "published"
    if promote_latest and (not existing_observation or not existing_is_published or observation["observed_at"] >= existing_observation.get("observed_at", "")):
        LATEST_PATH.write_text(json.dumps({"lake_id": observation["lake_id"], "status": "valid_observation", "as_of": observation["processed_at"], "latest_observation": observation, "limitations_url": "../../docs/limitations.md"}, indent=2) + "\n")
    print(json.dumps(observation, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Start date (YYYY-MM-DD) of image search window")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--ndwi-threshold", type=float, default=0.10)
    parser.add_argument("--min-valid-fraction", type=float, default=0.70)
    parser.add_argument("--project", default=os.environ.get("OPENIMJA_EE_PROJECT"), help="Earth Engine-enabled Google Cloud project (or set OPENIMJA_EE_PROJECT)")
    parser.add_argument("--auth-source", choices=["earthengine", "application-default"], default="earthengine", help="Credential store to use; application-default uses gcloud auth application-default login")
    parser.add_argument("--promote-latest", action="store_true", help="Update data/latest only after visually reviewing this candidate boundary")
    args = parser.parse_args()
    if not args.project:
        parser.error("--project (or OPENIMJA_EE_PROJECT) is required; Earth Engine operations must be charged to an enabled Cloud project.")
    if args.auth_source == "application-default":
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/earthengine", "https://www.googleapis.com/auth/cloud-platform"])
        ee.Initialize(credentials=credentials, project=args.project)
    else:
        ee.Initialize(project=args.project)
    publish(process(args), promote_latest=args.promote_latest)


if __name__ == "__main__":
    main()
