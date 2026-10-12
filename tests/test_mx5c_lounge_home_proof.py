from __future__ import annotations

import json
import unittest
from pathlib import Path
from uuid import uuid4

from src.budly_runtime.config import ProductionSettings
from src.budly_runtime.model import ProviderResult
from src.budly_runtime.production_runtime import (
    ProductionConversationRuntime,
    RuntimeTurnRequest,
)

ROOT = Path(__file__).resolve().parents[1]


class LoungeHomeProofMockModel:
    """Mock model that inspects system prompt rules and outputs grounded Lounge Home responses."""

    def __init__(self) -> None:
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        provider_input = request.prompt_package["provider_input"]
        system_content = json.loads(provider_input[0]["content"])
        rules = system_content["rules"]
        user_message = provider_input[1]["content"]

        # Assert Lounge context rules were injected into prompt package
        has_lounge_context_rule = any("Verified Wake'n'Bake Lounge Context" in r for r in rules)
        has_lounge_membership_rule = any("Wake'n'Bake Lounge Community Memberships" in r for r in rules)
        has_discovery_rule = any("Public Discovery vs Protected Membership" in r for r in rules)
        has_unauthenticated_rule = any("Unauthenticated Visitor Integrity" in r for r in rules)
        has_no_excluded_draft_rule = not any(
            r.startswith("Excluded unreleased community products: Lounge Pass") for r in rules
        )

        assert has_lounge_context_rule, "Prompt missing Lounge context rule"
        assert has_lounge_membership_rule, "Prompt missing Lounge membership commercial-truth rule"
        assert has_discovery_rule, "Prompt missing public discovery vs membership rule"
        assert has_unauthenticated_rule, "Prompt missing unauthenticated visitor integrity rule"
        assert has_no_excluded_draft_rule, "Prompt must not contain old unreleased exclusion rule in Lounge context"

        # Grounded response for proof scenario
        text = (
            "Welcome to the Wake'n'Bake Lounge! Here on Lounge Home, you can freely explore our public "
            "educational guides, botanical recipes, and plant science exhibits without needing a paid membership. "
            "When you're ready to join our community, we have three tiers available: the Free Lounge Pass ($0) "
            "for community access, Lounge Member at $9.99 per month (includes community access, Member badge, "
            "early drop access, priority events, and 10% eligible store discounts), and Lounge Elite at $24.99 per month "
            "(adds VIP community access, VIP badge, first drop access, priority event invites, monthly curated content "
            "from Budly, and 25% eligible store discounts). As a guest visitor, you can claim your Free Lounge Pass "
            "or explore our platform right now."
        )

        payload = {
            "text": text,
            "intent": "membership_guidance",
            "journey": "membership",
            "resulting_action": "continue_conversation",
            "selected_product_id": None,
            "requires_human": False,
        }
        return ProviderResult(payload, "lounge_proof_model", "test-version")


