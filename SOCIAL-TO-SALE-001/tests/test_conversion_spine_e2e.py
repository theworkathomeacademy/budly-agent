"""End-to-end simulated acceptance scenario and observability validation for STS-1."""

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


class TestConversionSpineE2E(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_sales.db"
        self.repo = JourneyRepository(self.db_path)
        self.registry = CTARegistry()
        self.spine = ConversionSpine(self.repo, self.registry)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_end_to_end_pilot_journey_with_observability(self):
        """Simulates full Instagram -> Ask Budly -> Anonymous Botanical Recommendation -> Voluntary Identity Lead Promotion."""
        # 1. Instagram outbound link generation
        attr = AttributionContext(
            source="social",
            platform="instagram",
            content_id="IG-20260906-0002",
            campaign_id="STS-PILOT-001",
            cta_id="CTA-ASK-BUDLY-001",
            product_or_topic="BOTANICAL_COLLECTION",
            published_post_id="POST-BOTANICAL-01",
        )
        instagram_bio_link = AttributionStandard.build_url(
            "https://www.wakenbakelounge.com/ask-budly",
            attr,
        )

        # 2. User clicks link and lands on Ask Budly
        entry_ctx = self.spine.handle_social_landing(instagram_bio_link)
        session_id = entry_ctx.session_id
        journey_id = entry_ctx.journey_id

        # Observability Check 1: Where did they come from / post / CTA?
        initial_journey = self.repo.get_journey(journey_id)
        self.assertIsNotNone(initial_journey)
        self.assertEqual(initial_journey.source, "social")
        self.assertEqual(initial_journey.platform, "instagram")
        self.assertEqual(initial_journey.content_id, "IG-20260906-0002")
        self.assertEqual(initial_journey.campaign_id, "STS-PILOT-001")
        self.assertEqual(initial_journey.cta_id, "CTA-ASK-BUDLY-001")

        # 3. User expresses interest in Botanical Collection anonymously
        turn1 = self.spine.process_turn(
            session_id,
            "I saw your Instagram post about the botanical collection volume 1, can you tell me what it is?",
        )

        # Observability Check 2: What did they want / topic / qualification / destination?
        self.assertEqual(turn1.intent, CommercialIntent.PRODUCT_INTEREST.value)
        self.assertEqual(turn1.product_or_topic, ProductTopic.BOTANICAL_COLLECTION.value)
        self.assertEqual(turn1.qualification_state, QualificationState.QUALIFIED_NURTURE.value)
        # BROS Lifecycle: Still anonymous, so is_lead is False
        self.assertFalse(turn1.is_lead)
        self.assertIsNone(turn1.lead_id)
        self.assertEqual(
            turn1.recommended_destination,
            "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/",
        )
        self.assertIn("source", turn1.evidence)
        self.assertEqual(turn1.evidence["content_id"], "IG-20260906-0002")

        # 4. Multi-turn purchase confirmation anonymously
        turn2 = self.spine.process_turn(
            session_id,
            "Looks awesome, I'm ready to buy the book now!",
        )

        # Observability Check 3: Did journey advance while preserving anonymous status?
        self.assertEqual(turn2.intent, CommercialIntent.PURCHASE_INTENT.value)
        self.assertEqual(turn2.qualification_state, QualificationState.QUALIFIED_PURCHASE_READY.value)
        self.assertEqual(turn2.recommended_cta_id, "CTA-BOTANICAL-VOL1-SHOP")
        self.assertFalse(turn2.is_lead)
        self.assertIsNone(turn2.lead_id)

        # 5. Subsequent Voluntary Identity Submission on Same Session
        turn3 = self.spine.process_turn(
            session_id,
            "Please email me receipt info at morgan@example.com",
            contact_data={"email": "morgan@example.com", "name": "Morgan"},
        )
        self.assertTrue(turn3.is_lead)
        self.assertIsNotNone(turn3.lead_id)

        journey_final = self.repo.get_journey(journey_id)
        self.assertIsNotNone(journey_final)
        self.assertEqual(journey_final.conversion_state, "recommended")
        self.assertEqual(journey_final.qualification_state, QualificationState.QUALIFIED_PURCHASE_READY.value)
        self.assertEqual(journey_final.lead_id, turn3.lead_id)
        self.assertEqual(
            journey_final.recommended_destination,
            "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/",
        )


if __name__ == "__main__":
    unittest.main()
