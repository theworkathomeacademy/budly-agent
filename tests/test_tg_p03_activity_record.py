import io
import json
import unittest
from dataclasses import asdict
from uuid import uuid4

from src.budly_runtime.tool_gateway import (
    ALLOWED_ACTIVITY_TYPES, ActivityRecordInput, Actor, AuditSink, CapabilityDefinition, CapabilityRef,
    ErrorClass, InMemoryActivityStore, LocalActivityAdapter, LocalKnowledgeAdapter,
    LocalOperationalMetricsAdapter, OperationalMetricsRetrieveInput, RequestValidationError, ResultStatus,
    SourceRef, SubjectRef, ToolGateway, ToolHealth, ToolRegistry, ToolRequest,
)
from tests.test_tg_p01_tool_gateway import FIXTURES as KNOWLEDGE_FIXTURES
from tests.test_tg_p02_operational_metrics import METRIC_FIXTURES, metrics_definition

OCCURRED_AT = "2026-08-24T12:00:00+00:00"


def activity_definition(enabled=True):
    return CapabilityDefinition(
        capability_id="activity.record", capability_version="1.0", bros_level=1, tool_class="T2",
        enabled=enabled, allowed_purposes=frozenset({"relationship_history", "interaction_recording", "support_history", "recommendation_evidence", "internal_test"}),
        allowed_channels=frozenset({"website_chat", "internal_test", "admin_console", "system_internal"}),
        specifically_authorized_bounded_write=True, allowed_activity_types=ALLOWED_ACTIVITY_TYPES,
    )


def request(activity_type="conversation_completed", actor_type="budly_service", idempotency_key="conversation-completed:C-TEST-001", properties=None, **changes):
    source_type = actor_type if actor_type in {"budly_service", "administrator", "system_service", "test_harness"} else "budly_service"
    values = {
        "request_id": str(uuid4()), "correlation_id": str(uuid4()),
        "actor": Actor("budly-test", actor_type), "capability": CapabilityRef("activity.record", "1.0"),
        "purpose": "interaction_recording", "channel": "website_chat", "environment": "prototype",
        "input": ActivityRecordInput(
            activity_type, SubjectRef("synthetic_person", "P-TEST-001"), SourceRef(source_type, "budly-test"),
            OCCURRED_AT, idempotency_key, dict(properties or {"conversation_id": "C-TEST-001"}), "VERIFIED_OPERATIONAL_FACT",
        ),
    }
    values.update(changes)
    return ToolRequest(**values)


def gateway(*, enabled=True, health=ToolHealth.HEALTHY, fail_write=False, fail_audit=False):
    registry = ToolRegistry(CapabilityDefinition(), LocalKnowledgeAdapter(list(KNOWLEDGE_FIXTURES)))
    registry.register(metrics_definition(), LocalOperationalMetricsAdapter(list(METRIC_FIXTURES)))
    store = InMemoryActivityStore()
    adapter = LocalActivityAdapter(store, state=health, fail_write=fail_write)
    registry.register(activity_definition(enabled), adapter)
    audit = AuditSink(fail=fail_audit)
    return ToolGateway(registry, audit), adapter, store, audit


