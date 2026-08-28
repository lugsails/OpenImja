#!/usr/bin/env python3
"""Scan every Sentinel-2 scene in a date range and persist QA outcomes.

This creates candidates/rejections only. It never changes data/latest.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import ee
import google.auth

from freshness import classify
from process_sentinel2 import METHOD, METHOD_VERSION, mask_s2
from sentinel2_qa import assess_scene

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config/lakes/imja-tsho.json"
SCENE_DIR = ROOT / "data/processed/imja-tsho/scenes"
REPORT_DIR = ROOT / "data/processed/imja-tsho/reports"


def z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_id(value: str) -> str:
    return value.replace("/", "_").replace(":", "_")


def existing_records() -> list[dict]:
    records = []
    for path in (ROOT / "data/processed/imja-tsho").glob("*.json"):
        records.append(json.loads(path.read_text()))
    return records


def valid_fraction(image: ee.Image, geometry: ee.Geometry) -> float | None:
    result = image.select("B3").mask().reduceRegion(ee.Reducer.mean(), geometry, 20, maxPixels=10_000_000).get("B3").getInfo()
    return float(result) if result is not None else None


def scan_scene(image: ee.Image, config: dict, envelope: ee.Geometry, references: list[dict]) -> dict:
    aoi = ee.Geometry(config["geometry"])
    seed = ee.Geometry(config["seed_point"])
    properties = image.toDictionary(["system:index", "system:time_start", "CLOUDY_PIXEL_PERCENTAGE"]).getInfo()
    observed = datetime.fromtimestamp(properties["system:time_start"] / 1000, timezone.utc)
    image_id = f"COPERNICUS/S2_SR_HARMONIZED/{properties['system:index']}"
    masked = mask_s2(image)
    aoi_fraction = valid_fraction(masked, aoi)
    envelope_fraction = valid_fraction(masked, envelope)
    ndwi = masked.normalizedDifference(["B3", "B8"])
    water = ndwi.gte(config.get("sentinel2_ndwi_threshold", 0.10)).selfMask().clip(aoi)
    vectors = water.reduceToVectors(geometry=aoi, scale=10, geometryType="polygon", eightConnected=True, labelProperty="water", reducer=ee.Reducer.countEvery(), maxPixels=100_000_000)
    components = vectors.filterBounds(seed).map(lambda feature: feature.set("area_m2", feature.geometry().area(1))).sort("area_m2", False)
    area = None
    boundary = None
    if components.size().getInfo():
        selected = ee.Feature(components.first())
        area = round(selected.geometry().area(1).getInfo() / 1_000_000, 6)
        boundary = selected.set({"lake_id": config["id"], "observed_at": z(observed), "image_id": image_id}).getInfo()
    decision = assess_scene(aoi_valid_fraction=aoi_fraction, lake_envelope_valid_fraction=envelope_fraction, lake_area_km2=area, observed_at=observed, reference_records=references, policy=config["sentinel2_qa"])
    processed = datetime.now(timezone.utc)
    record = {"lake_id": config["id"], "variable": "lake_area", "value": area, "unit": "km2", "observed_at": z(observed), "processed_at": z(processed), "source": "Sentinel-2", "source_product": image_id, "source_url": "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED", "method": METHOD, "method_version": METHOD_VERSION, "parameters": {"index": "NDWI=(B3-B8)/(B3+B8)", "ndwi_threshold": config.get("sentinel2_ndwi_threshold", 0.10), "cloud_mask": "QA60 cloud/cirrus bits plus SCL cloud-shadow/snow classes", "aoi_status": config["aoi_status"]}, "confidence": None, "quality_flags": decision.rejection_reasons or ["QA_PASSED_PENDING_REVIEW"], "observation_state": decision.state, "rejection_reasons": decision.rejection_reasons, "state_history": [{"state": "discovered", "at": z(processed)}, {"state": decision.state, "at": z(processed)}], "freshness": classify(observed, processed), "boundary_geojson_url": None, "qa": {"aoi_valid_fraction": aoi_fraction, "lake_envelope_valid_fraction": envelope_fraction, "reference_lake_envelope_path": config["reviewed_reference_lake_envelope"]["path"], "outlier_reference_observation": decision.outlier_reference_observation, "relative_area_change": decision.relative_area_change}, "provenance": {"code_version": "scan_sentinel2_v0_1", "config_path": "config/lakes/imja-tsho.json", "image_id": image_id, "earth_engine_collection": "COPERNICUS/S2_SR_HARMONIZED", "scene_cloud_cover_percent": properties.get("CLOUDY_PIXEL_PERCENTAGE"), "aoi_valid_fraction": aoi_fraction}}
    if boundary and decision.state == "processed":
        boundary_path = SCENE_DIR / f"{safe_id(properties['system:index'])}.geojson"
        boundary_path.write_text(json.dumps({"type": "FeatureCollection", "features": [boundary]}, indent=2) + "\n")
        record["boundary_geojson_url"] = str(boundary_path.relative_to(ROOT))
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--project", default=os.environ.get("OPENIMJA_EE_PROJECT"), required=os.environ.get("OPENIMJA_EE_PROJECT") is None)
    args = parser.parse_args()
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/earthengine", "https://www.googleapis.com/auth/cloud-platform"])
    ee.Initialize(credentials=credentials, project=args.project)
    config = json.loads(CONFIG_PATH.read_text())
    envelope_file = ROOT / config["reviewed_reference_lake_envelope"]["path"]
    envelope = ee.Geometry(json.loads(envelope_file.read_text())["features"][0]["geometry"])
    SCENE_DIR.mkdir(parents=True, exist_ok=True); REPORT_DIR.mkdir(parents=True, exist_ok=True)
    images = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(ee.Geometry(config["geometry"])).filterDate(args.start, args.end).sort("system:time_start")
    ids = images.aggregate_array("system:index").getInfo()
    references = existing_records()
    records = []
    for image_id in ids:
        record = scan_scene(ee.Image(f"COPERNICUS/S2_SR_HARMONIZED/{image_id}"), config, envelope, references)
        (SCENE_DIR / f"{safe_id(image_id)}.json").write_text(json.dumps(record, indent=2) + "\n")
        records.append(record)
    report = {"lake_id": config["id"], "start": args.start, "end": args.end, "generated_at": z(datetime.now(timezone.utc)), "scene_count": len(records), "states": {state: sum(item["observation_state"] == state for item in records) for state in ["processed", "rejected"]}, "scenes": [{"source_product": item["source_product"], "observed_at": item["observed_at"], "state": item["observation_state"], "rejection_reasons": item["rejection_reasons"], "lake_envelope_valid_fraction": item["qa"]["lake_envelope_valid_fraction"], "value": item["value"]} for item in records]}
    output = REPORT_DIR / f"sentinel2_{args.start}_{args.end}.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
