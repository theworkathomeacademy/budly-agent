import json
import unittest
from pathlib import Path

from src.budly_runtime.production_knowledge import ApprovedRepositoryKnowledgeAdapter
from src.budly_runtime.tool_gateway import AdapterContext


ROOT = Path(__file__).resolve().parents[1]


class G9DIntegrationContractTests(unittest.TestCase):
    def adapter(self):
        return ApprovedRepositoryKnowledgeAdapter(
            ROOT / "config/policies.json",
            ROOT / "config/products.json",
            ROOT / "config/budly_runtime/education-corpus-v0.1.json",
            ROOT / "config/budly_runtime/commercial-knowledge-v1.0.json",
            ROOT / "config/budly_runtime/affiliate-public-knowledge-g9d-v1.json",
        )

    def test_public_affiliate_truth_is_retrievable_and_public_only(self):
        adapter = self.adapter()
        for question in (
            "What is your affiliate program?",
            "How much can affiliates earn?",
            "Do you have recurring commissions?",
            "Are applications open?",
        ):
            items = adapter.retrieve(AdapterContext(question, "affiliate_program", 5, frozenset({"Public"}), "g9d", "g9d", "website_chat"))
            self.assertTrue(items, question)
            self.assertTrue(all(item["classification"] == "Public" for item in items))

    def test_public_affiliate_file_contains_no_invitation_token(self):
        raw = (ROOT / "config/budly_runtime/affiliate-public-knowledge-g9d-v1.json").read_text(encoding="utf-8")
        self.assertNotIn("G9DREF", raw)
        self.assertNotIn("invitation_token", raw)

    def test_n8n_workflow_is_disabled_and_has_no_network_trigger(self):
        workflow = json.loads((ROOT / "integration/g9d/G9D-Woo-Compatible-Synthetic-Event.json").read_text(encoding="utf-8"))[0]
        self.assertFalse(workflow["active"])
        self.assertEqual(workflow["meta"], {"production": False, "scope": "G9D"})
        self.assertEqual({node["type"] for node in workflow["nodes"]}, {"n8n-nodes-base.manualTrigger", "n8n-nodes-base.code"})
        code = next(node["parameters"]["jsCode"] for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.code")
        self.assertIn("bros.revenue_event.v1", code)
        self.assertIn("TEST_SYNTHETIC_NON_PRODUCTION_PERSON", code)

    def test_sql_contract_keeps_production_flags_off_and_audit_immutable(self):
        round_trip = (ROOT / "integration/g9d/02_synthetic_round_trip.sql").read_text(encoding="utf-8")
        rls = (ROOT / "integration/g9d/03_rls_role_proof.sql").read_text(encoding="utf-8")
        foundation = (ROOT / "migrations/affiliate_mvp/001_affiliate_mvp_foundation.sql").read_text(encoding="utf-8")
        self.assertIn("from bros_affiliate.feature_flags where enabled", round_trip)
        self.assertIn("PRODUCTION_FLAGS_CHANGED", round_trip)
        self.assertIn("AFFILIATE_IMMUTABLE_ROW", foundation)
        self.assertIn("G9D_RLS_ROLE_PROOF_PASS", rls)


if __name__ == "__main__":
    unittest.main()
