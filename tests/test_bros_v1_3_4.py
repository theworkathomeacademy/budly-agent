import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.sales_agent import APPLICATION_VERSION, SCHEMA_VERSION, Discovery, OpportunitySignals, SalesAgent
from src.conversation_service import ConversationService


class BrosV134Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "sales.db"
        self.agent = SalesAgent(self.db)
        self.customer = self.agent.intake(name="Jordan", email="jordan@example.com")

    def tearDown(self):
        self.temp.cleanup()

    def discover(self, goal="topical body butter", preferred="topical"):
        self.agent.record_discovery(
            self.customer["id"], Discovery(goal, "new", preferred, "", "soon")
        )

    def test_version_reporting_and_active_rule_versions(self):
        diagnostics = self.agent.diagnostics()
        self.assertEqual("1.3.4", APPLICATION_VERSION)
        self.assertEqual("1.2.0", SCHEMA_VERSION)
        self.assertEqual("qualification-1.3.4.1", diagnostics["rule_versions"]["qualification"])
        self.assertEqual(7, len(diagnostics["rule_versions"]))

    def test_configuration_selection_is_idempotent(self):
        SalesAgent(self.db)
        db = sqlite3.connect(self.db)
        try:
            count = db.execute("SELECT COUNT(*) FROM active_configurations").fetchone()[0]
        finally:
            db.close()
        self.assertEqual(7, count)

    def test_qualification_preserves_governed_evidence(self):
        self.discover()
        self.agent.qualify(self.customer["id"], OpportunitySignals(5, 5, 5, 5))
        evidence = self.agent.decision_evidence(self.customer["id"])[0]
        self.assertEqual("qualification", evidence["decision_type"])
        self.assertEqual("qualification-1.3.4.1", evidence["rule_version"])
        self.assertEqual("qualified", evidence["outcome"])
        self.assertEqual("topical body butter", evidence["objective"])
        self.assertEqual(100, sum(json.loads(evidence["inputs_json"])["weights"].values()))

    def test_recommendation_preserves_allowlist_exclusions_and_confidence(self):
        self.discover()
        product = self.agent.recommend(self.customer["id"])
        evidence = self.agent.decision_evidence(self.customer["id"])[0]
        self.assertIsNotNone(product)
        self.assertEqual(product["id"], evidence["selected_product_id"])
        exclusions = json.loads(evidence["excluded_products_json"])
        self.assertTrue(any(x["reason"] == "human_sales_required" for x in exclusions))
        self.assertIn(evidence["confidence"], {"low", "medium", "high"})

    def test_safe_no_match_is_recorded_and_never_fabricates(self):
        self.discover("something absent from catalog", "unknown")
        self.assertIsNone(self.agent.recommend(self.customer["id"]))
        evidence = self.agent.decision_evidence(self.customer["id"])[0]
        self.assertEqual("no_match", evidence["outcome"])
        self.assertIsNone(evidence["selected_product_id"])
        self.assertEqual("request_clarification_or_human_help", evidence["resulting_action"])

    def test_escalation_preserves_evidence_and_audit_link(self):
        escalation = self.agent.escalate(self.customer["id"], "medical", "help diagnose this")
        evidence = self.agent.decision_evidence(self.customer["id"])[0]
        self.assertEqual(escalation, evidence["escalation_id"])
        self.assertEqual("human_review", evidence["outcome"])
        db = sqlite3.connect(self.db)
        try:
            payload = json.loads(db.execute(
                "SELECT payload FROM audit_events WHERE event_type='decision.escalation'"
            ).fetchone()[0])
        finally:
            db.close()
        self.assertEqual(evidence["id"], payload["decision_id"])

    def test_conversation_no_match_records_decision(self):
        response = ConversationService(self.db).complete(
            customer_id=self.customer["id"], shopping_goal="unlisted artifact",
            journey_answers=[], experience_level="unknown", preferred_format="unknown",
            budget_range="", purchase_timeline="",
        )
        self.assertEqual("no_match", response["outcome"])
        self.assertEqual("no_match", self.agent.decision_evidence(self.customer["id"])[-1]["outcome"])

    def test_decision_evidence_has_no_public_mutation_api(self):
        self.discover()
        self.agent.recommend(self.customer["id"])
        self.assertFalse(hasattr(self.agent, "delete_decision_evidence"))
        self.assertFalse(hasattr(self.agent, "update_decision_evidence"))


class WordpressV134ContractTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_wordpress_version_schema_and_decision_tables(self):
        plugin = (self.ROOT / "deploy/wordpress/budly-sales-agent/budly-sales-agent.php").read_text(encoding="utf-8")
        config = (self.ROOT / "deploy/wordpress/budly-sales-agent/includes/SecureMemory/Config.php").read_text(encoding="utf-8")
        migration = (self.ROOT / "deploy/wordpress/budly-sales-agent/includes/SecureMemory/Database/Migrator.php").read_text(encoding="utf-8")
        self.assertIn("Version: 1.3.4", plugin)
        self.assertIn("SCHEMA_VERSION = '1.2.0'", config)
        self.assertIn("decision_evidence", migration)
        self.assertIn("rule_configurations", migration)
        self.assertIn("qualification-1.3.4.1", migration)
        self.assertIn("catalog-allowlist-2026-07-16", migration)

    def test_admin_visibility_includes_versions_and_decisions(self):
        service = (self.ROOT / "deploy/wordpress/budly-sales-agent/includes/SecureMemory/Admin/AdminService.php").read_text(encoding="utf-8")
        repository = (self.ROOT / "deploy/wordpress/budly-sales-agent/includes/SecureMemory/Admin/AdminRepository.php").read_text(encoding="utf-8")
        self.assertIn("application_version", service)
        self.assertIn("active_configurations", service)
        self.assertIn("recent_decisions", repository)
        routes = (self.ROOT / "deploy/wordpress/budly-sales-agent/includes/SecureMemory/Api/Routes.php").read_text(encoding="utf-8")
        self.assertIn("/admin/decisions", routes)
        self.assertIn("admin_permission()", routes)


if __name__ == "__main__":
    unittest.main()
