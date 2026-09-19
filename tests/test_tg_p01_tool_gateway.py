import json
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from src.budly_runtime.tool_gateway import (
    Actor, AuditSink, CapabilityDefinition, CapabilityRef, ErrorClass,
    KnowledgeRetrieveInput, LocalKnowledgeAdapter, RequestValidationError,
    ResultStatus, ToolGateway, ToolHealth, ToolRegistry, ToolRequest,
    reconcile_authority,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "config/tool_gateway/tg-p01-knowledge-fixtures.json").read_text(encoding="utf-8"))


def request(actor_type="budly_service", domain="customer_policy", query="approved return policy", **changes):
    values = {
        "request_id": str(uuid4()), "correlation_id": str(uuid4()),
        "actor": Actor("budly-service-test", actor_type),
        "capability": CapabilityRef("knowledge.retrieve", "1.0"),
        "purpose": "customer_education", "channel": "website_chat", "environment": "prototype",
        "input": KnowledgeRetrieveInput(query, domain, 5),
    }
    values.update(changes)
    return ToolRequest(**values)


def gateway(*, enabled=True, health=ToolHealth.HEALTHY, fail=False, fixtures=None):
    adapter = LocalKnowledgeAdapter(list(FIXTURES if fixtures is None else fixtures), state=health, fail=fail)
    audit = AuditSink()
    return ToolGateway(ToolRegistry(CapabilityDefinition(enabled=enabled), adapter), audit), adapter, audit


