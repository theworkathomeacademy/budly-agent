import unittest
from pathlib import Path
from src.sales_agent import SalesAgent, Discovery, APPLICATION_VERSION, SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy" / "wordpress" / "budly-sales-agent"

class ConversationIntelligenceV17Tests(unittest.TestCase):
    def setUp(self):
        self.agent = SalesAgent()

    def test_version_declarations_v17(self):
        self.assertEqual(APPLICATION_VERSION, "1.7.0")
        self.assertEqual(SCHEMA_VERSION, "1.5.0")

    def test_phase1_conversation_state_machine(self):
        customer = self.agent.intake(name="Alice", email="alice@example.com")
        stage = self.agent.canonical_lifecycle_stage(customer)
        self.assertEqual(stage, "Visitor")

    def test_phase2_discovery_intelligence(self):
        discovery = Discovery("tincture for sleep", "new", "tincture", "$50", "today")
        discovery.validate()
        self.assertEqual(discovery.shopping_goal, "tincture for sleep")

    def test_phase3_adaptive_question_selection(self):
        known = {"shopping_goal": "CBD oil"}
        question = self.agent.select_next_adaptive_question(known)
        self.assertIsNotNone(question)
        self.assertEqual(question["attribute"], "experience_level")
        self.assertGreater(question["information_value"], 0.0)

    def test_phase4_explainable_recommendation_rationale(self):
        product = {"name": "Restful Sleep Tincture"}
        discovery = Discovery("sleep help", "new", "tincture", "$40", "today")
        rationale = self.agent.explain_recommendation(product, discovery)
        self.assertIn("observation", rationale)
        self.assertIn("reasoning", rationale)
        self.assertIn("recommendation", rationale)
        self.assertIn("explanation", rationale)
        self.assertEqual(rationale["recommendation"], "Restful Sleep Tincture")

    def test_phase5_relationship_lifecycle_mapping(self):
        customer_new = {"stage": "new", "score": 10}
        customer_qualified = {"stage": "qualified", "score": 90}
        customer_won = {"stage": "closed_won", "score": 100}
        self.assertEqual(self.agent.canonical_lifecycle_stage(customer_new), "Visitor")
        self.assertEqual(self.agent.canonical_lifecycle_stage(customer_qualified), "Explorer")
        self.assertEqual(self.agent.canonical_lifecycle_stage(customer_won), "Member")

    def test_phase6_canonical_lifecycle_stages(self):
        stages = ["Visitor", "Explorer", "Member", "Returning Member", "Community Member", "Advocate", "Leader"]
        self.assertEqual(len(stages), 7)
        self.assertIn("Visitor", stages)
        self.assertIn("Leader", stages)

    def test_phase7_wordpress_v17_files_exist(self):
        manager_file = PLUGIN / "includes" / "Conversation" / "ConversationManager.php"
        lifecycle_file = PLUGIN / "includes" / "Lifecycle" / "LifecycleEngine.php"
        self.assertTrue(manager_file.is_file())
        self.assertTrue(lifecycle_file.is_file())

    def test_phase8_secure_memory_schema_150(self):
        config = (PLUGIN / "includes" / "SecureMemory" / "Config.php").read_text(encoding="utf-8")
        migrator = (PLUGIN / "includes" / "SecureMemory" / "Database" / "Migrator.php").read_text(encoding="utf-8")
        self.assertIn("SCHEMA_VERSION = '1.5.0'", config)
        self.assertIn("conversation_state", migrator)
        self.assertIn("conversation_pattern_history", migrator)
        self.assertIn("relationship_health", migrator)
        self.assertIn("member_journey", migrator)

    def test_phase9_commerce_attribution_integration(self):
        migrator = (PLUGIN / "includes" / "SecureMemory" / "Database" / "Migrator.php").read_text(encoding="utf-8")
        self.assertIn("commerce_attribution", migrator)
        self.assertIn("conversation_intelligence", migrator)

    def test_phase10_admin_rest_routes(self):
        routes = (PLUGIN / "includes" / "SecureMemory" / "Api" / "Routes.php").read_text(encoding="utf-8")
        self.assertIn("/admin/conversation/health", routes)
        self.assertIn("/admin/lifecycle", routes)
        self.assertIn("/discovery", routes)
        self.assertIn("/conversation-state", routes)
        self.assertIn("/relationship", routes)

if __name__ == "__main__":
    unittest.main()