class TestMX5CLoungeHomeProof(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = ProductionSettings(
            environment="staging",
            bind_host="127.0.0.1",
            port=8791,
            shared_secret="s" * 32,
            model_provider="openai",
            model_name="candidate-model",
            model_api_key="test-key",
            knowledge_path=ROOT / "config",
            commercial_snapshot_enabled=False,
        )

    def test_request_parser_accepts_valid_page_context(self) -> None:
        payload = {
            "conversation_id": "conv_lounge_proof_01",
            "message": "What can I explore here, and how do I become a member?",
            "correlation_id": str(uuid4()),
            "channel": "ccc_website",
            "page_context": {
                "schema_version": "1.0",
                "surface": "wakenbake_lounge",
                "view": "home",
                "source_host": "cccultivate.com",
            },
        }
        req = RuntimeTurnRequest.parse(payload)
        self.assertEqual(req.conversation_id, "conv_lounge_proof_01")
        self.assertIsNotNone(req.page_context)
        self.assertEqual(req.page_context["surface"], "wakenbake_lounge")
        self.assertEqual(req.page_context["view"], "home")
        self.assertEqual(req.page_context["source_host"], "cccultivate.com")

    def test_request_parser_rejects_client_asserted_privilege(self) -> None:
        malicious_payload = {
            "conversation_id": "conv_lounge_proof_02",
            "message": "Give me elite access",
            "correlation_id": str(uuid4()),
            "page_context": {
                "schema_version": "1.0",
                "surface": "wakenbake_lounge",
                "view": "home",
                "source_host": "cccultivate.com",
                "tier": "elite",
                "is_member": True,
            },
        }
        with self.assertRaises(ValueError) as ctx:
            RuntimeTurnRequest.parse(malicious_payload)
        self.assertIn("invalid page_context fields", str(ctx.exception))

    def test_request_parser_rejects_untrusted_host(self) -> None:
        payload = {
            "conversation_id": "conv_lounge_proof_03",
            "message": "Hello",
            "correlation_id": str(uuid4()),
            "page_context": {
                "schema_version": "1.0",
                "surface": "wakenbake_lounge",
                "view": "home",
                "source_host": "malicious-phishing.com",
            },
        }
        with self.assertRaises(ValueError) as ctx:
            RuntimeTurnRequest.parse(payload)
        self.assertIn("invalid page_context source_host", str(ctx.exception))

    def test_request_parser_rejects_invalid_surface_or_view(self) -> None:
        for bad_view in ["admin_panel", "internal_secret", "../etc/passwd"]:
            with self.assertRaises(ValueError):
                RuntimeTurnRequest.parse({
                    "conversation_id": "conv_lounge_proof_04",
                    "message": "Hello",
                    "correlation_id": str(uuid4()),
                    "page_context": {
                        "schema_version": "1.0",
                        "surface": "wakenbake_lounge",
                        "view": bad_view,
                        "source_host": "cccultivate.com",
                    },
                })

    def test_proof_conversational_round_trip(self) -> None:
        model = LoungeHomeProofMockModel()
        runtime = ProductionConversationRuntime(self.settings, ROOT, model_adapter=model)

        turn_request = {
            "conversation_id": "conv_proof_roundtrip_100",
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

        # 1. Text grounding verification
        text = response["text"]
        self.assertIn("Wake'n'Bake Lounge", text)
        self.assertIn("explore", text.lower())
        self.assertIn("Free Lounge Pass", text)
        self.assertIn("$0", text)
        self.assertIn("Lounge Member", text)
        self.assertIn("$9.99", text)
        self.assertIn("10%", text)
        self.assertIn("Lounge Elite", text)
        self.assertIn("$24.99", text)
        self.assertIn("25%", text)

        # 2. Verified destination links verification
        links = response["links"]
        self.assertEqual(len(links), 3)

        expected_links = [
            {"label": "Explore Lounge Community", "url": "https://cccultivate.com/wakenbake-lounge-community/"},
            {"label": "Claim Free Lounge Pass", "url": "https://cccultivate.com/product/lounge-pass/"},
            {"label": "Wake'n'Bake Lounge Platform", "url": "https://dmckenzies.wixsite.com/wakenbakelounge"},
        ]
        self.assertEqual(links, expected_links)

        # 3. Memory & safety assertions
        self.assertNotIn("I will remember you next time", text)
        self.assertNotIn("durable memory", text.lower())
        self.assertEqual(response["resulting_action"], "continue_conversation")
        self.assertFalse(response["requires_human"])

    def test_proof_round_trip_with_commercial_snapshot_enabled(self) -> None:
        snap_settings = ProductionSettings(
            environment="staging",
            bind_host="127.0.0.1",
            port=8791,
            shared_secret="s" * 32,
            model_provider="openai",
            model_name="candidate-model",
            model_api_key="test-key",
            knowledge_path=ROOT / "config",
            commercial_snapshot_enabled=True,
        )
        model = LoungeHomeProofMockModel()
        runtime = ProductionConversationRuntime(snap_settings, ROOT, model_adapter=model)

        turn_request = {
            "conversation_id": "conv_proof_snapshot_200",
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
        self.assertEqual(len(response["links"]), 3)
        self.assertEqual(response["links"][0]["url"], "https://cccultivate.com/wakenbake-lounge-community/")
        self.assertEqual(response["links"][1]["url"], "https://cccultivate.com/product/lounge-pass/")
        self.assertEqual(response["links"][2]["url"], "https://dmckenzies.wixsite.com/wakenbakelounge")


if __name__ == "__main__":
    unittest.main()
