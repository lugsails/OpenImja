# Future source adapters

This folder reserves a narrow adapter contract for Nepal DHM lake level, stream gauges, precipitation, snow, temperature, and warning-system status. v0.1 contains no active adapter and makes no network requests to those services.

Before adding an adapter, document the stable public endpoint or permission, terms of use, station/location identity, native timestamp/timezone, units and datum, expected latency, missing-data behaviour, calibration, and quality flags. Preserve a raw reference or permitted raw copy, then normalize into `SourceRecord` without conflating it with satellite-derived lake area. A source adapter must never turn a status feed into an evacuation recommendation.
