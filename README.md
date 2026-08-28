# OpenImja

OpenImja is an experimental open-source observatory for making public observations of Imja Tsho easier to find, reproduce, and understand.

It is **not** an operational flood-warning system. Satellite measurements can be delayed, obscured by cloud, incomplete, or wrong. It does not predict breach probability, issue evacuations, or provide hazard scores. For emergency information, rely on Nepal's official authorities.

Relevant information about glacial lakes is distributed across satellite archives, government systems, research papers, and project reports. OpenImja aims to provide a reproducible public observation layer across those sources, beginning with satellite-derived lake surface area.

## v0.1 milestone

Given Imja Tsho and a date, `pipeline/python/process_sentinel2.py` searches Sentinel-2 Level-2A imagery in a defined date window, applies cloud/snow/shadow masks, calculates NDWI, selects a probable-water polygon connected to the configured lake seed point, and writes an area estimate with provenance. It needs an authenticated Google Earth Engine session; no credentials are committed here.

```sh
python -m venv .venv && . .venv/bin/activate
pip install -r pipeline/python/requirements.txt
earthengine authenticate
python pipeline/python/process_sentinel2.py --date 2025-10-15
```

Review the generated GeoJSON boundary and quality flags before publishing it. The committed `data/latest/imja-tsho.json` currently says that no reviewed observation has been published—this is intentional rather than a fabricated measurement.

## Repository map

- `config/lakes/` — lake metadata and draft processing AOI
- `schemas/` — machine-readable lake and observation contracts
- `pipeline/` — reproducible Earth Engine processing code
- `data/processed/` — detailed JSON records, boundaries, and CSV index
- `data/latest/` — small latest-observation JSON for static consumers
- `web/` — minimal static public interface
- `docs/` — methodology, sources, and limitations

Every published observation should make clear what was measured, when it was observed, source product, method and parameters, quality flags, freshness, and how to reproduce it. See [the methodology](docs/methodology.md) and [limitations](docs/limitations.md).

## Freshness is not risk

`CURRENT`, `AGING`, `STALE`, `HISTORICAL`, and `UNKNOWN` label only the elapsed age of a satellite observation. They do not signal lake hazard or safety. v0.1 uses 14, 45, and 180 days as the current/aging/stale boundaries, recorded alongside each result.

## Development

Serve the repository root with any static file server and open `web/index.html` (for example, `python -m http.server`). No database, account, or backend is required. The GitHub workflow is manual-only while the processing logic is validated.

See [CONTRIBUTING.md](CONTRIBUTING.md) for data and method contribution expectations.
