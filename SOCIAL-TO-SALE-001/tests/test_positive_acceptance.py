"""Positive Acceptance Tests for SOCIAL-TO-SALE-001 (STS-1).

Verifies all 9 mandatory positive acceptance requirements with BROS known-visitor lifecycle governance:
1. Valid attributed Instagram entry captured.
2. Correct content ID attached to journey.
3. Ask Budly session created.
4. Product interest recognized.
5. Journey updated deterministically.
6. Appropriate qualification state assigned.
7. Approved CTA selected.
8. Approved destination returned.
9. No manual data transfer by d-mac (automatic persistence, canonical CRM lead promotion upon voluntary identity).
"""

import sys
import tempfile
import unittest
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parents[1]
if str(PKG_DIR) not in sys.path:
    sys.path.insert(0, str(PKG_DIR))

from attribution import AttributionContext, AttributionStandard
from conversion_spine import ConversionSpine
from cta_registry import CTARegistry
from intent_taxonomy import CommercialIntent, ProductTopic
from journey_repository import JourneyRepository
from qualification import QualificationState


class TestPositiveAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_sales.db"
        self.repo = JourneyRepository(self.db_path)
        self.registry = CTARegistry()
        self.spine = ConversionSpine(self.repo, self.registry)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_complete_positive_conversion_spine_journey(self):
        # 1. Valid attributed Instagram entry captured
        landing_url = (
            "https://www.wakenbakelounge.com/ask-budly"
            "?source=social"
            "&platform=instagram"
            "&content_id=IG-20260906-0002"
            "&campaign_id=STS-PILOT-001"
            "&cta_id=CTA-ASK-BUDLY-001"
            "&product_or_topic=BOTANICAL_COLLECTION"
        )
        entry_ctx = self.spine.handle_social_landing(landing_url)
        self.assertIsNotNone(entry_ctx.session_id)
        self.assertIsNotNone(entry_ctx.journey_id)
        self.assertEqual(entry_ctx.attribution.source, "social")
        self.assertEqual(entry_ctx.attribution.platform, "instagram")

        # 2. Correct content ID attached to journey
        self.assertEqual(entry_ctx.attribution.content_id, "IG-20260906-0002")
        self.assertEqual(entry_ctx.attribution.campaign_id, "STS-PILOT-001")
        journey_record = self.repo.get_journey(entry_ctx.journey_id)
        self.assertIsNotNone(journey_record)
        self.assertEqual(journey_record.content_id, "IG-20260906-0002")

        # 3. Ask Budly session created
        self.assertEqual(journey_record.session_id, entry_ctx.session_id)
        self.assertEqual(journey_record.conversion_state, "initiated")

        # 4. Product interest recognized
        user_msg = "Tell me more about the Botanical Collection Volume 1 book"
        turn_res = self.spine.process_turn(entry_ctx.session_id, user_msg)
        self.assertEqual(turn_res.intent, CommercialIntent.PRODUCT_INTEREST.value)
        self.assertEqual(turn_res.product_or_topic, ProductTopic.BOTANICAL_COLLECTION.value)

        # 5. Journey updated deterministically
        updated_journey = self.repo.get_journey(entry_ctx.journey_id)
        self.assertIsNotNone(updated_journey)
        self.assertEqual(updated_journey.intent, CommercialIntent.PRODUCT_INTEREST.value)
        self.assertEqual(updated_journey.product_or_topic, ProductTopic.BOTANICAL_COLLECTION.value)

        # 6. Appropriate qualification state assigned
        self.assertEqual(turn_res.qualification_state, QualificationState.QUALIFIED_NURTURE.value)
        self.assertEqual(updated_journey.qualification_state, QualificationState.QUALIFIED_NURTURE.value)

        # Anonymous visitor is NOT a CRM Lead yet
        self.assertFalse(turn_res.is_lead)
        self.assertIsNone(turn_res.lead_id)

        # 7. Approved CTA selected
        self.assertIn(turn_res.recommended_cta_id, ["CTA-BOTANICAL-VOL1-EXPLORE", "CTA-BOTANICAL-VOL1-SHOP"])
        cta_record = self.registry.get_active_cta(turn_res.recommended_cta_id)
        self.assertIsNotNone(cta_record)
        self.assertTrue(cta_record.is_eligible)

        # 8. Approved destination returned
        expected_dest = "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/"
        self.assertEqual(turn_res.recommended_destination, expected_dest)
        self.assertEqual(updated_journey.recommended_destination, expected_dest)

        # 9. No manual data transfer by d-mac: Upon voluntary identity submission, canonical Lead is linked automatically
        turn_with_identity = self.spine.process_turn(
            entry_ctx.session_id,
            "I'd like to buy it, my email is alex@example.com",
            contact_data={"email": "alex@example.com", "name": "Alex"},
        )
        self.assertTrue(turn_with_identity.is_lead)
        self.assertIsNotNone(turn_with_identity.lead_id)
        lead_record = self.repo.get_lead(turn_with_identity.lead_id)
        self.assertIsNotNone(lead_record)
        self.assertEqual(lead_record.journey_id, entry_ctx.journey_id)
        self.assertEqual(lead_record.product_or_topic, ProductTopic.BOTANICAL_COLLECTION.value)


if __name__ == "__main__":
    unittest.main()
