"""Tests for Governed CTA Registry."""

import sys
import unittest
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parents[1]
if str(PKG_DIR) not in sys.path:
    sys.path.insert(0, str(PKG_DIR))

from cta_registry import ApprovalState, CTARecord, CTARegistry, CTAType


class TestCTARegistry(unittest.TestCase):
    def setUp(self):
        self.registry = CTARegistry()

    def test_approved_ctas_loaded(self):
        vol1_explore = self.registry.get_cta("CTA-BOTANICAL-VOL1-EXPLORE")
        self.assertIsNotNone(vol1_explore)
        self.assertEqual(vol1_explore.cta_type, CTAType.EXPLORE_PRODUCT.value)
        self.assertEqual(vol1_explore.approval_state, ApprovalState.APPROVED.value)
        self.assertTrue(vol1_explore.is_eligible)
        self.assertEqual(
            vol1_explore.destination_url,
            "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/",
        )

    def test_inactive_or_draft_cta_not_active(self):
        draft_cta = self.registry.get_cta("CTA-INACTIVE-TEST-001")
        self.assertIsNotNone(draft_cta)
        self.assertFalse(draft_cta.is_eligible)
        # get_active_cta must return None for inactive/draft
        self.assertIsNone(self.registry.get_active_cta("CTA-INACTIVE-TEST-001"))

    def test_list_approved_ctas_filter_platform(self):
        ig_ctas = self.registry.list_approved_ctas(platform="instagram")
        self.assertTrue(len(ig_ctas) >= 4)
        for cta in ig_ctas:
            self.assertTrue(cta.is_eligible)
            self.assertIn("instagram", [p.lower() for p in cta.allowed_platforms])

    def test_invalid_cta_record_validation(self):
        with self.assertRaises(ValueError):
            CTARecord(
                cta_id="",
                cta_type=CTAType.ASK_BUDLY.value,
                display_label="Test",
                description="desc",
                destination_url="https://wakenbakelounge.com",
                destination_type="landing",
                product_or_topic="UNKNOWN",
                active=True,
                approval_state=ApprovalState.APPROVED.value,
                allowed_platforms=["web"],
                created_at="2026-09-07",
                updated_at="2026-09-07",
            ).validate()

        with self.assertRaises(ValueError):
            CTARecord(
                cta_id="TEST-001",
                cta_type="INVALID_TYPE",
                display_label="Test",
                description="desc",
                destination_url="https://wakenbakelounge.com",
                destination_type="landing",
                product_or_topic="UNKNOWN",
                active=True,
                approval_state=ApprovalState.APPROVED.value,
                allowed_platforms=["web"],
                created_at="2026-09-07",
                updated_at="2026-09-07",
            ).validate()


if __name__ == "__main__":
    unittest.main()
