# Data sources

| Source | v0.1 use | Notes |
| --- | --- | --- |
| Sentinel-2 Level-2A | Implemented processor for recent optical estimates | Surface reflectance in Google Earth Engine collection `COPERNICUS/S2_SR_HARMONIZED`. |
| Landsat Collection 2 Level 2 | Historical strategy only | Annual candidate dates are scaffolded; a sensor-specific masking/index adapter must be validated before data are published. |
| Sentinel-1 GRD | Designed for, not implemented | Future cloud-independent complement; do not compare directly with optical estimates without validation. |
| Nepal DHM and partner ground sources | Placeholder only | No DHM data are fetched or represented in v0.1. |

The Imja reference location and elevation require careful source review. The initial ICIMOD story-map coordinate used in this repository proved visibly inconsistent with the lake. The revised candidate reference is the commonly reported 27°53′55″N, 86°55′20″E, but remains explicitly unverified as a processing seed. This is a reference point, not a surveyed shoreline. Product-specific terms and access conditions remain those of their respective providers.

To add a ground source, document a stable public endpoint or a permitted data-sharing agreement; map source timestamps and units; retain raw responses where licensing permits; add a source-specific schema/adapter; and publish latency, gaps, calibration, and quality information. No future feed should be treated as an emergency alert by default.
