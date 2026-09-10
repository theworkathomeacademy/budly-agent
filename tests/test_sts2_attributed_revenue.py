import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy/wordpress/budly-sales-agent"


class STS2AttributedRevenueTests(unittest.TestCase):
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
        self.assertIn("$valid_link", self.attribution)
        self.assertIn("$valid_link?'attributed':'unattributed'", self.attribution)
        self.assertIn("verified_commerce_correlation", self.attribution)

    def test_conversion_requires_woocommerce_revenue_evidence(self):
        self.assertIn("payment_completed", self.adapter)
        self.assertIn("order_completed", self.adapter)
        self.assertIn("processing','completed", self.adapter)
        self.assertIn("commerce_correlation_id", self.adapter)
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
