import json
import tempfile
import unittest
from pathlib import Path

from scripts.patch_sts2_revenue_workflow import build

ROOT = Path(__file__).resolve().parents[1]
class STS2RevenueWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow_path = ROOT / "deploy/n8n/REV-Woo-Order-Event-Intake-STS2.json"
        cls.workflow = json.loads(cls.workflow_path.read_text(encoding="utf-8"))[0]
        cls.code = next(node for node in cls.workflow["nodes"] if node["name"] == "Normalize Revenue Event v1")["parameters"]["jsCode"]

    def test_established_security_and_idempotency_nodes_remain(self):
        names = {node["name"] for node in self.workflow["nodes"]}
        for name in ("Compute Woo HMAC", "Verify Signature and Validate Envelope", "Generate Idempotency Key", "Supabase Atomic Ingest RPC"):
            self.assertIn(name, names)
        self.assertEqual(self.workflow["id"], "REVWooIntakeV1")

    def test_only_governed_order_meta_is_normalized(self):
        for key in ("_budly_commerce_correlation_id", "_budly_conversation_id", "_budly_decision_id"):
            self.assertIn(key, self.code)
        for pii in ("billing.email", "billing.phone", "shipping.address", "customer_ip_address"):
            self.assertNotIn(pii, self.code)

    def test_missing_and_invalid_correlation_do_not_attribute(self):
        self.assertIn("status: correlationId || conversationId || decisionId ? 'invalid' : 'absent'", self.code)
        self.assertIn("correlationValid ?", self.code)

    def test_schema_and_rpc_are_unchanged(self):
        self.assertIn("schema_version: 'bros.revenue_event.v1'", self.code)
        rpc = next(node for node in self.workflow["nodes"] if node["name"] == "Supabase Atomic Ingest RPC")
        self.assertTrue(rpc["parameters"]["url"].endswith("/rpc/bros_ingest_revenue_event"))

    def test_builder_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            build(self.workflow_path, first)
            build(first, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
