# Methodology

OpenImja v0.1 estimates surface water extent from public satellite imagery. It is an experimental, reproducible observation method—not a calibrated operational measurement and not a flood-warning method.

## Optical sources

Recent estimates use Sentinel-2 Level-2A surface reflectance (`COPERNICUS/S2_SR_HARMONIZED` in Google Earth Engine). The historical plan uses annual Landsat Collection 2 Level-2 observations, with a Landsat adapter to be validated before results are published. The chosen source product ID and acquisition time are kept with every result.

## Water extent

For Sentinel-2, the current processor masks pixels flagged as cloud, cirrus, cloud shadow, snow/ice, saturated/defective, or no-data using QA60 and SCL. It calculates normalized difference water index (NDWI): `(green - NIR) / (green + NIR)`, using B3 and B8. Pixels at or above a configurable threshold (default 0.10) are considered *probable water*. Connected polygons are made from those pixels, and the polygon containing the configuration's seed point is selected. Its geodesic area is reported in km².

The configuration's AOI and seed point are deliberately marked `draft_requires_visual_validation`. They must be visually reviewed with each new method version. A fixed threshold is not universal; it can fail as water colour, ice, shadow, illumination, or sensor conditions change. The threshold and mask choices are recorded in every observation.

## Quality and uncertainty

Scene-wide cloud percentage is only a coarse signal. The processor also records its calculated unmasked fraction inside the AOI. It fails rather than emitting a measurement when no candidate scene clears that fraction or no selected component contains the seed point. This does not make accepted images correct. Boundary pixels, mixed pixels, thin ice, debris, steep terrain, cloud edge, and topographic shadow all introduce uncertainty. v0.1 reports `confidence: null` rather than inventing a probability; validation against reviewed boundaries is needed to develop a defensible uncertainty model.

## Optical versus SAR

Optical imagery is affected by cloud and illumination but provides spectral water indices. Sentinel-1 synthetic-aperture radar can observe through cloud and can complement optical coverage, but its backscatter is sensitive to roughness, geometry, terrain effects, and wet snow. Sentinel-1 is reserved in the data model for future work; it is not blended into v0.1 values.

## Reproducibility

Each record carries acquisition time, processing time, source product ID, collection, parameters, code revision, configuration path, quality flags, freshness evaluation, and a derived GeoJSON boundary. The CSV is a convenient index; the observation JSON is the authoritative detailed record.
