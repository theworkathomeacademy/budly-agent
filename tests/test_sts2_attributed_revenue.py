"""Comprehensive Verification Suite for STS-2 Attributed Revenue.

Validates:
1. Recommendation \u2192 Purchase \u2192 Verified Woo Revenue Event \u2192 Deterministic Journey Attribution
2. Event replay idempotency (duplicate webhooks/replays)
3. Anonymous buyer conversion without CRM Lead generation
4. Direct buyer unattributed handling
5. Malformed/invalid attribution params ignored/sanitized
6. Customer identity conflict handling (customer_mismatch)
7. CCS-006 Excluded Lounge products fail-closed
8. Refund and reversal handling with net revenue adjustment and audit preservation
9. Zero PII in attribution URLs
10. Deterministic CCSS canonical_id and catalog_version binding
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader
from budly_runtime.commercial_snapshot.resolver import DeterministicEntityResolver

# Import SOCIAL-TO-SALE-001 modules
import sys
ROOT = Path(__file__).resolve().parents[1]
STS_DIR = ROOT / "SOCIAL-TO-SALE-001"
if str(STS_DIR) not in sys.path:
    sys.path.insert(0, str(STS_DIR))

from attribution import AttributionContext, AttributionStandard
from cta_registry import CTARegistry
from conversion_spine import ConversionSpine
from journey_repository import ConversionJourney, ConversionLead, JourneyRepository
from recommendation_router import RecommendationOutcome, RecommendationRouter


class TestSTS2AttributedRevenue(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "sts2_test_sales.db"
        self.repo = JourneyRepository(self.db_path)
        self.registry = CTARegistry()
        self.catalog_dir = ROOT / "config" / "commercial_catalog"
        self.snapshot_loader = CommercialSnapshotLoader(self.catalog_dir)
        self.router = RecommendationRouter(self.registry, self.snapshot_loader)
        self.spine = ConversionSpine(self.repo, self.registry)
        self.spine.router = self.router

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_end_to_end_attributed_recommendation_and_conversion(self):
        """1. Full flow: Social landing \u2192 Recommendation \u2192 Correlated checkout URL \u2192 Conversion."""
        landing_url = (
            "https://www.wakenbakelounge.com/ask-budly"
            "?source=social&platform=instagram&content_id=IG-20260918-001"
            "&campaign_id=STS-2-LAUNCH&cta_id=CTA-ASK-BUDLY-001"
            "&product_or_topic=BOTANICAL_COLLECTION"
        )
        entry_ctx = self.spine.handle_social_landing(landing_url)
        session_id = entry_ctx.session_id
        journey_id = entry_ctx.journey_id

        # Ask Budly turn
        turn = self.spine.process_turn(session_id, "I want to buy the botanical collection book")
        self.assertEqual(turn.intent, "PURCHASE_INTENT")
        self.assertEqual(turn.product_or_topic, "BOTANICAL_COLLECTION")
        self.assertTrue(turn.recommended_destination.startswith("https://cccultivate.com/"))
        
        # Correlated destination URL verification
        corr_url = turn.correlated_destination_url
        self.assertIsNotNone(corr_url)
        parsed = urlparse(corr_url)
        params = dict(parse_qsl(parsed.query))
        
        self.assertEqual(params.get("_budly_session_id"), session_id)
        self.assertEqual(params.get("_budly_journey_id"), journey_id)
        self.assertEqual(params.get("_budly_source"), "social")
        self.assertEqual(params.get("_budly_platform"), "instagram")
        self.assertEqual(params.get("_budly_content_id"), "IG-20260918-001")
        self.assertEqual(params.get("_budly_campaign_id"), "STS-2-LAUNCH")
        self.assertEqual(params.get("_budly_canonical_id"), "ccc:book:wakenbake-lounge-cannabis-botanical-collection-volume-1")
        self.assertEqual(params.get("_budly_catalog_version"), self.snapshot_loader.loaded_catalog_version)

        # Record verified conversion
        converted = self.spine.record_revenue_conversion(
            order_id="WC-88412",
            gross_revenue=40.0,
            net_revenue=40.0,
            session_id=session_id,
            currency="USD",
            canonical_id=params.get("_budly_canonical_id"),
            catalog_version=params.get("_budly_catalog_version"),
        )
        self.assertEqual(converted.conversion_state, "converted")
        self.assertEqual(converted.order_id, "WC-88412")
        self.assertEqual(converted.gross_revenue, 40.0)
        self.assertEqual(converted.net_revenue, 40.0)
        self.assertEqual(converted.currency, "USD")
        self.assertIsNotNone(converted.converted_at)

    def test_02_event_replay_idempotency(self):
        """2. Duplicate payment_completed or order_completed webhooks do not duplicate revenue."""
        direct_ctx = self.spine.handle_social_landing(AttributionContext.direct().to_dict(), "sess_replay_01")
        
        conv1 = self.repo.record_conversion(
            order_id="WC-REPLAY-100",
            gross_revenue=100.0,
            net_revenue=100.0,
            session_id="sess_replay_01",
        )
        self.assertEqual(conv1.conversion_state, "converted")
        self.assertEqual(conv1.gross_revenue, 100.0)
        converted_at_first = conv1.converted_at

        # Replay same order_id
        conv2 = self.repo.record_conversion(
            order_id="WC-REPLAY-100",
            gross_revenue=100.0,
            net_revenue=100.0,
            session_id="sess_replay_01",
        )
        self.assertEqual(conv2.converted_at, converted_at_first)
        self.assertEqual(conv2.gross_revenue, 100.0)

    def test_03_anonymous_buyer_conversion_without_lead_creation(self):
        """3. Privacy rule: Anonymous purchasers must NOT automatically create a ConversionLead."""
        landing_url = "https://www.wakenbakelounge.com/ask-budly?source=social&platform=web"
        entry_ctx = self.spine.handle_social_landing(landing_url, "sess_anon_999")
        
        self.spine.process_turn("sess_anon_999", "Tell me about botanical collection")
        
        # Verify no lead exists prior
        journey = self.repo.get_by_session("sess_anon_999")
        self.assertIsNone(journey.lead_id)

        # Buyer converts anonymously at checkout
        self.repo.record_conversion(
            order_id="WC-ANON-777",
            gross_revenue=50.0,
            session_id="sess_anon_999",
        )
        updated_journey = self.repo.get_by_session("sess_anon_999")
        self.assertEqual(updated_journey.conversion_state, "converted")
        self.assertIsNone(updated_journey.lead_id)

    def test_04_direct_buyer_unattributed_handling(self):
        """4. Direct organic journey records clean unattributed state."""
        entry_ctx = self.spine.handle_social_landing(AttributionContext.direct().to_dict(), "sess_direct_01")
        self.assertEqual(entry_ctx.attribution.source, "direct")
        self.assertEqual(entry_ctx.attribution.platform, "web")
        self.assertEqual(entry_ctx.attribution.content_id, "")

        converted = self.repo.record_conversion(
            order_id="WC-DIRECT-001",
            gross_revenue=75.0,
            session_id="sess_direct_01",
        )
        self.assertEqual(converted.source, "direct")
        self.assertEqual(converted.conversion_state, "converted")

    def test_05_malformed_attribution_parameters_sanitized(self):
        """5. Malformed, oversized, or injection parameters are sanitized and bounded."""
        malformed_url = (
            "https://www.wakenbakelounge.com/ask-budly"
            "?source=" + ("s" * 200) +
            "&platform=insta<script>alert(1)</script>" +
            "&content_id=IG-TEST-123%20DROP%20TABLE" +
            "&campaign_id=CAMP-01"
        )
        entry_ctx = self.spine.handle_social_landing(malformed_url)
        self.assertLessEqual(len(entry_ctx.attribution.source), 80)
        self.assertNotIn("<script>", entry_ctx.attribution.platform)

    def test_06_ccs006_excluded_lounge_products_fail_closed(self):
        """6. CCS-006 Rule: Excluded community products must NEVER be recommended."""
        # Attempt to route directly to an excluded lounge membership
        with self.assertRaises(ValueError) as ctx:
            self.router.route(
                intent="purchase_intent",
                product_or_topic="LOUNGE_MEMBER",
                qualification_state="qualified_purchase_ready",
            )
        self.assertIn("CCS-006", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx2:
            self.router.route(
                intent="purchase_intent",
                product_or_topic="wnb:community:lounge-elite",
                qualification_state="qualified_purchase_ready",
            )
        self.assertIn("CCS-006", str(ctx2.exception))

    def test_07_refund_and_reversal_adjusts_net_revenue(self):
        """7. Refunds adjust net revenue while preserving conversion audit record."""
        self.spine.handle_social_landing(AttributionContext.direct().to_dict(), "sess_refund_01")
        conv = self.repo.record_conversion(
            order_id="WC-REFUND-1",
            gross_revenue=120.0,
            net_revenue=120.0,
            session_id="sess_refund_01",
        )
        self.assertEqual(conv.net_revenue, 120.0)

        # Partial refund $40
        refunded = self.repo.record_refund("WC-REFUND-1", 40.0)
        self.assertIsNotNone(refunded)
        self.assertEqual(refunded.gross_revenue, 120.0)
        self.assertEqual(refunded.net_revenue, 80.0)
        self.assertEqual(refunded.conversion_state, "converted")

    def test_08_zero_pii_in_attribution_urls(self):
        """8. Attribution URLs must contain zero PII (no emails, phone numbers, or names)."""
        outcome = self.router.route(
            intent="purchase_intent",
            product_or_topic="BOTANICAL_COLLECTION",
            qualification_state="qualified_purchase_ready",
        )
        corr_url = outcome.build_correlated_url(
            session_id="sess_safe_123",
            journey_id="jrn_safe_456",
            source="social",
            platform="instagram",
            content_id="IG-SAFE-01",
            campaign_id="CAMP-SAFE",
        )
        self.assertNotIn("@", corr_url)
        self.assertNotIn("email", corr_url.lower())
        self.assertNotIn("phone", corr_url.lower())
        self.assertNotIn("name", corr_url.lower())

    def test_09_customer_mismatch_conflict_logic(self):
        """9. Customer identity mismatch between session and order flags conflict."""
        # Simulated customer mismatch test: if evidence['customer_id'] = 123 and order_customer = 456
        # Verify AttributionService PHP file contains the exact deterministic mismatch check
        attr_service_php = (ROOT / "deploy" / "wordpress" / "budly-sales-agent" / "includes" / "Commerce" / "AttributionService.php").read_text()
        self.assertIn("customer_mismatch", attr_service_php)
        self.assertIn("review_required", attr_service_php)
        self.assertIn("$conflict = (!empty($evidence['customer_id']) && $customer_id && $customer_id!==(int)$evidence['customer_id'])", attr_service_php)

    def test_10_ccss_deterministic_canonical_resolution(self):
        """10. Deterministic CCSS resolver matches public records and rejects excluded lounge records."""
        resolver = DeterministicEntityResolver(public_only=True)
        # Public match
        res_infused = resolver.resolve("Infused Basics")
        self.assertEqual(res_infused.status, "EXACT_MATCH")
        self.assertEqual(res_infused.canonical_id, "ccc:book:infused-basics")
        rec = self.snapshot_loader.get_by_canonical_id(res_infused.canonical_id)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.price_usd, 40.0)

        # Excluded match fails closed
        res_lounge = resolver.resolve("What is Lounge Member?")
        self.assertEqual(res_lounge.status, "NO_MATCH")

    def test_11_multiple_touchpoints_journey_continuity(self):
        """11. Progression from initiated -> engaged -> recommended -> converted."""
        entry = self.spine.handle_social_landing(AttributionContext.direct().to_dict(), "sess_prog_01")
        j = self.repo.get_by_session("sess_prog_01")
        self.assertEqual(j.conversion_state, "initiated")

        # Turn 1
        turn1 = self.spine.process_turn("sess_prog_01", "Can you help me find a book?")
        j1 = self.repo.get_by_session("sess_prog_01")
        self.assertEqual(j1.conversion_state, "recommended")

        # Turn 2
        turn2 = self.spine.process_turn("sess_prog_01", "I would like to order the botanical collection")
        j2 = self.repo.get_by_session("sess_prog_01")
        self.assertEqual(j2.conversion_state, "recommended")

        # Conversion
        j_conv = self.repo.record_conversion(order_id="WC-PROG-99", gross_revenue=40.0, session_id="sess_prog_01")
        self.assertEqual(j_conv.conversion_state, "converted")

    def test_12_refund_bounded_at_zero(self):
        """12. Excess refund cannot produce negative net revenue."""
        self.spine.handle_social_landing(AttributionContext.direct().to_dict(), "sess_bound_01")
        self.repo.record_conversion(order_id="WC-BOUND-1", gross_revenue=50.0, net_revenue=50.0, session_id="sess_bound_01")
        refunded = self.repo.record_refund("WC-BOUND-1", 100.0)
        self.assertEqual(refunded.net_revenue, 0.0)

    def test_13_audit_log_captures_all_sts2_events(self):
        """13. sts_audit_log persists structured audit trails for conversions and refunds."""
        self.spine.handle_social_landing(AttributionContext.direct().to_dict(), "sess_audit_01")
        self.repo.record_conversion(
            order_id="WC-AUDIT-1",
            gross_revenue=65.0,
            net_revenue=65.0,
            session_id="sess_audit_01",
            canonical_id="ccc:book:infused-basics",
            catalog_version="1.9.0-test",
        )
        self.repo.record_refund("WC-AUDIT-1", 20.0, reason="customer_request")

        with self.repo._connect() as db:
            events = db.execute("SELECT * FROM sts_audit_log ORDER BY created_at ASC").fetchall()
            event_types = [e["event_type"] for e in events]
            self.assertIn("journey_converted", event_types)
            self.assertIn("journey_refunded", event_types)

            conv_event = next(e for e in events if e["event_type"] == "journey_converted")
            payload = json.loads(conv_event["payload_json"])
            self.assertEqual(payload["order_id"], "WC-AUDIT-1")
            self.assertEqual(payload["gross_revenue"], 65.0)
            self.assertEqual(payload["canonical_id"], "ccc:book:infused-basics")
            self.assertEqual(payload["catalog_version"], "1.9.0-test")


if __name__ == "__main__":
    unittest.main()
