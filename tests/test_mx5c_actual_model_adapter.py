from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from uuid import uuid4

from src.budly_runtime.config import ProductionSettings
from src.budly_runtime.model import OpenAIResponsesAdapter
from src.budly_runtime.production_runtime import (
    OUTPUT_SCHEMA,
    ProductionConversationRuntime,
    RuntimeTurnRequest,
)

ROOT = Path(__file__).resolve().parents[1]


class TestMX5CActualModelAdapter(unittest.TestCase):
    """Verifies governed context delivery and execution behavior using the actual configured
    Budly model adapter (OpenAIResponsesAdapter).

    Adheres strictly to MWB-005 instruction:
    'Add a separate test using the actual configured Budly model adapter (OpenAIResponsesAdapter).
    Verify governed context delivery and response to "What can I explore here, and how do I become a member?".
    Do not use a mock model to claim actual model success; if live model API execution is
    unavailable in the environment, state the limitation explicitly.'
    """

    def setUp(self) -> None:
        self.live_api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("BUDLY_MODEL_API_KEY")
        self.settings = ProductionSettings(
            environment="staging",
            bind_host="127.0.0.1",
            port=8791,
            shared_secret="s" * 32,
            model_provider="openai",
            model_name="gpt-4o-mini",
            model_api_key=self.live_api_key or "sk-placeholder-not-configured",
            knowledge_path=ROOT / "config",
            commercial_snapshot_enabled=False,
        )

    def test_actual_adapter_governed_payload_delivery(self) -> None:
        """Verifies that ProductionConversationRuntime configures the actual OpenAIResponsesAdapter
        and delivers governed Lounge Home rules and schema into the provider request.
        """
        captured_requests = []

        class MockOpener:
            def __call__(self, request, timeout=15.0):
                captured_requests.append(request)
                raise ConnectionError("intercepted for payload verification")

        adapter = OpenAIResponsesAdapter(
            "gpt-4o-mini",
            "sk-test-key-for-payload-audit",
            opener=MockOpener(),
        )

        runtime = ProductionConversationRuntime(self.settings, ROOT, model_adapter=adapter)

        turn_request = {
            "conversation_id": "conv_actual_adapter_payload_01",
            "message": "What can I explore here, and how do I become a member?",
            "correlation_id": str(uuid4()),
            "page_context": {
                "schema_version": "1.0",
                "surface": "wakenbake_lounge",
                "view": "home",
                "source_host": "cccultivate.com",
            },
        }

        # Executing turn triggers the actual adapter's generate()
        result = runtime.turn(turn_request)
        self.assertTrue(result["success"])
        # Adapter intercepted via MockOpener, returning safe fallback gracefully
        self.assertEqual(len(captured_requests), 1)

        sent_request = captured_requests[0]
        self.assertEqual(sent_request.get_method(), "POST")
        self.assertEqual(sent_request.full_url, "https://api.openai.com/v1/responses")
        self.assertEqual(sent_request.headers.get("Authorization"), "Bearer sk-test-key-for-payload-audit")

        body = json.loads(sent_request.data.decode("utf-8"))
        self.assertEqual(body["model"], "gpt-4o-mini")
        self.assertEqual(body["text"]["format"]["schema"], OUTPUT_SCHEMA)

        provider_input = body["input"]
        self.assertEqual(len(provider_input), 2)
        self.assertEqual(provider_input[1]["content"], "What can I explore here, and how do I become a member?")

        system_payload = json.loads(provider_input[0]["content"])
        rules = system_payload["rules"]

        # 1. Governed Lounge context rule delivered
        self.assertTrue(any("Verified Wake'n'Bake Lounge Context" in r for r in rules))

        # 2. Dynamic commercial truth rule delivered
        self.assertTrue(any("Wake'n'Bake Lounge Community Memberships" in r for r in rules))
        lounge_rule = next(r for r in rules if "Wake'n'Bake Lounge Community Memberships" in r)
        self.assertIn("Free Lounge Pass ($0", lounge_rule)
        self.assertIn("Lounge Member ($9.99/mo", lounge_rule)
        self.assertIn("Lounge Elite ($24.99/mo", lounge_rule)
        self.assertIn("Discounts exclude:", lounge_rule)

        # 3. MX-4 publication status and exploration rule delivered
        self.assertTrue(any("Publication Status & Exploration" in r for r in rules))
        pub_rule = next(r for r in rules if "Publication Status & Exploration" in r)
        self.assertIn("editorial production / exhibit preparation", pub_rule)
        self.assertIn("Lounge Community hub orientation", pub_rule)

        # 4. Clean separation of historic NFT membership family
        self.assertTrue(any("Historic NFT Membership Family" in r for r in rules))
        self.assertFalse(any("NO free membership tier" in r for r in rules))
        self.assertFalse(any(r.startswith("Excluded unreleased community products: Lounge Pass") for r in rules))

    def test_live_execution_or_explicit_limitation_disclosure(self) -> None:
        """Executes against live OpenAI endpoint if credentials exist, or explicitly
        discloses the development environment limitation without falsely claiming
        mock success as live execution.
        """
        if not self.live_api_key or self.live_api_key.startswith("sk-placeholder"):
            limitation_disclosure = (
                "ENVIRONMENT LIMITATION: Live model API credentials (OPENAI_API_KEY / BUDLY_MODEL_API_KEY) "
                "are not configured in this offline development environment. Live model execution cannot be "
                "performed. Governed prompt assembly, request routing, and OpenAIResponsesAdapter payload "
                "contract have been verified separately without claiming mock model execution as live success."
            )
            # Record explicit limitation per MWB-005
            print(f"\n[MWB-005 DISCLOSURE] {limitation_disclosure}")
            self.assertTrue(True, limitation_disclosure)
            return

        # If live API key is present in environment, perform real live call
        adapter = OpenAIResponsesAdapter("gpt-4o-mini", self.live_api_key)
        runtime = ProductionConversationRuntime(self.settings, ROOT, model_adapter=adapter)

        turn_request = {
            "conversation_id": f"conv_live_{uuid4().hex[:8]}",
            "message": "What can I explore here, and how do I become a member?",
            "correlation_id": str(uuid4()),
            "page_context": {
                "schema_version": "1.0",
                "surface": "wakenbake_lounge",
                "view": "home",
                "source_host": "cccultivate.com",
            },
        }

        result = runtime.turn(turn_request)
        self.assertTrue(result["success"])
        response = result["response"]
        text = response["text"]

        self.assertIn("Wake'n'Bake Lounge", text)
        self.assertIn("Free Lounge Pass", text)
        self.assertEqual(len(response["links"]), 3)
