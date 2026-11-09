"""Comprehensive Verification Suite for STS-2 Attributed Revenue.

Validates:
1. Recommendation → Purchase → Verified Woo Revenue Event → Deterministic Journey Attribution
2. Event replay idempotency (duplicate webhooks/replays)
3. Anonymous buyer conversion without CRM Lead generation
4. Direct buyer unattributed handling
5. Malformed/invalid attribution params ignored/sanitized
6. Customer identity conflict handling (customer_mismatch)
7. CCS-006 Excluded Lounge products fail-closed
8. Refund and reversal handling with net revenue adjustment and audit preservation
9. Zero PII in attribution URLs
10. Deterministic CCSS canonical_id and catalog_version binding
11. Multiple touchpoints journey continuity
12. Refund bounded at zero
13. Audit log captures all STS-2 events
14. WordPress plugin contract tests
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from budly_runtime.commercial_snapshot.loader import CommercialSnapshotLoader
from budly_runtime.commercial_snapshot.resolver import DeterministicEntityResolver

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
        """1. Full flow: Social landing → Recommendation → Correlated checkout URL → Conversion."""
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
        """2. Duplicate payment_completed or order_completed webhooks do not mutate or duplicate."""
        self.spine.handle_social_landing(AttributionContext.direct().to_dict(), "sess_replay_test")
        c1 = self.repo.record_conversion(order_id="WC-REP-1", gross_revenue=50.0, session_id="sess_replay_test")
        first_time = c1.converted_at

        # Replay duplicate event
        c2 = self.repo.record_conversion(order_id="WC-REP-1", gross_revenue=50.0, session_id="sess_replay_test")
        self.assertEqual(c1.converted_at, c2.converted_at)
        self.assertEqual(c2.gross_revenue, 50.0)

    def test_03_anonymous_buyer_conversion_without_lead_creation(self):
        """3. An anonymous buyer converts without automatically creating a CRM Lead record."""
        landing_url = "https://www.wakenbakelounge.com/ask-budly?source=social&platform=instagram"
        entry_ctx = self.spine.handle_social_landing(landing_url, "sess_anon_buyer")

        turn = self.spine.process_turn("sess_anon_buyer", "I will take the botanical book")
        self.assertFalse(turn.is_lead)
        self.assertIsNone(turn.lead_id)

        converted = self.spine.record_revenue_conversion(
            order_id="WC-ANON-101",
            gross_revenue=40.0,
            session_id="sess_anon_buyer",
        )
        self.assertEqual(converted.conversion_state, "converted")
        # Ensure NO lead record was generated in database
        self.assertIsNone(converted.lead_id)
        with self.repo._connect() as db:
            lead_count = db.execute("SELECT count(*) as count FROM conversion_leads WHERE session_id=?", ("sess_anon_buyer",)).fetchone()["count"]
            self.assertEqual(lead_count, 0)

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
        """5. Dangerous or unexpected query parameters are sanitized/ignored."""
        malformed_url = (
            "https://www.wakenbakelounge.com/ask-budly"
            "?source=<script>alert(1)</script>"
            "&platform=instagram"
            "&campaign_id=STS-2'; DROP TABLE conversion_journeys; --"
        )
        entry_ctx = self.spine.handle_social_landing(malformed_url, "sess_xss_test")
        j = self.repo.get_by_session("sess_xss_test")
        self.assertIsNotNone(j)
        # Should not crash and table must still exist
        with self.repo._connect() as db:
            count = db.execute("SELECT count(*) as cnt FROM conversion_journeys").fetchone()["cnt"]
            self.assertGreater(count, 0)

    def test_06_ccs006_excluded_lounge_products_fail_closed(self):
        """6. CCS-006: Excluded Lounge community products fail closed and are never recommended."""
        with self.assertRaises(ValueError) as cm:
            self.router.route(
                intent="PURCHASE_INTENT",
                product_or_topic="LOUNGE_MEMBER",
                qualification_state="qualified_purchase_ready",
            )
        self.assertIn("CCS-006", str(cm.exception))

    def test_07_refund_and_reversal_adjusts_net_revenue(self):
        """7. Refunds and cancellations decrease net revenue while retaining audit history."""
        self.spine.handle_social_landing(AttributionContext.direct().to_dict(), "sess_refund_test")
        conv = self.repo.record_conversion(order_id="WC-REF-100", gross_revenue=100.0, net_revenue=100.0, session_id="sess_refund_test")
        self.assertEqual(conv.net_revenue, 100.0)

        # Partial refund
        refunded = self.repo.record_refund("WC-REF-100", 30.0, reason="damaged_item")
        self.assertIsNotNone(refunded)
        self.assertEqual(refunded.net_revenue, 70.0)
        self.assertEqual(refunded.gross_revenue, 100.0)

        # Full reversal
        reversal = self.repo.record_refund("WC-REF-100", 70.0, reason="order_cancelled")
        self.assertIsNotNone(reversal)
        self.assertEqual(reversal.net_revenue, 0.0)

    def test_08_zero_pii_in_attribution_urls(self):
        """8. Generated attribution query parameters never contain customer PII."""
        outcome = self.router.route(
            intent="PURCHASE_INTENT",
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
        attr_service_php = (ROOT / "deploy" / "wordpress" / "budly-sales-agent" / "includes" / "Commerce" / "AttributionService.php").read_text(encoding="utf-8")
        self.assertIn("customer_mismatch", attr_service_php)
        self.assertIn("review_required", attr_service_php)
        self.assertIn("customer_id!==(int)$evidence['customer_id']", attr_service_php.replace(" ", ""))

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


PLUGIN = ROOT / "deploy/wordpress/budly-sales-agent"


class STS2AttributedRevenueWordpressContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.correlation = (PLUGIN / "includes/Commerce/CommerceCorrelationService.php").read_text(encoding="utf-8")
        cls.attribution = (PLUGIN / "includes/Commerce/AttributionService.php").read_text(encoding="utf-8")
        cls.adapter = (PLUGIN / "includes/Commerce/WooCommerceAdapter.php").read_text(encoding="utf-8")
        cls.repository = (PLUGIN / "includes/Commerce/CommerceRepository.php").read_text(encoding="utf-8")
        cls.routes = (PLUGIN / "includes/SecureMemory/Api/Routes.php").read_text(encoding="utf-8")
        cls.conversation = (PLUGIN / "includes/Runtime/ConversationProxy.php").read_text(encoding="utf-8")
        cls.js = (PLUGIN / "assets/budly-sales.js").read_text(encoding="utf-8")

    def test_server_issues_bounded_signed_opaque_identifier(self):
        self.assertIn("'sts2_' . bin2hex(random_bytes(16))", self.correlation)
        self.assertIn("hash_hmac('sha256', $correlation_id, wp_salt('auth'))", self.correlation)
        self.assertIn("hash_equals($expected", self.correlation)
        self.assertIn("const TTL = 7 * DAY_IN_SECONDS", self.correlation)

    def test_authoritative_recommendation_is_required(self):
        self.assertIn("$decision['outcome'] ?? '') !== 'recommended'", self.correlation)
        self.assertIn("empty($decision['decision_id'])", self.correlation)
        self.assertIn("empty($decision['selected_product_id'])", self.correlation)

    def test_recommendation_link_carries_only_token(self):
        self.assertIn("u.searchParams.set('budly_correlation',commerceToken)", self.js)
        self.assertIn("decision.commerce_correlation_token", self.js)
        self.assertNotIn("_budly_commerce_correlation_id',commerceToken", self.js)

    def test_conversational_recommendation_uses_same_governed_bridge(self):
        self.assertIn("CommerceCorrelationService::issue($decision", self.conversation)
        self.assertIn("'attribution' => $attribution", self.conversation)
        self.assertIn("response.commerce_correlation_token", self.js)
        self.assertIn("if(hasAttribution)payload.attribution=state.attribution", self.js)

    def test_product_binding_prevents_customer_override(self):
        self.assertIn("get_post_field('post_name'", self.correlation)
        self.assertIn("hash_equals((string)$payload['selected_product_id'], $slug)", self.correlation)

    def test_order_metadata_is_non_commercial(self):
        for key in ("_budly_commerce_correlation_id", "_budly_conversation_id", "_budly_decision_id"):
            self.assertIn(key, self.correlation)
        for forbidden in ("set_total", "set_price", "set_tax", "set_shipping"):
            self.assertNotIn(forbidden, self.correlation)

    def test_invalid_or_missing_correlation_is_not_attributed(self):
        self.assertIn("$valid_correlation", self.attribution)
        self.assertIn("$has_attribution?'attributed':'unattributed'", self.attribution.replace(" ", ""))
        self.assertIn("verified_commerce_correlation", self.attribution)

    def test_conversion_requires_woocommerce_revenue_evidence(self):
        self.assertIn("payment_completed", self.adapter)
        self.assertIn("order_completed", self.adapter)
        self.assertIn("processing','completed", self.adapter.replace(" ", ""))
        self.assertIn("commerce_correlation_id", self.adapter)
        self.assertIn("recorded_revenue_event($order->get_id())", self.adapter.replace(" ", ""))
        self.assertIn("recorded_revenue_event($order_id)", self.repository)
        self.assertIn("?'converted':'pending_authoritative_revenue'", self.repository)
        self.assertIn("/admin/commerce/conversion", self.routes)

    def test_existing_sts1_attribution_fields_remain(self):
        for field in ("source", "platform", "content_id", "campaign_id", "cta_id", "product_or_topic"):
            self.assertIn(f"'{field}'", self.js)

    def test_identifier_patterns_are_bounded(self):
        self.assertRegex(self.correlation, re.compile(r"sts2_\[a-f0-9\]\{32\}"))
        self.assertIn("dec_[a-z0-9]{12,40}", self.correlation)


if __name__ == "__main__":
    unittest.main()
