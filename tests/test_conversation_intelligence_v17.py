import unittest
from pathlib import Path
from src.sales_agent import SalesAgent, Discovery, APPLICATION_VERSION, SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy" / "wordpress" / "budly-sales-agent"


class ConversationIntelligenceV17Tests(unittest.TestCase):
    def setUp(self):
        self.agent = SalesAgent()

    def test_version_declarations_v17(self):
        self.assertEqual(APPLICATION_VERSION, "1.7.1")
        self.assertEqual(SCHEMA_VERSION, "1.5.0")

    def test_canonical_patterns_10_of_10_coverage(self):
        patterns = self.agent.canonical_patterns()
        expected_keys = {
            "first_visit",
            "returning_member",
            "educational_conversation",
            "product_recommendation",
            "comparison",
            "complaint",
            "affiliate_inquiry",
            "wholesale_inquiry",
            "human_handoff",
            "conversation_recovery",
        }
        self.assertEqual(set(patterns.keys()), expected_keys)
        self.assertEqual(len(patterns), 10)

        # Test pattern selection logic for all 10 scenarios
        ws = self.agent.select_pattern("I need a wholesale bulk order")
        self.assertEqual(ws["name"], "wholesale_inquiry")

        aff = self.agent.select_pattern("Tell me about your affiliate referral program")
        self.assertEqual(aff["name"], "affiliate_inquiry")

        comp = self.agent.select_pattern("I have a complaint about a damaged item")
        self.assertEqual(comp["name"], "complaint")

        hh = self.agent.select_pattern("Can I talk to a human support agent?")
        self.assertEqual(hh["name"], "human_handoff")

        cmp = self.agent.select_pattern("Compare CBD tinctures vs gummies")
        self.assertEqual(cmp["name"], "comparison")

        edu = self.agent.select_pattern("How to choose the right CBD dosage and learn more?")
        self.assertEqual(edu["name"], "educational_conversation")

        ret = self.agent.select_pattern("Hi again", {"is_returning_member": True})
        self.assertEqual(ret["name"], "returning_member")

        recov = self.agent.select_pattern("Where were we?", {"needs_recovery": True})
        self.assertEqual(recov["name"], "conversation_recovery")

        rec = self.agent.select_pattern("What do you suggest?", {"ready_for_recommendation": True})
        self.assertEqual(rec["name"], "product_recommendation")

        fv = self.agent.select_pattern("Hello, I am looking around")
        self.assertEqual(fv["name"], "first_visit")

    def test_lifecycle_stage_transitions_and_validation(self):
        stages = ["Visitor", "Explorer", "Member", "Returning Member", "Community Member", "Advocate", "Leader"]
        self.assertEqual(len(stages), 7)

        # Behavioral mapping test
        c_visitor = {"stage": "new", "score": 10}
        c_explorer = {"stage": "qualified", "score": 85}
        c_member = {"stage": "closed_won", "score": 100}

        self.assertEqual(self.agent.canonical_lifecycle_stage(c_visitor), "Visitor")
        self.assertEqual(self.agent.canonical_lifecycle_stage(c_explorer), "Explorer")
        self.assertEqual(self.agent.canonical_lifecycle_stage(c_member), "Member")

    def test_adaptive_question_engine_dynamics(self):
        # 1. Known attributes skip answered questions
        known_goal = {"shopping_goal": "CBD oil"}
        q1 = self.agent.select_next_adaptive_question(known_goal)
        self.assertIsNotNone(q1)
        self.assertEqual(q1["attribute"], "experience_level")

        # 2. Journey priority shifting
        q_budget = self.agent.select_next_adaptive_question({}, journey="budget")
        self.assertEqual(q_budget["attribute"], "budget_range")

        q_wholesale = self.agent.select_next_adaptive_question({}, journey="wholesale")
        self.assertEqual(q_wholesale["attribute"], "shopping_goal")

        # 3. Stop asking when confidence is high (insufficient information value)
        q_high_conf = self.agent.select_next_adaptive_question({}, confidence=0.95)
        self.assertIsNone(q_high_conf)

        # 4. Stop asking when all fields known
        all_known = {
            "shopping_goal": "CBD",
            "experience_level": "new",
            "preferred_format": "tincture",
            "budget_range": "$50",
            "purchase_timeline": "today",
        }
        q_all = self.agent.select_next_adaptive_question(all_known)
        self.assertIsNone(q_all)

    def test_recommendation_rationale_explainability(self):
        product = {"name": "Calming Sleep Tincture"}
        discovery = Discovery("sleep support", "new", "tincture", "$40", "today")
        rationale = self.agent.explain_recommendation(product, discovery)

        self.assertIn("observation", rationale)
        self.assertIn("reasoning", rationale)
        self.assertIn("recommendation", rationale)
        self.assertIn("explanation", rationale)
        self.assertIn("confirmation_prompt", rationale)
        self.assertIn("sleep support", rationale["observation"])
        self.assertIn("tincture", rationale["explanation"])
        # Ensure no private chain-of-thought is present
        self.assertNotIn("chain_of_thought", rationale)
        self.assertNotIn("prompt_tokens", rationale)

    def test_no_unauthorized_autonomous_outreach(self):
        # Verify no automated email marketing or scheduling calls exist in conversation_service
        service_text = (ROOT / "src" / "conversation_service.py").read_text(encoding="utf-8")
        self.assertNotIn("send_marketing_email", service_text)
        self.assertNotIn("schedule_campaign", service_text)
        self.assertNotIn("auto_subscribe", service_text)

    def test_wordpress_v17_architecture(self):
        manager_text = (PLUGIN / "includes" / "Conversation" / "ConversationManager.php").read_text(encoding="utf-8")
        lifecycle_text = (PLUGIN / "includes" / "Lifecycle" / "LifecycleEngine.php").read_text(encoding="utf-8")

        self.assertIn("class ConversationManager", manager_text)
        self.assertIn("class LifecycleEngine", lifecycle_text)
        self.assertIn("STAGE_VISITOR = 'Visitor'", lifecycle_text)
        self.assertIn("STAGE_LEADER = 'Leader'", lifecycle_text)
        self.assertIn("select_pattern", manager_text)
        self.assertIn("select_next_adaptive_question", manager_text)

    def test_secure_memory_schema_150(self):
        config = (PLUGIN / "includes" / "SecureMemory" / "Config.php").read_text(encoding="utf-8")
        migrator = (PLUGIN / "includes" / "SecureMemory" / "Database" / "Migrator.php").read_text(encoding="utf-8")
        self.assertIn("SCHEMA_VERSION = '1.5.0'", config)
        self.assertIn("conversation_state", migrator)
        self.assertIn("conversation_pattern_history", migrator)
        self.assertIn("relationship_health", migrator)
        self.assertIn("member_journey", migrator)

    def test_admin_rest_routes(self):
        routes = (PLUGIN / "includes" / "SecureMemory" / "Api" / "Routes.php").read_text(encoding="utf-8")
        self.assertIn("/admin/conversation/health", routes)
        self.assertIn("/admin/lifecycle", routes)
        self.assertIn("/discovery", routes)
        self.assertIn("/conversation-state", routes)
        self.assertIn("/relationship", routes)
        self.assertIn("SessionGuard::verified_customer_id", routes)


if __name__ == "__main__":
    unittest.main()
