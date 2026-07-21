import tempfile
import unittest
from pathlib import Path

from src.budly_agent import BudlyAgent, Qualification


class BudlyAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.agent = BudlyAgent(Path(self.temp.name) / "test.db")
        self.prospect = self.agent.intake(
            name="Alex",
            email="Alex@Example.com",
            source="QR campaign",
            platform="Instagram",
            niche="wellness education",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_email_is_normalized_and_duplicate_is_updated(self):
        updated = self.agent.intake(
            name="Alex Updated",
            email=" alex@example.com ",
            source="referral",
            platform="TikTok",
            niche="education",
        )
        self.assertEqual(self.prospect["id"], updated["id"])
        self.assertEqual("Alex Updated", updated["name"])

    def test_invalid_email_is_rejected(self):
        with self.assertRaises(ValueError):
            self.agent.intake(name="B", email="bad", source="x", platform="x", niche="x")

    def test_high_score_invites_to_apply(self):
        result = self.agent.qualify(self.prospect["id"], Qualification(5, 5, 5, 5, 5, 5))
        self.assertEqual(100, result["score"])
        self.assertEqual("invite_to_apply", result["status"])

    def test_mid_score_nurtures(self):
        result = self.agent.qualify(self.prospect["id"], Qualification(3, 3, 3, 3, 3, 3))
        self.assertEqual(60, result["score"])
        self.assertEqual("nurture", result["status"])

    def test_low_score_monitors(self):
        result = self.agent.qualify(self.prospect["id"], Qualification(1, 1, 1, 1, 1, 1))
        self.assertEqual(20, result["score"])
        self.assertEqual("monitor", result["status"])

    def test_risky_message_escalates(self):
        result = self.agent.local_response(self.prospect, "I have a missing payout and commission dispute")
        refreshed = self.agent.get_prospect(self.prospect["id"])
        self.assertIn("human review", result)
        self.assertEqual("human_review", refreshed["status"])

    def test_factor_range_is_validated(self):
        with self.assertRaises(ValueError):
            self.agent.qualify(self.prospect["id"], Qualification(6, 1, 1, 1, 1, 1))


if __name__ == "__main__":
    unittest.main()
