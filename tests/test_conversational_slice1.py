from __future__ import annotations

import hashlib
import hmac
import io
import json
import time
import unittest
from pathlib import Path
from uuid import uuid4

from src.budly_runtime.config import FeatureFlags, ProductionSettings, RuntimeConfig
from src.budly_runtime.http_service import RuntimeHTTPService
from src.budly_runtime.model import OpenAIResponsesAdapter, ProviderResult
from src.budly_runtime.production_knowledge import ApprovedRepositoryKnowledgeAdapter
from src.budly_runtime.production_runtime import (
    EphemeralSessionStore, ProductionConversationRuntime, ProductionResponseValidator,
    RuntimeTurnRequest,
)
from src.budly_runtime.tool_gateway import ToolHealth

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy/wordpress/budly-sales-agent"


class FakeModel:
    def __init__(self, behavior: str = "normal") -> None:
        self.behavior = behavior
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.behavior == "timeout":
            raise TimeoutError
        if self.behavior == "unavailable":
            raise ConnectionError
        if self.behavior == "invalid":
            return ProviderResult({"text": "bad"}, "fake", "fake")
        prompt = json.loads(request.prompt_package["provider_input"][0]["content"])
        user = request.prompt_package["provider_input"][1]["content"]
        deterministic = prompt["deterministic_authority"]
        selected = deterministic.get("selected_product_id")
        payload = {
            "text": f"Budly answer: {user}", "intent": "education", "journey": deterministic.get("journey"),
            "resulting_action": "continue_conversation", "selected_product_id": selected,
            "requires_human": False,
        }
        return ProviderResult(payload, "fake", "fake")


def settings(environment="staging"):
    return ProductionSettings(environment, "127.0.0.1", 8791, "s" * 32, "openai", "candidate-model", "test-key", ROOT / "config")


