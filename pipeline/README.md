# Processing pipeline

The v0.1 pipeline is intentionally a command-line workflow that produces plain JSON, CSV, and GeoJSON files. It uses Google Earth Engine only as a reproducible catalogue and compute backend; credentials are supplied by the operator and never stored in this repository.

## Setup

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r pipeline/python/requirements.txt
export OPENIMJA_EE_PROJECT="your-earth-engine-enabled-cloud-project"
earthengine authenticate --auth_mode=gcloud --scopes=https://www.googleapis.com/auth/earthengine,https://www.googleapis.com/auth/cloud-platform --force
earthengine set_project "$OPENIMJA_EE_PROJECT"
```

Before authenticating, register the project through `https://code.earthengine.google.com/register?project=YOUR_PROJECT_ID`; this enables/ registers Earth Engine access for the selected commercial or noncommercial use. Authenticate with an account that is permitted to use that project. `gcloud` mode uses Google's supported command-line OAuth flow, and the explicit scopes above omit Drive because this pipeline does not export to Drive. If Google blocks a consent screen, do not bypass it or paste credentials anywhere: confirm the account/project has Earth Engine access, use `gcloud` mode, and ask the Workspace administrator to allow Google Cloud/Earth Engine if the account is managed. Then process a date; the script searches a configurable surrounding window and chooses the least-cloudy candidate that clears the configured AOI validity threshold.

If you authenticated with `gcloud auth application-default login` instead, pass `--auth-source application-default` to a processor. This uses the current Google application-default credential when an old Earth Engine credential file is unusable.

```sh
python pipeline/python/process_sentinel2.py --date 2025-10-15
```

It writes an observation JSON, a GeoJSON boundary, and a CSV row. It does **not** update `data/latest/imja-tsho.json` unless `--promote-latest` is supplied after visual review of the candidate boundary. A result is an EO-derived estimate, not an official lake measurement or warning.

Historical backfills are idempotent by source product: the CSV replaces a matching product row and remains date-sorted. An older acquisition cannot displace a newer `data/latest` observation.

## Validate before a first publication

Open `earth_engine/imja_sentinel2_inspect.js` in the Earth Engine Code Editor and select the configured Cloud project. It renders the raw RGB image, SCL classes, raw NDWI, masked probable water, draft AOI, and draft seed point. Adjusting the configuration or threshold requires recording why and visually reviewing the resulting boundary; do not lower criteria simply to fill a data gap.

For a long-term candidate series (Landsat) and recent Sentinel-2 dates, first inspect the date strategy in `build_history.py`; it deliberately requires `--execute` before it runs processing. Landsat's 30 m results need separate review before comparing them with Sentinel-2.
