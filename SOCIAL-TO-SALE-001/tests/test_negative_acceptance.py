"""Negative Acceptance Tests for SOCIAL-TO-SALE-001 (STS-1).

Verifies all 8 mandatory negative acceptance requirements:
1. Unknown CTA ID rejected or safely downgraded.
2. Inactive CTA never selected.
3. Missing attribution still allows conversation but records source as unknown/direct.
4. Invalid content ID does not create false attribution.
5. Unapproved destination cannot be recommended.
6. Anonymous visitor does not automatically become a lead.
7. No invented price/offer/reservation claim.
8. Repeated identical event does not create duplicate journey records.
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
from lead_threshold import LeadThresholdEvaluator
from qualification import QualificationState


class TestNegativeAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_sales.db"
        self.repo = JourneyRepository(self.db_path)
        self.registry = CTARegistry()
        self.spine = ConversionSpine(self.repo, self.registry)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_negative_1_unknown_cta_downgraded(self):
        """1. Unknown CTA ID rejected or safely downgraded."""
        url = "https://www.wakenbakelounge.com/ask-budly?source=social&platform=instagram&cta_id=CTA-UNKNOWN-999"
        ctx = self.spine.handle_social_landing(url)
        self.assertTrue(ctx.cta_downgraded)
        self.assertEqual(ctx.attribution.cta_id, "CTA-ASK-BUDLY-001")

    def test_negative_2_inactive_cta_never_selected(self):
        """2. Inactive CTA never selected."""
        inactive_id = "CTA-INACTIVE-TEST-001"
        active_cta = self.registry.get_active_cta(inactive_id)
        self.assertIsNone(active_cta)

        # Ensure intake downgrades inactive CTA
        url = f"https://www.wakenbakelounge.com/ask-budly?source=social&platform=instagram&cta_id={inactive_id}"
        ctx = self.spine.handle_social_landing(url)
        self.assertTrue(ctx.cta_downgraded)
        self.assertEqual(ctx.attribution.cta_id, "CTA-ASK-BUDLY-001")

    def test_negative_3_missing_attribution_allows_conversation(self):
        """3. Missing attribution still allows conversation but records source as unknown/direct."""
        url = "https://www.wakenbakelounge.com/ask-budly"
        ctx = self.spine.handle_social_landing(url)
        self.assertEqual(ctx.attribution.source, "direct")
        self.assertEqual(ctx.attribution.platform, "web")
        self.assertEqual(ctx.attribution.content_id, "")

        # Conversation continues smoothly
        turn = self.spine.process_turn(ctx.session_id, "Hi there")
        self.assertEqual(turn.intent, CommercialIntent.GENERAL_CONVERSATION.value)
        self.assertIn("https://www.wakenbakelounge.com/ask-budly", turn.recommended_destination)

    def test_negative_4_invalid_content_id_does_not_create_false_attribution(self):
        """4. Invalid content ID (e.g. script/malformed/PII) is sanitized."""
        dirty_content_id = "IG-POST-<script>alert(1)</script>@email.com"
        cleaned = AttributionStandard.clean_param(dirty_content_id)
        self.assertNotIn("<script>", cleaned)
        self.assertNotIn("@", cleaned)

        params = {"source": "social", "platform": "instagram", "content_id": "test@user.com"}
        ctx = self.spine.handle_social_landing(params)
        # Content ID containing PII is stripped
        self.assertEqual(ctx.attribution.content_id, "")

    def test_negative_5_unapproved_destination_cannot_be_recommended(self):
        """5. Unapproved destination cannot be recommended."""
        # For arbitrary unknown intent/topic, verify returned destination is in approved registry
        approved_urls = {cta.destination_url for cta in self.registry.list_approved_ctas()}
        turn = self.spine.process_turn("anon_sess_1", "What do you sell?")
        self.assertIn(turn.recommended_destination, approved_urls)

    def test_negative_6_anonymous_visitor_does_not_become_lead(self):
        """6. Anonymous visitor does not automatically become a lead."""
        ctx = self.spine.handle_social_landing("https://www.wakenbakelounge.com/ask-budly")
        turn = self.spine.process_turn(ctx.session_id, "Good morning, just saying hi")
        self.assertFalse(turn.is_lead)
        self.assertIsNone(turn.lead_id)
        self.assertIsNone(turn.lead_promotion_reason)
        # Verify in DB
        journey = self.repo.get_journey(ctx.journey_id)
        self.assertIsNotNone(journey)
        self.assertIsNone(journey.lead_id)

    def test_negative_7_no_invented_price_or_offer_claims(self):
        """7. No invented price/offer/reservation claims in recommendation dialogue."""
        turn = self.spine.process_turn("sess_test_claims", "Can I book a table or get a discount?")
        # Budly does not invent a discount or booking flow; routes to verified CTA
        self.assertNotIn("50% off", turn.bot_message)
        self.assertNotIn("table reserved", turn.bot_message)
        self.assertNotIn("free discount", turn.bot_message)

    def test_negative_8_idempotency_prevents_duplicate_journey(self):
        """8. Repeated identical event does not create duplicate journey records."""
        landing_params = {
            "source": "social",
            "platform": "instagram",
            "content_id": "IG-20260906-0002",
            "campaign_id": "STS-PILOT-001",
            "cta_id": "CTA-ASK-BUDLY-001",
        }
        fixed_session_id = "sess_fixed_12345"

        # First entry
        entry1 = self.spine.handle_social_landing(landing_params, session_id=fixed_session_id)
        self.assertTrue(entry1.is_new_session)

        # Second identical entry with same session
        entry2 = self.spine.handle_social_landing(landing_params, session_id=fixed_session_id)
        self.assertFalse(entry2.is_new_session)
        self.assertEqual(entry1.journey_id, entry2.journey_id)

        # Verify only one journey record exists for this session
        journey = self.repo.get_by_session(fixed_session_id)
        self.assertIsNotNone(journey)
        self.assertEqual(journey.journey_id, entry1.journey_id)


if __name__ == "__main__":
    unittest.main()