class SliceOneRuntimeTests(unittest.TestCase):
    def make_runtime(self, model=None, knowledge=None):
        return ProductionConversationRuntime(settings(), ROOT, model_adapter=model or FakeModel(), knowledge_adapter=knowledge)

    def request(self, conversation="conv_abcdef123456", message="hello", **extra):
        return {"conversation_id": conversation, "message": message, "correlation_id": str(uuid4()),
                "use_durable_memory": False, **extra}

    def test_runtime_request_is_strict_and_memory_disabled(self):
        RuntimeTurnRequest.parse(self.request())
        with self.assertRaises(ValueError):
            RuntimeTurnRequest.parse(self.request(use_durable_memory=True))
        with self.assertRaises(ValueError):
            RuntimeTurnRequest.parse({**self.request(), "provider": "openai"})

    def test_current_session_continuity_is_bounded(self):
        model = FakeModel()
        runtime = self.make_runtime(model)
        req = self.request(message="hello")
        first = runtime.turn(req)
        second = runtime.turn({**req, "message": "follow up", "correlation_id": str(uuid4())})
        self.assertTrue(first["success"] and second["success"])
        prompt = json.loads(model.requests[-1].prompt_package["provider_input"][0]["content"])
        recent = next(layer["content"] for layer in prompt["layers"] if layer["name"] == "RECENT CONVERSATION TURNS")
        self.assertEqual(recent[-2]["content"], "hello")

    def test_follow_up_reuses_governed_knowledge_domain(self):
        model = FakeModel()
        runtime = self.make_runtime(model)
        runtime.turn(self.request(message="Tell me about cannabinoids."))
        result = runtime.turn(self.request(message="Explain them simply."))
        self.assertTrue(result["evidence"]["knowledge_used"])

    def test_sessions_are_isolated(self):
        model = FakeModel()
        runtime = self.make_runtime(model)
        runtime.turn(self.request("conv_customerA1", "alpha"))
        runtime.turn(self.request("conv_customerB2", "beta"))
        prompt = json.loads(model.requests[-1].prompt_package["provider_input"][0]["content"])
        recent = next(layer["content"] for layer in prompt["layers"] if layer["name"] == "RECENT CONVERSATION TURNS")
        self.assertNotIn("alpha", json.dumps(recent))

    def test_reset_discards_ephemeral_context(self):
        model = FakeModel()
        runtime = self.make_runtime(model)
        runtime.turn(self.request(message="alpha"))
        runtime.turn(self.request(message="fresh", reset=True))
        prompt = json.loads(model.requests[-1].prompt_package["provider_input"][0]["content"])
        recent = next(layer["content"] for layer in prompt["layers"] if layer["name"] == "RECENT CONVERSATION TURNS")
        self.assertEqual(recent, [])

    def test_provider_failure_returns_guided_fallback(self):
        for behavior in ("timeout", "unavailable", "invalid"):
            result = self.make_runtime(FakeModel(behavior)).turn(self.request())
            self.assertEqual(result["response"]["resulting_action"], "legacy_guided_flow")

    def test_deterministic_human_review_wins(self):
        result = self.make_runtime().turn(self.request(deterministic_context={"outcome": "human_review", "journey": "wellness"}))
        self.assertTrue(result["response"]["requires_human"])
        self.assertEqual(result["response"]["resulting_action"], "human_handoff")

    def test_model_cannot_change_product_truth(self):
        validator = ProductionResponseValidator()
        payload = {"text":"x","intent":"product","journey":"education","resulting_action":"continue_conversation",
                   "selected_product_id":"invented","requires_human":False}
        valid, reasons = validator.validate(payload, {"selected_product_id":"approved"})
        self.assertFalse(valid)
        self.assertIn("product_authority", reasons)

    def test_policy_retrieval_has_provenance(self):
        result = self.make_runtime().turn(self.request(message="What is the return policy for physical books?"))
        self.assertTrue(result["evidence"]["knowledge_used"])
        self.assertTrue(self.make_runtime().tools.registry.resolve("knowledge.retrieve", "1.0").tool_id.startswith("approved_"))

    def test_unapproved_educational_gap_is_honest(self):
        model = FakeModel()
        result = self.make_runtime(model).turn(self.request(message="What medical treatment cures glaucoma?"))
        self.assertFalse(result["evidence"]["knowledge_used"])
        self.assertIn("approved source", result["response"]["text"])
        self.assertEqual(result["response"]["resulting_action"], "safe_no_match")
        self.assertEqual(model.requests, [])

    def test_approved_education_corpus_is_bounded_and_provenanced(self):
        adapter = ApprovedRepositoryKnowledgeAdapter(
            ROOT / "config/policies.json", ROOT / "config/products.json",
            ROOT / "config/budly_runtime/education-corpus-v0.1.json",
        )
        blue_dream = next(item for item in adapter._items if item["knowledge_id"] == "education:blue-dream-terpenes")
        self.assertEqual(blue_dream["classification"], "Public")
        self.assertEqual(blue_dream["version"], "0.1")
        self.assertIn("owner-controlled://", blue_dream["source_reference"])
        self.assertIn("myrcene, pinene, and caryophyllene", blue_dream["content"])
        self.assertIn("should not be presented as guaranteed chemistry", blue_dream["content"])
        combined = " ".join(item["content"].lower() for item in adapter._items if item["knowledge_id"].startswith("education:"))
        self.assertNotIn("potency range", combined)

    def test_product_source_excludes_price_and_stock(self):
        adapter = ApprovedRepositoryKnowledgeAdapter(ROOT / "config/policies.json", ROOT / "config/products.json")
        item = next(item for item in adapter._items if item["domain"] == "product_catalog")
        content = json.loads(item["content"])
        self.assertNotIn("price", content)
        self.assertNotIn("in_stock", content)

    def test_event_correlation_and_no_transcript_fields(self):
        runtime = self.make_runtime()
        req = self.request()
        runtime.turn(req)
        event = runtime.events.events[-1]
        self.assertEqual(event["correlation_id"], req["correlation_id"])
        self.assertNotIn("message", event)
        self.assertNotIn("response_text", event)

    def test_ephemeral_store_expires_mapping(self):
        store = EphemeralSessionStore(ttl_seconds=60)
        first = store.acquire("conv_abcdef")
        store._map["conv_abcdef"] = (first.session_id, time.monotonic() - 61)
        second = store.acquire("conv_abcdef")
        self.assertNotEqual(first.session_id, second.session_id)


