# Processing pipeline

The v0.1 pipeline is intentionally a command-line workflow that produces plain JSON, CSV, and GeoJSON files. It uses Google Earth Engine only as a reproducible catalogue and compute backend; credentials are supplied by the operator and never stored in this repository.

## Setup

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r pipeline/python/requirements.txt
earthengine authenticate
```

Authenticate with an Earth Engine account that is permitted to use the public collections. Then process a date; the script searches a configurable surrounding window and chooses the least-cloudy candidate that clears the configured AOI validity threshold.

```sh
python pipeline/python/process_sentinel2.py --date 2025-10-15
```

It writes an observation JSON, a GeoJSON boundary, appends a CSV row, and refreshes `data/latest/imja-tsho.json`. Review the output before committing or publishing it. A result is an EO-derived estimate, not an official lake measurement or warning.

For a long-term candidate series (Landsat) and recent Sentinel-2 dates, first inspect the date strategy in `build_history.py`; it deliberately requires `--execute` before it runs processing. Landsat's 30 m results need separate review before comparing them with Sentinel-2.