class TGP01AcceptanceTests(unittest.TestCase):
    def test_t01_unknown_actor(self):
        gw, adapter, _ = gateway()
        result = gw.execute(request(actor_type="anonymous_actor"))
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.DENIED, ErrorClass.UNKNOWN_ACTOR.value))
        self.assertIsNone(adapter.last_context)

    def test_t02_production_environment(self):
        gw, adapter, _ = gateway()
        result = gw.execute(request(environment="production"))
        self.assertEqual(result.error["classification"], ErrorClass.ENVIRONMENT_DENIED.value)
        self.assertIsNone(adapter.last_context)

    def test_t03_unknown_capability(self):
        gw, _, _ = gateway()
        result = gw.execute(request(capability=CapabilityRef("unknown.capability", "1.0")))
        self.assertEqual(result.error["classification"], ErrorClass.UNKNOWN_CAPABILITY.value)

    def test_t04_caller_cannot_select_provider(self):
        raw = self.raw_request(); raw["provider"] = "attacker-selected"
        with self.assertRaises(RequestValidationError): ToolRequest.from_dict(raw)

    def test_t05_superseded_knowledge_excluded(self):
        gw, _, _ = gateway()
        result = gw.execute(request(query="policy fixture"))
        ids = {item["knowledge_id"] for item in result.result["items"]}
        self.assertIn("K-TEST-001", ids)
        self.assertNotIn("K-TEST-003", ids)

    def test_t06_restricted_knowledge_denied_to_budly(self):
        gw, _, _ = gateway()
        result = gw.execute(request(domain="governance", query="restricted governance"))
        self.assertEqual(result.error["classification"], ErrorClass.DATA_SCOPE_DENIED.value)
        self.assertIsNone(result.result)

    def test_t07_malformed_input(self):
        gw, adapter, audit = gateway()
        raw = self.raw_request(); raw["input"].pop("query")
        result = gw.execute_raw(raw)
        self.assertEqual(result.error["classification"], ErrorClass.INPUT_VALIDATION_FAILED.value)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertIsNone(adapter.last_context)
        self.assertEqual(audit.events[-1].error_classification, ErrorClass.INPUT_VALIDATION_FAILED.value)

    def test_t08_missing_provenance(self):
        malformed = [dict(FIXTURES[0])]; malformed[0].pop("source_reference")
        gw, _, _ = gateway(fixtures=malformed)
        result = gw.execute(request())
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.FAILED, ErrorClass.OUTPUT_VALIDATION_FAILED.value))
        self.assertIsNone(result.result)

    def test_t09_adapter_failure(self):
        gw, _, _ = gateway(fail=True)
        result = gw.execute(request())
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.FAILED, ErrorClass.ADAPTER_FAILURE.value))

    def test_t10_unauthorized_domain(self):
        gw, _, _ = gateway()
        result = gw.execute(request(domain="governance"))
        self.assertEqual(result.error["classification"], ErrorClass.DATA_SCOPE_DENIED.value)

    def test_t11_authorized_budly_retrieval(self):
        gw, _, audit = gateway()
        result = gw.execute(request())
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.result["items"][0]["knowledge_id"], "K-TEST-001")
        self.assertTrue(result.result["items"][0]["source_reference"])
        self.assertEqual(result.authority, {"bros_level": 1, "tool_class": "T0"})
        self.assertEqual(result.evidence_reference, audit.events[-1].audit_event_id)

    def test_t12_authorized_administrator_retrieval(self):
        gw, _, _ = gateway()
        result = gw.execute(request(actor_type="administrator", actor=Actor("admin-test", "administrator"), domain="governance", query="restricted governance"))
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.result["items"][0]["knowledge_id"], "K-TEST-004")

    def test_t13_correlation_preserved(self):
        gw, _, audit = gateway(); req = request()
        result = gw.execute(req)
        self.assertEqual(req.correlation_id, result.correlation_id)
        self.assertEqual(req.correlation_id, audit.events[-1].correlation_id)

    def test_t14_result_limit(self):
        extra = dict(FIXTURES[0]); extra.update(knowledge_id="K-TEST-006", title="Another approved return policy")
        gw, _, _ = gateway(fixtures=FIXTURES + [extra])
        result = gw.execute(request(input=KnowledgeRetrieveInput("approved return policy", "customer_policy", 1)))
        self.assertLessEqual(len(result.result["items"]), 1)

    def test_t15_empty_valid_search(self):
        gw, _, _ = gateway()
        result = gw.execute(request(query="nonmatching-zebra-term"))
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.result, {"items": []})

    def test_t16_context_injection_does_not_reach_adapter(self):
        gw, adapter, _ = gateway(); raw = self.raw_request()
        raw["input"]["customer_email"] = "synthetic@example.invalid"
        result = gw.execute_raw(raw)
        self.assertEqual(result.error["classification"], ErrorClass.INPUT_VALIDATION_FAILED.value)
        self.assertIsNone(adapter.last_context)

    def test_t17_authority_cannot_be_downgraded(self):
        self.assertFalse(reconcile_authority(2, "T0").execution_allowed)
        self.assertTrue(reconcile_authority(2, "T0").human_review_required)
        self.assertFalse(reconcile_authority(3, "T0").execution_allowed)
        self.assertFalse(reconcile_authority(1, "T3").execution_allowed)
        self.assertTrue(reconcile_authority(1, "T3").human_review_required)
        self.assertEqual(reconcile_authority(1, "TX").reason, "prohibited")
        self.assertFalse(reconcile_authority(1, "T2").execution_allowed)
        self.assertTrue(reconcile_authority(1, "T2", specifically_authorized_bounded_write=True).execution_allowed)

    def test_t18_disabled_capability(self):
        gw, adapter, _ = gateway(enabled=False)
        result = gw.execute(request())
        self.assertEqual(result.error["classification"], ErrorClass.CAPABILITY_DISABLED.value)
        self.assertIsNone(adapter.last_context)

    def test_t19_unavailable_tool_has_no_fallback(self):
        gw, _, _ = gateway(health=ToolHealth.UNAVAILABLE)
        result = gw.execute(request())
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.UNAVAILABLE, ErrorClass.TOOL_UNAVAILABLE.value))
        self.assertIsNone(result.result)

    def test_t20_audit_evidence_for_denial(self):
        gw, _, audit = gateway(); req = request(actor_type="unknown_agent")
        result = gw.execute(req); event = audit.events[-1]
        self.assertEqual(event.actor_id, req.actor.actor_id)
        self.assertEqual(event.capability_id, "knowledge.retrieve")
        self.assertEqual(event.permission_decision, "DENY")
        self.assertEqual(event.correlation_id, req.correlation_id)
        self.assertEqual(event.error_classification, ErrorClass.UNKNOWN_ACTOR.value)
        self.assertNotIn("query", event.__dict__)
        self.assertEqual(result.evidence_reference, event.audit_event_id)

    @staticmethod
    def raw_request():
        req = request()
        return {
            "request_id": req.request_id, "correlation_id": req.correlation_id,
            "actor": {"actor_id": req.actor.actor_id, "actor_type": req.actor.actor_type},
            "capability": {"capability_id": req.capability.capability_id, "capability_version": req.capability.capability_version},
            "purpose": req.purpose, "channel": req.channel, "environment": req.environment,
            "input": {"query": req.input.query, "domain": req.input.domain, "max_results": req.input.max_results},
        }


if __name__ == "__main__":
    unittest.main()
