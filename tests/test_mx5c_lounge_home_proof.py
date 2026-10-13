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
        has_publication_rule = any("Publication Status & Exploration" in r for r in rules)
        has_unauthenticated_rule = any("Unauthenticated Visitor Integrity" in r for r in rules)
        has_no_excluded_draft_rule = not any(
            r.startswith("Excluded unreleased community products: Lounge Pass") for r in rules
        )
        has_no_contradictory_no_free_tier = not any(
            "NO free membership tier" in r for r in rules
        )
        has_historic_nft_rule = any(
            "Historic NFT Membership Family" in r for r in rules
        )

        assert has_lounge_context_rule, "Prompt missing Lounge context rule"
        assert has_lounge_membership_rule, "Prompt missing Lounge membership commercial-truth rule"
        assert has_publication_rule, "Prompt missing publication status & exploration rule"
        assert has_unauthenticated_rule, "Prompt missing unauthenticated visitor integrity rule"
        assert has_no_excluded_draft_rule, "Prompt must not contain old unreleased exclusion rule in Lounge context"
        assert has_no_contradictory_no_free_tier, "Prompt must not contain contradictory NO free membership tier rule"
        assert has_historic_nft_rule, "Prompt missing cleanly separated historic NFT membership family rule"

        # Grounded response for proof scenario distinguishing planned exhibits from currently accessible passes
        text = (
            "Welcome to the Wake'n'Bake Lounge! Here on Lounge Home, you can explore our community orientation "
            "and learn about our upcoming educational guides, botanical recipes, and plant-science exhibits, which are "
            "currently in editorial preparation for future release. When you're ready to join our community, "
            "we have three tiers available: the Free Lounge Pass ($0) for community access, Lounge Member at $9.99 "
            "per month (includes community access, Member badge, early drop access, priority events, and 10% eligible store discounts), "
            "and Lounge Elite at $24.99 per month (adds VIP community access, VIP badge, first drop access, priority event invites, "
            "monthly curated content from Budly, and 25% eligible store discounts). As a guest visitor, you can claim your Free Lounge Pass "
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
        self.assertIn("editorial preparation", text.lower())
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

    def test_fails_safely_when_commercial_truth_missing(self) -> None:
        model = LoungeHomeProofMockModel()
        runtime = ProductionConversationRuntime(self.settings, ROOT, model_adapter=model)
        # Mock _load_governed_commercial_truth to simulate unverified truth file
        runtime._load_governed_commercial_truth = lambda: None

        turn_request = {
            "conversation_id": "conv_proof_missing_truth_300",
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
        self.assertEqual(response["resulting_action"], "safe_no_match")
        self.assertIn("I don’t have an approved source for that yet, so I won’t guess.", response["text"])
        self.assertEqual(response["links"], [])

    def test_no_contradictory_prompt_rules_in_lounge_home_context(self) -> None:
        model = LoungeHomeProofMockModel()
        runtime = ProductionConversationRuntime(self.settings, ROOT, model_adapter=model)

        turn_request = {
            "conversation_id": "conv_proof_prompt_inspection_400",
            "message": "Tell me about the community tiers and exploration",
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
        self.assertEqual(len(model.requests), 1)
        req = model.requests[0]
        sys_content = json.loads(req.prompt_package["provider_input"][0]["content"])
        rules = sys_content["rules"]

        # Check prompt rules integrity
        for r in rules:
            self.assertFalse(r.startswith("Excluded unreleased community products: Lounge Pass"))
            self.assertNotIn("NO free membership tier", r)

        has_nft_family = any("Historic NFT Membership Family" in r for r in rules)
        self.assertTrue(has_nft_family)

        has_dynamic_lounge_rule = any("Wake'n'Bake Lounge Community Memberships" in r for r in rules)
        self.assertTrue(has_dynamic_lounge_rule)
        lounge_rule = next(r for r in rules if "Wake'n'Bake Lounge Community Memberships" in r)
        self.assertIn("Free Lounge Pass ($0", lounge_rule)
        self.assertIn("Lounge Member ($9.99/mo", lounge_rule)
        self.assertIn("Lounge Elite ($24.99/mo", lounge_rule)
        self.assertIn("eligible purchases, subject to the governed exclusions", lounge_rule)
        self.assertNotIn("eligible Lounge Collection purchases", lounge_rule)
        self.assertIn("Discounts exclude:", lounge_rule)
        self.assertIn("LEGENDS NFT memberships remain separate and unchanged", lounge_rule)


if __name__ == "__main__":
    unittest.main()
