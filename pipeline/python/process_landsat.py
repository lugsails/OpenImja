#!/usr/bin/env python3
"""Derive one historical optical estimate from Landsat Collection 2 Level 2.

This is a reproducible candidate generator. Review every boundary and do not mix
sensor/method versions in interpretation without validation.
"""
from __future__ import annotations
import argparse, csv, json, os, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
import ee, google.auth
from freshness import classify
from process_sentinel2 import publish

ROOT=Path(__file__).resolve().parents[2]; CONFIG=ROOT/"config/lakes/imja-tsho.json"; CSV=ROOT/"data/processed/imja-tsho/lake-area.csv"; LATEST=ROOT/"data/latest/imja-tsho.json"; BOUNDARIES=ROOT/"data/processed/imja-tsho/boundaries"
METHOD="landsat_c2_l2_qa_pixel_ndwi_connected_component"; VERSION="0.1.0"

def z(dt): return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
def revision():
    try: return subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    except Exception: return "unknown"
def prep(image, green, nir):
    qa=image.select("QA_PIXEL")
    clear=qa.bitwiseAnd(1).eq(0).And(qa.bitwiseAnd(1<<1).eq(0)).And(qa.bitwiseAnd(1<<2).eq(0)).And(qa.bitwiseAnd(1<<3).eq(0)).And(qa.bitwiseAnd(1<<4).eq(0)).And(qa.bitwiseAnd(1<<5).eq(0))
    return image.select([green,nir],["green","nir"]).multiply(0.0000275).add(-0.2).updateMask(clear)
def collection(aoi, start, end):
    sources=[("LANDSAT/LT05/C02/T1_L2","SR_B2","SR_B4"),("LANDSAT/LE07/C02/T1_L2","SR_B2","SR_B4"),("LANDSAT/LC08/C02/T1_L2","SR_B3","SR_B5"),("LANDSAT/LC09/C02/T1_L2","SR_B3","SR_B5")]
    merged=ee.ImageCollection([])
    for name,g,n in sources: merged=merged.merge(ee.ImageCollection(name).filterBounds(aoi).filterDate(start,end).map(lambda img, g=g,n=n: prep(img,g,n)))
    return merged
def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--date",required=True); p.add_argument("--window-days",type=int,default=45); p.add_argument("--ndwi-threshold",type=float,default=.10); p.add_argument("--min-valid-fraction",type=float,default=.70); p.add_argument("--project",default=os.environ.get("OPENIMJA_EE_PROJECT"),help="Earth Engine-enabled Google Cloud project (or set OPENIMJA_EE_PROJECT)"); p.add_argument("--auth-source",choices=["earthengine","application-default"],default="earthengine"); a=p.parse_args()
    if not a.project: p.error("--project (or OPENIMJA_EE_PROJECT) is required; Earth Engine operations must be charged to an enabled Cloud project.")
    if a.auth_source == "application-default":
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/earthengine", "https://www.googleapis.com/auth/cloud-platform"])
        ee.Initialize(credentials=credentials, project=a.project)
    else: ee.Initialize(project=a.project)
    cfg=json.loads(CONFIG.read_text()); aoi=ee.Geometry(cfg["geometry"]); seed=ee.Geometry(cfg["seed_point"]); end=(datetime.fromisoformat(a.date)+timedelta(days=a.window_days+1)).date().isoformat()
    def annotate(img): return img.set("openimja_valid_fraction",img.select("green").mask().reduceRegion(ee.Reducer.mean(),aoi,30,maxPixels=10_000_000).get("green"))
    choices=collection(aoi,a.date,end).map(annotate).filter(ee.Filter.gte("openimja_valid_fraction",a.min_valid_fraction)).sort("CLOUD_COVER")
    if choices.size().getInfo()==0: raise RuntimeError("No Landsat image met criteria; no output written.")
    image=ee.Image(choices.first()); water=image.normalizedDifference(["green","nir"]).gte(a.ndwi_threshold).selfMask().clip(aoi)
    vectors=water.reduceToVectors(geometry=aoi,scale=30,geometryType="polygon",eightConnected=True,labelProperty="water",reducer=ee.Reducer.countEvery(),maxPixels=100_000_000).map(lambda f:f.set("area_m2",f.geometry().area(1)))
    selecteds=vectors.filterBounds(seed).sort("area_m2",False)
    if selecteds.size().getInfo()==0: raise RuntimeError("No water component contains seed point; no output written.")
    selected=ee.Feature(selecteds.first()); properties=image.toDictionary(["system:index","system:id","system:time_start","CLOUD_COVER","openimja_valid_fraction","SPACECRAFT_ID"]).getInfo(); observed=datetime.fromtimestamp(properties["system:time_start"]/1000,timezone.utc); image_id=properties.get("system:id") or properties["system:index"]
    BOUNDARIES.mkdir(parents=True,exist_ok=True); path=BOUNDARIES/f"{observed.date().isoformat()}_landsat_{image_id}.geojson"; feature=selected.set({"lake_id":cfg["id"],"observed_at":z(observed),"image_id":image_id}).getInfo(); path.write_text(json.dumps({"type":"FeatureCollection","features":[feature]},indent=2)+"\n")
    flags=["DRAFT_AOI_REQUIRES_VISUAL_VALIDATION","OPTICAL_WATER_CLASSIFICATION","LANDSAT_30M_RESOLUTION"]
    if properties.get("openimja_valid_fraction",0)<.9: flags.append("PARTIALLY_MASKED_AOI")
    obs={"lake_id":cfg["id"],"variable":"lake_area","value":round(selected.geometry().area(1).getInfo()/1e6,6),"unit":"km2","observed_at":z(observed),"processed_at":z(datetime.now(timezone.utc)),"source":"Landsat","source_product":image_id,"source_url":"https://developers.google.com/earth-engine/datasets/catalog/landsat","method":METHOD,"method_version":VERSION,"parameters":{"index":"NDWI=(green-NIR)/(green+NIR)","ndwi_threshold":a.ndwi_threshold,"cloud_mask":"Landsat QA_PIXEL fill/dilated-cloud/cirrus/cloud/shadow/snow bits","aoi_valid_fraction_minimum":a.min_valid_fraction,"aoi_status":cfg["aoi_status"],"scale_m":30},"confidence":None,"quality_flags":flags,"observation_state":"processed","rejection_reasons":[],"freshness":classify(observed),"boundary_geojson_url":str(path.relative_to(ROOT)),"provenance":{"code_version":revision(),"config_path":"config/lakes/imja-tsho.json","image_id":image_id,"earth_engine_collection":"Landsat Collection 2 Level 2 (merged sensors)","scene_cloud_cover_percent":properties.get("CLOUD_COVER"),"aoi_valid_fraction":properties.get("openimja_valid_fraction")}}
    obs["measurement_family"] = "optical"
    publish(obs, promote_latest=False)
if __name__=="__main__": main()
