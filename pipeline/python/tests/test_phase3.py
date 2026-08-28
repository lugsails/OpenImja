import unittest
from datetime import datetime, timezone

from lifecycle import should_update_latest
from pairing import observation_pairs, summarize_pairs
from sar_qa import assess_sar_scene
from sentinel2_qa import nearest_reference


class TemporalAndLifecycleTest(unittest.TestCase):
    def test_reference_is_most_recent_preceding_only(self):
        candidate = datetime(2025, 6, 1, tzinfo=timezone.utc)
        records = [
            {"observation_state": "published", "observed_at": "2025-01-01T00:00:00Z", "value": 1, "source_product": "older-past"},
            {"observation_state": "published", "observed_at": "2025-05-20T00:00:00Z", "value": 1, "source_product": "past"},
            {"observation_state": "published", "observed_at": "2025-06-02T00:00:00Z", "value": 1, "source_product": "future"},
        ]
        self.assertEqual(nearest_reference(candidate, records, 365, 1)["source_product"], "past")

    def test_publishing_older_record_does_not_regress_latest(self):
        existing = {"latest_observation": {"observation_state": "published", "observed_at": "2025-11-17T00:00:00Z"}}
        older = {"observation_state": "published", "observed_at": "2024-11-07T00:00:00Z"}
        newer = {"observation_state": "published", "observed_at": "2026-01-01T00:00:00Z"}
        self.assertFalse(should_update_latest(existing, older))
        self.assertTrue(should_update_latest(existing, newer))


class SarAndPairingTest(unittest.TestCase):
    def test_sar_low_envelope_is_rejected(self):
        decision = assess_sar_scene(lake_envelope_valid_fraction=0.28, lake_area_km2=0.13, policy={"minimum_lake_envelope_valid_fraction": 0.8, "minimum_component_area_km2": 0.05})
        self.assertEqual(decision.state, "rejected")
        self.assertIn("LOW_LAKE_ENVELOPE_OBSERVABILITY", decision.rejection_reasons)

    def test_pairs_keep_rejected_sar_and_calculate_difference(self):
        optical = [{"measurement_family": "optical", "observation_state": "published", "observed_at": "2025-11-17T05:00:00Z", "value": 1.34, "source_product": "s2", "quality_flags": []}]
        sar = [{"measurement_family": "sar", "observation_state": "rejected", "observed_at": "2025-11-18T05:00:00Z", "value": 1.0, "source_product": "s1", "quality_flags": ["LOW_LAKE_ENVELOPE_OBSERVABILITY"], "provenance": {"orbit_pass": "DESCENDING"}}]
        pairs = observation_pairs(optical, sar, 3)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["sentinel1_state"], "rejected")
        self.assertAlmostEqual(pairs[0]["absolute_area_difference_km2"], 0.34)
        self.assertEqual(summarize_pairs(pairs)["overall"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
