import tempfile
import unittest
from pathlib import Path

from src.conversation_service import ConversationService


class ConversationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = ConversationService(Path(self.temp.name) / "chat.db")

    def tearDown(self):
        self.temp.cleanup()

    def customer(self, suffix="shopper"):
        return self.service.start(name="Casey", email=f"{suffix}@example.com")["customer_id"]

    def test_route_returns_adaptive_journey_questions(self):
        customer_id = self.customer()
        result = self.service.route(customer_id=customer_id, shopping_goal="I want a home grow course")
        self.assertEqual("books_courses", result["journey"]["id"])
        self.assertGreaterEqual(len(result["journey"]["discovery_questions"]), 3)

    def test_consumer_path_returns_safe_product_card(self):
        customer_id = self.customer("consumer")
        result = self.service.complete(
            customer_id=customer_id,
            shopping_goal="one-time CBD tincture oil",
            journey_answers=["oil", "one-time purchase", "$50 to $75"],
            experience_level="new",
            preferred_format="oil",
            budget_range="$50-$75",
            purchase_timeline="today",
        )
        self.assertEqual("recommendation", result["outcome"])
        self.assertEqual("consumer_wellness", result["journey"]["id"])
        self.assertEqual("therapeutic-oil-tincture-1-time", result["recommendation"]["product_id"])
        self.assertNotIn("treat", result["recommendation"]["summary"].lower())

    def test_wholesale_path_creates_human_handoff(self):
        customer_id = self.customer("buyer")
        result = self.service.complete(
            customer_id=customer_id,
            shopping_goal="bulk white label oil for my retail business",
            journey_answers=["retail", "20 oz", "North Carolina", "next month"],
            experience_level="experienced",
            preferred_format="oil",
            budget_range="unknown",
            purchase_timeline="this_month",
        )
        self.assertEqual("human_handoff", result["outcome"])
        self.assertEqual("wholesale", result["journey"]["id"])
        self.assertTrue(result["escalation_id"])
        self.assertEqual("budlysupport@gmail.com", result["human_sales_email"])

    def test_medical_request_never_returns_product(self):
        customer_id = self.customer("medical")
        result = self.service.complete(
            customer_id=customer_id,
            shopping_goal="What dosage will treat my anxiety?",
            journey_answers=["oil"],
            experience_level="new",
            preferred_format="oil",
            budget_range="",
            purchase_timeline="today",
        )
        self.assertEqual("human_handoff", result["outcome"])
        self.assertNotIn("recommendation", result)


if __name__ == "__main__":
    unittest.main()
