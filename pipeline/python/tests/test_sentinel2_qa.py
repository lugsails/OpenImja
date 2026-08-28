import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from sentinel2_qa import assess_scene


ROOT = Path(__file__).resolve().parents[3]
POLICY = json.loads((ROOT / "config/lakes/imja-tsho.json").read_text())["sentinel2_qa"]
REFERENCE = {"observation_state": "published", "observed_at": "2025-11-17T05:01:00.426000Z", "value": 1.34024, "source_product": "COPERNICUS/S2_SR_HARMONIZED/20251117T044959_20251117T045240_T45RVL"}


class Sentinel2QaExamplesTest(unittest.TestCase):
    def test_november_2024_passes_with_actual_envelope_fraction(self):
        decision = assess_scene(aoi_valid_fraction=0.8370346055561986, lake_envelope_valid_fraction=0.9384547694473779, lake_area_km2=1.654877, observed_at=datetime(2024, 11, 7, tzinfo=timezone.utc), reference_records=[REFERENCE], policy=POLICY)
        self.assertEqual(decision.state, "processed")
        self.assertEqual(decision.rejection_reasons, [])

    def test_november_2025_reference_scene_passes(self):
        decision = assess_scene(aoi_valid_fraction=0.6029874558914119, lake_envelope_valid_fraction=1.0, lake_area_km2=1.34024, observed_at=datetime(2025, 11, 17, tzinfo=timezone.utc), reference_records=[REFERENCE], policy=POLICY)
        self.assertEqual(decision.state, "processed")

    def test_august_2026_is_rejected(self):
        decision = assess_scene(aoi_valid_fraction=0.38245046193541227, lake_envelope_valid_fraction=0.2874621612108415, lake_area_km2=0.130205, observed_at=datetime(2026, 8, 11, tzinfo=timezone.utc), reference_records=[REFERENCE], policy=POLICY)
        self.assertEqual(decision.state, "rejected")
        self.assertIn("LOW_LAKE_ENVELOPE_OBSERVABILITY", decision.rejection_reasons)
        self.assertIn("TEMPORAL_AREA_CHANGE_OUTLIER", decision.rejection_reasons)


if __name__ == "__main__":
    unittest.main()
