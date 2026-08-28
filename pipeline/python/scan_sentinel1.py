#!/usr/bin/env python3
"""Persist experimental Sentinel-1 GRD QA candidates; never publishes observations."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import ee
import google.auth

from freshness import classify
from sar_qa import assess_sar_scene

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config/lakes/imja-tsho.json"
SCENE_DIR = ROOT / "data/processed/imja-tsho/sar-scenes"
REPORT_DIR = ROOT / "data/processed/imja-tsho/reports"
METHOD = "sentinel1_grd_vv_threshold_connected_component"
METHOD_VERSION = "0.1.0-experimental"


def z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_id(value: str) -> str:
    return value.replace("/", "_").replace(":", "_")


def mask_edge(image: ee.Image, threshold_db: float, polarization: str) -> ee.Image:
    """Remove no-data/very-low-backscatter border pixels; not a terrain-shadow correction."""
    valid = image.select(polarization).gt(threshold_db)
    return image.updateMask(image.mask().And(valid))


def valid_fraction(image: ee.Image, geometry: ee.Geometry, polarization: str) -> float | None:
    value = image.select(polarization).mask().reduceRegion(ee.Reducer.mean(), geometry, 10, maxPixels=10_000_000).get(polarization).getInfo()
    return float(value) if value is not None else None


def process_scene(image: ee.Image, config: dict, envelope: ee.Geometry) -> dict:
    sar = config["sentinel1_sar"]
    aoi = ee.Geometry(config["geometry"]); seed = ee.Geometry(config["seed_point"])
    pol = sar["polarization"]
    properties = image.toDictionary(["system:index", "system:time_start", "orbitProperties_pass", "relativeOrbitNumber_start", "instrumentMode", "transmitterReceiverPolarisation", "platform_number", "resolution_meters"]).getInfo()
    observed = datetime.fromtimestamp(properties["system:time_start"] / 1000, timezone.utc)
    image_id = f"COPERNICUS/S1_GRD/{properties['system:index']}"
    masked = mask_edge(image, sar["edge_mask_threshold_db"], pol)
    envelope_fraction = valid_fraction(masked, envelope, pol)
    water = masked.select(pol).lte(sar["water_backscatter_threshold_db"]).selfMask().clip(aoi)
    vectors = water.reduceToVectors(geometry=aoi, scale=10, geometryType="polygon", eightConnected=True, labelProperty="water", reducer=ee.Reducer.countEvery(), maxPixels=100_000_000)
    components = vectors.filterBounds(seed).map(lambda feature: feature.set("area_m2", feature.geometry().area(1))).sort("area_m2", False)
    area = None; boundary = None
    if components.size().getInfo():
        selected = ee.Feature(components.first())
        area = round(selected.geometry().area(1).getInfo() / 1_000_000, 6)
        boundary = selected.set({"lake_id": config["id"], "observed_at": z(observed), "image_id": image_id}).getInfo()
    decision = assess_sar_scene(lake_envelope_valid_fraction=envelope_fraction, lake_area_km2=area, policy=sar)
    processed = datetime.now(timezone.utc)
    record = {"lake_id": config["id"], "variable": "lake_area", "measurement_family": "sar", "value": area, "unit": "km2", "observed_at": z(observed), "processed_at": z(processed), "source": "Sentinel-1", "source_product": image_id, "source_url": "https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S1_GRD", "method": METHOD, "method_version": METHOD_VERSION, "parameters": {"instrument_mode": sar["instrument_mode"], "polarization": pol, "edge_mask_threshold_db": sar["edge_mask_threshold_db"], "water_backscatter_threshold_db": sar["water_backscatter_threshold_db"], "classifier": f"{pol} <= threshold", "earth_engine_preprocessing": "GRD calibrated, ortho-corrected dB; orbit/noise/radiometric/terrain steps provided by Earth Engine"}, "confidence": None, "quality_flags": decision.rejection_reasons or ["EXPERIMENTAL_SAR_PENDING_REVIEW"], "observation_state": decision.state, "rejection_reasons": decision.rejection_reasons, "state_history": [{"state": "discovered", "at": z(processed)}, {"state": decision.state, "at": z(processed)}], "freshness": classify(observed, processed), "boundary_geojson_url": None, "qa": {"aoi_valid_fraction": valid_fraction(masked, aoi, pol), "lake_envelope_valid_fraction": envelope_fraction, "reference_lake_envelope_path": config["reviewed_reference_lake_envelope"]["path"], "outlier_reference_observation": None, "relative_area_change": None}, "provenance": {"code_version": "scan_sentinel1_v0_1", "config_path": "config/lakes/imja-tsho.json", "image_id": image_id, "earth_engine_collection": "COPERNICUS/S1_GRD", "orbit_pass": properties.get("orbitProperties_pass"), "relative_orbit": properties.get("relativeOrbitNumber_start"), "platform_number": properties.get("platform_number"), "instrument_mode": properties.get("instrumentMode"), "polarizations": properties.get("transmitterReceiverPolarisation"), "resolution_meters": properties.get("resolution_meters")}}
    if boundary:
        path = SCENE_DIR / f"{safe_id(properties['system:index'])}.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": [boundary]}, indent=2) + "\n")
        record["boundary_geojson_url"] = str(path.relative_to(ROOT))
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True); parser.add_argument("--end", required=True)
    parser.add_argument("--orbit", choices=["ASCENDING", "DESCENDING"])
    parser.add_argument("--project", default=os.environ.get("OPENIMJA_EE_PROJECT"), required=os.environ.get("OPENIMJA_EE_PROJECT") is None)
    args = parser.parse_args()
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/earthengine", "https://www.googleapis.com/auth/cloud-platform"])
    ee.Initialize(credentials=credentials, project=args.project)
    config = json.loads(CONFIG_PATH.read_text()); sar = config["sentinel1_sar"]
    envelope = ee.Geometry(json.loads((ROOT / config["reviewed_reference_lake_envelope"]["path"]).read_text())["features"][0]["geometry"])
    aoi = ee.Geometry(config["geometry"])
    images = ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(aoi).filterDate(args.start, args.end).filter(ee.Filter.eq("instrumentMode", sar["instrument_mode"])).filter(ee.Filter.listContains("transmitterReceiverPolarisation", sar["polarization"]))
    if args.orbit: images = images.filter(ee.Filter.eq("orbitProperties_pass", args.orbit))
    ids = images.sort("system:time_start").aggregate_array("system:index").getInfo()
    SCENE_DIR.mkdir(parents=True, exist_ok=True); REPORT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for image_id in ids:
        record = process_scene(ee.Image(f"COPERNICUS/S1_GRD/{image_id}"), config, envelope)
        (SCENE_DIR / f"{safe_id(image_id)}.json").write_text(json.dumps(record, indent=2) + "\n")
        records.append(record)
    report = {"lake_id": config["id"], "measurement_family": "sar", "start": args.start, "end": args.end, "scene_count": len(records), "generated_at": z(datetime.now(timezone.utc)), "scenes": [{"source_product": r["source_product"], "observed_at": r["observed_at"], "state": r["observation_state"], "value": r["value"], "rejection_reasons": r["rejection_reasons"], "orbit_pass": r["provenance"]["orbit_pass"]} for r in records]}
    (REPORT_DIR / f"sentinel1_{args.start}_{args.end}.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
