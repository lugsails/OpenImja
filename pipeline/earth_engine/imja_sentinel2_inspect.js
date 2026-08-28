// OpenImja v0.1 visual validation helper.
// Paste into https://code.earthengine.google.com/ after selecting your Cloud project.
// It does not export, publish, or make a warning. Use it to validate the draft AOI,
// seed point, masks, and threshold before publishing a derived observation.

var aoi = ee.Geometry.Polygon([[
  [86.913, 27.893], [86.942, 27.893], [86.942, 27.906],
  [86.913, 27.906], [86.913, 27.893]
]]);
var seed = ee.Geometry.Point([86.9222222, 27.8986111]);
var start = '2025-10-15';
var end = '2025-11-30';
var threshold = 0.10;

function maskS2(image) {
  var qa = image.select('QA60');
  var qaClear = qa.bitwiseAnd(1 << 10).eq(0)
    .and(qa.bitwiseAnd(1 << 11).eq(0));
  var scl = image.select('SCL');
  var sclClear = scl.neq(0).and(scl.neq(1)).and(scl.neq(3))
    .and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));
  return image.updateMask(qaClear.and(sclClear));
}

var scenes = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
  .filterBounds(aoi)
  .filterDate(start, end)
  .sort('CLOUDY_PIXEL_PERCENTAGE');
var image = ee.Image(scenes.first());
var masked = maskS2(image);
var rawNdwi = image.normalizedDifference(['B3', 'B8']).rename('raw_ndwi');
var maskedNdwi = masked.normalizedDifference(['B3', 'B8']).rename('masked_ndwi');
var water = maskedNdwi.gte(threshold).selfMask();

print('Candidate scenes', scenes.size());
print('Selected image', image.toDictionary(['system:index', 'system:time_start', 'CLOUDY_PIXEL_PERCENTAGE']));
print('Seed pixel: raw bands and SCL', image.select(['B3', 'B8', 'SCL', 'QA60']).reduceRegion({reducer: ee.Reducer.first(), geometry: seed, scale: 10}));
print('Seed pixel: raw NDWI', rawNdwi.reduceRegion({reducer: ee.Reducer.first(), geometry: seed, scale: 10}));

Map.centerObject(aoi, 14);
Map.addLayer(image.clip(aoi), {bands: ['B4', 'B3', 'B2'], min: 0, max: 3500}, 'raw Sentinel-2 RGB');
Map.addLayer(image.select('SCL').clip(aoi), {min: 0, max: 11, palette: ['000000', 'ff0000', '2f2f2f', '643200', '00a000', 'ffe65a', '0000ff', '808080', 'c0c0c0', 'ffffff', 'b4b4ff', 'ff96ff']}, 'SCL classes');
Map.addLayer(rawNdwi.clip(aoi), {min: -0.5, max: 0.5, palette: ['8a5a44', 'f5f5f0', '187d91']}, 'raw NDWI');
Map.addLayer(water.clip(aoi), {palette: ['187d91']}, 'masked probable water (threshold ' + threshold + ')');
Map.addLayer(aoi, {color: 'f2b134'}, 'draft AOI');
Map.addLayer(seed, {color: 'ff3f2f'}, 'draft seed point');
