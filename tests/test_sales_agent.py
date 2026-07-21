import json
import tempfile
import unittest
from pathlib import Path

from src.sales_agent import Discovery, OpportunitySignals, SalesAgent


class SalesAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.agent = SalesAgent(Path(self.temp.name) / "sales.db")
        self.customer = self.agent.intake(name="Taylor", email="Taylor@Example.com", source="website")

    def tearDown(self):
        self.temp.cleanup()

    def discovery(self):
        return Discovery("learn about wellness products", "new", "digital", "$25-$50", "this month")

    def test_intake_normalizes_and_deduplicates(self):
        updated = self.agent.intake(name="Taylor Updated", email=" taylor@example.com ", source="referral")
        self.assertEqual(self.customer["id"], updated["id"])
        self.assertEqual("Taylor Updated", updated["name"])

    def test_discovery_is_stored(self):
        result = self.agent.record_discovery(self.customer["id"], self.discovery())
        self.assertEqual("discovery", result["stage"])
        self.assertEqual("new", json.loads(result["discovery_json"])["experience_level"])

    def test_invalid_experience_is_rejected(self):
        with self.assertRaises(ValueError):
            self.agent.record_discovery(self.customer["id"], Discovery("goal", "expert-ish", "", "", ""))

    def test_high_score_qualifies(self):
        result = self.agent.qualify(self.customer["id"], OpportunitySignals(5, 5, 5, 5))
        self.assertEqual(100, result["score"])
        self.assertEqual("qualified", result["stage"])

    def test_medium_score_nurtures(self):
        result = self.agent.qualify(self.customer["id"], OpportunitySignals(3, 3, 3, 3))
        self.assertEqual(60, result["score"])
        self.assertEqual("nurture", result["stage"])

    def test_low_score_routes_low_intent(self):
        result = self.agent.qualify(self.customer["id"], OpportunitySignals(1, 1, 1, 1))
        self.assertEqual(20, result["score"])
        self.assertEqual("low_intent", result["stage"])

    def test_empty_catalog_does_not_invent_recommendation(self):
        self.agent.catalog = {"products": []}
        self.agent.record_discovery(self.customer["id"], self.discovery())
        self.assertIsNone(self.agent.recommend(self.customer["id"]))

    def test_medical_request_escalates(self):
        response = self.agent.local_response(self.customer, "What dosage will treat my anxiety?")
        refreshed = self.agent.get_customer(self.customer["id"])
        self.assertIn("human review", response)
        self.assertEqual("human_review", refreshed["stage"])

    def test_unconfigured_catalog_response_is_transparent(self):
        self.agent.catalog = {"products": []}
        response = self.agent.local_response(self.customer, "What should I buy?")
        self.assertIn("catalog has not been loaded", response)

    def test_verified_catalog_can_match_education_product(self):
        self.agent.record_discovery(
            self.customer["id"],
            Discovery("beginner cooking infusion education", "new", "digital", "", "this month"),
        )
        product = self.agent.recommend(self.customer["id"])
        self.assertIsNotNone(product)
        self.assertEqual("infused-basics", product["id"])

    def test_wholesale_products_require_human_sales(self):
        self.agent.record_discovery(
            self.customer["id"],
            Discovery("bulk wholesale white label oil", "experienced", "oil", "", "this month"),
        )
        product = self.agent.recommend(self.customer["id"])
        self.assertNotEqual("wholesale", product.get("category") if product else None)

    def test_invalid_signal_range_is_rejected(self):
        with self.assertRaises(ValueError):
            self.agent.qualify(self.customer["id"], OpportunitySignals(6, 1, 1, 1))

    def test_all_public_products_have_live_facts(self):
        self.assertEqual(32, len(self.agent.catalog["products"]))
        for product in self.agent.catalog["products"]:
            self.assertIsNotNone(product.get("price_display"), product["id"])
            self.assertIn("in_stock", product, product["id"])
            self.assertIn("safe_summary", product, product["id"])
            self.assertIn("exclusions", product, product["id"])

    def test_hidden_store_records_are_not_in_public_catalog(self):
        public_ids = {product["id"] for product in self.agent.catalog["products"]}
        excluded = set(self.agent.product_facts["unlisted_store_records_excluded"])
        self.assertTrue(public_ids.isdisjoint(excluded))

    def test_five_journey_routing(self):
        cases = {
            "consumer_wellness": "compare a CBD tincture and body butter",
            "culinary": "I need a cooking oil size",
            "books_courses": "I want a home grow course",
            "nft_memberships": "I want an NFT membership tier",
            "wholesale": "bulk white label products for my business",
        }
        for journey_id, goal in cases.items():
            with self.subTest(journey_id=journey_id):
                customer = self.agent.intake(
                    name=journey_id,
                    email=f"{journey_id}@example.com",
                    source="test",
                )
                self.agent.record_discovery(
                    customer["id"], Discovery(goal, "unknown", "", "", ""),
                )
                self.assertEqual(journey_id, self.agent.select_journey(customer["id"])["id"])

    def test_recommendation_card_uses_sales_safe_copy(self):
        self.agent.record_discovery(
            self.customer["id"],
            Discovery("CBD tincture oil one-time", "new", "oil", "$50-$75", "now"),
        )
        card = self.agent.recommendation_card(self.customer["id"])
        self.assertIsNotNone(card)
        text = json.dumps({"summary": card["summary"], "features": card["factual_features"]}).lower()
        self.assertNotIn("treat", text)
        self.assertNotIn("cure", text)
        self.assertEqual("therapeutic-oil-tincture-1-time", card["product_id"])
        self.assertIn("product_url", card)

    def test_subscription_cancellation_policy(self):
        response = self.agent.local_response(self.customer, "How do I cancel my subscription?")
        self.assertIn("account profile", response)
        self.assertIn("budlysupport@gmail.com", response)
        self.assertIn("before the next renewal", response)

    def test_membership_refund_policy_and_usage_rule(self):
        response = self.agent.local_response(self.customer, "Can I cancel my membership for a refund?")
        self.assertIn("7 days", response)
        self.assertIn("transaction finishes processing", response)
        self.assertIn("membership discount", response)
        self.assertIn("disqualifies", response)

    def test_support_response_target(self):
        response = self.agent.local_response(self.customer, "What is your support response time?")
        self.assertIn("3 business days", response)


if __name__ == "__main__":
    unittest.main()