class ConfigurationAndProviderTests(unittest.TestCase):
    def test_production_settings_fail_closed(self):
        complete = {"BUDLY_RUNTIME_ENV":"staging","BUDLY_RUNTIME_SHARED_SECRET":"s"*32,
                    "BUDLY_MODEL_PROVIDER":"openai","BUDLY_MODEL_NAME":"candidate","BUDLY_MODEL_API_KEY":"key"}
        self.assertEqual(ProductionSettings.from_environment(complete).environment, "staging")
        for key in ("BUDLY_RUNTIME_SHARED_SECRET", "BUDLY_MODEL_NAME", "BUDLY_MODEL_API_KEY"):
            broken = dict(complete); broken.pop(key)
            with self.assertRaises(ValueError): ProductionSettings.from_environment(broken)

    def test_production_cannot_bind_public_interface(self):
        with self.assertRaises(ValueError):
            ProductionSettings("production", "0.0.0.0", 8791, "s"*32, "openai", "m", "k", ROOT / "config").validate()

    def test_durable_memory_flag_cannot_be_enabled(self):
        with self.assertRaises(ValueError):
            RuntimeConfig(flags=FeatureFlags(budly_durable_memory_enabled=True))

    def test_openai_adapter_parses_structured_response(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self): return json.dumps({"output_text": json.dumps({"ok": True}), "usage":{"input_tokens":1,"output_tokens":2}}).encode()
        captured = {}
        def opener(request, timeout):
            captured["request"], captured["timeout"] = request, timeout
            return Response()
        adapter = OpenAIResponsesAdapter("candidate", "server-secret", opener=opener)
        result = adapter.generate(type("Request", (), {"prompt_package":{"provider_input":[],"output_schema":{"type":"object"}}})())
        self.assertEqual(result.payload, {"ok": True})
        self.assertEqual(result.provider, "openai")
        self.assertIn(b"candidate", captured["request"].data)
        self.assertNotIn(b"server-secret", captured["request"].data)

    def test_hmac_boundary_rejects_replay_and_bad_signature(self):
        service = RuntimeHTTPService(object(), "s"*32)
        body = b'{}'; stamp = str(int(time.time())); correlation = str(uuid4())
        signature = hmac.new(b"s"*32, stamp.encode()+b"."+body, hashlib.sha256).hexdigest()
        self.assertTrue(service.authenticate(body, stamp, signature, correlation))
        self.assertFalse(service.authenticate(body, stamp, signature, correlation))
        self.assertFalse(service.authenticate(body, stamp, "bad", str(uuid4())))


class WordPressIntegrationContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proxy = (PLUGIN / "includes/Runtime/ConversationProxy.php").read_text(encoding="utf-8")
        cls.plugin = (PLUGIN / "budly-sales-agent.php").read_text(encoding="utf-8")
        cls.js = (PLUGIN / "assets/budly-sales.js").read_text(encoding="utf-8")

    def test_wordpress_route_has_nonce_size_rate_and_timeout_controls(self):
        for token in ("budly-runtime/v1", "wp_verify_nonce", "MAX_REQUEST_BYTES", "rate_allowed", "RUNTIME_TIMEOUT_SECONDS", "wp_safe_remote_post"):
            self.assertIn(token, self.proxy)

    def test_secret_is_server_only(self):
        self.assertIn("BUDLY_CONVERSATIONAL_RUNTIME_SECRET", self.proxy)
        self.assertNotIn("RUNTIME_SECRET", self.js)
        self.assertNotIn("conversationSecret", self.plugin)

    def test_caller_cannot_select_provider_or_tool(self):
        self.assertIn("array('conversation_id','message','reset')", self.proxy)
        self.assertNotIn("provider", "conversation_id,message,reset")

    def test_wordpress_forces_durable_memory_false(self):
        self.assertIn("'use_durable_memory' => false", self.proxy)
        self.assertIn("'durableMemoryEnabled' => false", self.plugin)

    def test_feature_off_preserves_legacy_source(self):
        self.assertIn("ConversationProxy::enabled()", self.plugin)
        self.assertIn("if(cfg.conversationEnabled)", self.js)
        self.assertIn("governedDecision", self.js)
        self.assertIn("activateLegacy", self.js)

    def test_response_is_revalidated_by_wordpress(self):
        self.assertIn("valid_runtime_response", self.proxy)
        self.assertIn("selected_product_id", self.proxy)
        self.assertIn("human_review", self.proxy)

    def test_frontend_uses_json_non_streaming_and_safe_fallback(self):
        self.assertIn("conversationalTurn", self.js)
        self.assertIn("JSON.stringify({conversation_id:state.session,message})", self.js)
        self.assertIn("switching to the guided experience", self.js)
        self.assertNotIn("WebSocket", self.js)
        self.assertNotIn("EventSource", self.js)


if __name__ == "__main__":
    unittest.main()