class TGP03AcceptanceTests(unittest.TestCase):
    def test_t01_authorized_activity_creates_exactly_one_record(self):
        gw, _, store, audit = gateway(); result = gw.execute(request())
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(store.count(), 1)
        self.assertEqual(len(audit.events), 1)
        self.assertEqual(audit.events[0].activity_id, result.result["activity_id"])
        self.assertTrue(result.result["recorded"])

    def test_t02_unknown_actor(self):
        gw, adapter, store, _ = gateway(); result = gw.execute(request(actor_type="anonymous_actor"))
        self.assertEqual(result.error["classification"], ErrorClass.UNKNOWN_ACTOR.value)
        self.assertEqual(store.count(), 0)
        self.assertIsNone(adapter.last_context)

    def test_t03_production_environment(self):
        gw, adapter, store, _ = gateway(); result = gw.execute(request(environment="production"))
        self.assertEqual(result.error["classification"], ErrorClass.ENVIRONMENT_DENIED.value)
        self.assertEqual(store.count(), 0)
        self.assertIsNone(adapter.last_context)

    def test_t04_unknown_capability(self):
        gw, _, store, _ = gateway(); result = gw.execute(request(capability=CapabilityRef("unknown.write", "1.0")))
        self.assertEqual(result.error["classification"], ErrorClass.UNKNOWN_CAPABILITY.value)
        self.assertEqual(store.count(), 0)

    def test_t05_unauthorized_activity_type(self):
        gw, _, store, _ = gateway(); result = gw.execute(request(activity_type="purchase_completed"))
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.DENIED, ErrorClass.ACTIVITY_TYPE_NOT_AUTHORIZED.value))
        self.assertEqual(store.count(), 0)

    def test_t06_malformed_input(self):
        gw, adapter, store, _ = gateway(); raw = self.raw_request(); raw["input"].pop("subject")
        result = gw.execute_raw(raw)
        self.assertEqual(result.error["classification"], ErrorClass.INPUT_VALIDATION_FAILED.value)
        self.assertEqual(store.count(), 0)
        self.assertIsNone(adapter.last_context)

    def test_t07_missing_idempotency_key(self):
        gw, _, store, _ = gateway(); result = gw.execute(request(idempotency_key=""))
        self.assertEqual(result.error["classification"], ErrorClass.IDEMPOTENCY_KEY_REQUIRED.value)
        self.assertEqual(store.count(), 0)

    def test_t08_exact_duplicate(self):
        gw, _, store, audit = gateway(); req = request()
        first, second = gw.execute(req), gw.execute(req)
        self.assertEqual(first.status, ResultStatus.SUCCESS)
        self.assertEqual(second.status, ResultStatus.SUCCESS)
        self.assertEqual(first.result["activity_id"], second.result["activity_id"])
        self.assertEqual((second.result["recorded"], second.result["duplicate"]), (False, True))
        self.assertEqual(store.count(), 1)
        self.assertEqual(audit.events[-1].idempotency_decision, "DUPLICATE")

    def test_t09_idempotency_conflict(self):
        gw, _, store, _ = gateway(); first = request()
        gw.execute(first)
        conflict = request(idempotency_key=first.input.idempotency_key, properties={"conversation_id": "C-TEST-002"})
        result = gw.execute(conflict)
        self.assertEqual(result.error["classification"], ErrorClass.IDEMPOTENCY_CONFLICT.value)
        self.assertEqual(store.count(), 1)

    def test_t10_correlation_preservation(self):
        gw, _, store, audit = gateway(); req = request(); result = gw.execute(req)
        activity = store.get(result.result["activity_id"])
        self.assertEqual(req.correlation_id, result.correlation_id)
        self.assertEqual(req.correlation_id, activity.correlation_id)
        self.assertEqual(req.correlation_id, audit.events[-1].correlation_id)

    def test_t11_caller_cannot_select_storage_provider(self):
        gw, adapter, store, _ = gateway(); raw = self.raw_request(); raw["provider"] = "supabase"
        with self.assertRaises(RequestValidationError): ToolRequest.from_dict(raw)
        self.assertEqual(adapter.tool_id, "local_activity_store")
        self.assertIsNone(adapter.last_context)
        self.assertEqual(store.count(), 0)

    def test_t12_context_pii_injection(self):
        gw, adapter, store, _ = gateway(); raw = self.raw_request()
        raw["input"]["properties"].update({"customer_email": "synthetic@example.invalid", "phone": "000", "address": "synthetic", "raw_transcript": "synthetic"})
        result = gw.execute_raw(raw)
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertIsNone(adapter.last_context)
        self.assertEqual(store.count(), 0)
        self.assertNotIn("synthetic@example.invalid", json.dumps(result.to_dict()))

    def test_t13_inference_cannot_become_verified_fact(self):
        gw, _, store, _ = gateway(); result = gw.execute(request(properties={"conversation_id": "C-TEST-001", "inferred": True}))
        self.assertEqual(result.error["classification"], ErrorClass.FACT_CLASSIFICATION_INVALID.value)
        self.assertEqual(store.count(), 0)

    def test_t14_consent_cannot_be_changed(self):
        neighbor = {"consent": "not_granted"}; before = dict(neighbor)
        gw, _, store, _ = gateway(); result = gw.execute(request(activity_type="consent_granted"))
        self.assertEqual(result.error["classification"], ErrorClass.ACTIVITY_TYPE_NOT_AUTHORIZED.value)
        self.assertEqual(neighbor, before)
        self.assertEqual(store.count(), 0)

    def test_t15_lifecycle_cannot_be_changed(self):
        neighbor = {"lifecycle": "visitor"}; before = dict(neighbor)
        gw, _, store, _ = gateway(); result = gw.execute(request(properties={"conversation_id": "C-TEST-001", "lifecycle_stage": "member"}))
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(neighbor, before)
        self.assertEqual(store.count(), 0)

    def test_t16_purchase_truth_cannot_be_changed(self):
        neighbor = {"purchased": False}; before = dict(neighbor)
        gw, _, store, _ = gateway(); result = gw.execute(request(activity_type="purchase_completed"))
        self.assertEqual(result.error["classification"], ErrorClass.ACTIVITY_TYPE_NOT_AUTHORIZED.value)
        self.assertEqual(neighbor, before)
        self.assertEqual(store.count(), 0)

    def test_t17_existing_activity_cannot_be_mutated(self):
        gw, _, store, _ = gateway(); created = gw.execute(request())
        existing = store.get(created.result["activity_id"]); before = asdict(existing)
        result = gw.execute(request(idempotency_key="mutation-attempt", properties={"activity_id": existing.activity_id}))
        self.assertEqual(result.status, ResultStatus.DENIED)
        self.assertEqual(asdict(store.get(existing.activity_id)), before)
        self.assertEqual(store.count(), 1)

    def test_t18_simulated_write_failure(self):
        gw, _, store, _ = gateway(fail_write=True); result = gw.execute(request())
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.FAILED, ErrorClass.WRITE_FAILED.value))
        self.assertEqual(store.count(), 0)

    def test_t19_audit_failure_rolls_back(self):
        gw, _, store, audit = gateway(fail_audit=True); result = gw.execute(request())
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.FAILED, ErrorClass.AUDIT_FAILURE.value))
        self.assertEqual(store.count(), 0)
        self.assertEqual(audit.events, [])

    def test_t20_tg_p01_and_tg_p02_regression_preservation(self):
        from tests.test_tg_p01_tool_gateway import TGP01AcceptanceTests
        from tests.test_tg_p02_operational_metrics import TGP02AcceptanceTests
        for case in (TGP01AcceptanceTests, TGP02AcceptanceTests):
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(case)
            result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
            self.assertEqual(result.testsRun, 20)
            self.assertTrue(result.wasSuccessful())

    @staticmethod
    def raw_request():
        req = request()
        return {
            "request_id": req.request_id, "correlation_id": req.correlation_id,
            "actor": {"actor_id": req.actor.actor_id, "actor_type": req.actor.actor_type},
            "capability": {"capability_id": req.capability.capability_id, "capability_version": req.capability.capability_version},
            "purpose": req.purpose, "channel": req.channel, "environment": req.environment,
            "input": {
                "activity_type": req.input.activity_type,
                "subject": {"subject_type": req.input.subject.subject_type, "subject_id": req.input.subject.subject_id},
                "source": {"source_type": req.input.source.source_type, "source_id": req.input.source.source_id},
                "occurred_at": req.input.occurred_at, "idempotency_key": req.input.idempotency_key,
                "properties": dict(req.input.properties), "fact_classification": req.input.fact_classification,
            },
        }


if __name__ == "__main__":
    unittest.main()
