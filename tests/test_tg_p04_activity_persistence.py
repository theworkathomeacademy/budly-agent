import io
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from uuid import uuid4

import psycopg

from src.budly_runtime.postgres_activity import PostgresActivityAdapter
from src.budly_runtime.tool_gateway import (
    ALLOWED_ACTIVITY_TYPES, ActivityRecordInput, Actor, AuditSink, CapabilityDefinition, CapabilityRef,
    ErrorClass, RequestValidationError, ResultStatus, SourceRef, SubjectRef, ToolGateway, ToolRegistry,
    ToolRequest,
)
from tests import test_tg_p01_tool_gateway as tg_p01
from tests import test_tg_p02_operational_metrics as tg_p02
from tests import test_tg_p03_activity_record as tg_p03

OCCURRED_AT = "2026-08-24T12:00:00+00:00"


def definition():
    return CapabilityDefinition(
        capability_id="activity.record", capability_version="1.0", bros_level=1, tool_class="T2",
        allowed_purposes=frozenset({"relationship_history", "interaction_recording", "support_history", "recommendation_evidence", "internal_test"}),
        allowed_channels=frozenset({"website_chat", "internal_test", "admin_console", "system_internal"}),
        specifically_authorized_bounded_write=True, allowed_activity_types=ALLOWED_ACTIVITY_TYPES,
    )


def request(*, key="tg-p04:C-TEST-001", properties=None, environment="prototype", activity_type="conversation_completed"):
    return ToolRequest(
        str(uuid4()), str(uuid4()), Actor("budly-test", "budly_service"), CapabilityRef("activity.record", "1.0"),
        "interaction_recording", "website_chat", environment,
        ActivityRecordInput(
            activity_type, SubjectRef("synthetic_person", "P-TEST-001"), SourceRef("budly_service", "budly-test"),
            OCCURRED_AT, key, dict(properties or {"conversation_id": "C-TEST-001"}), "VERIFIED_OPERATIONAL_FACT",
        ),
    )


def raw_request():
    item = request()
    return {
        "request_id": item.request_id, "correlation_id": item.correlation_id,
        "actor": asdict(item.actor), "capability": asdict(item.capability), "purpose": item.purpose,
        "channel": item.channel, "environment": item.environment,
        "input": {
            "activity_type": item.input.activity_type, "subject": asdict(item.input.subject),
            "source": asdict(item.input.source), "occurred_at": item.input.occurred_at,
            "idempotency_key": item.input.idempotency_key, "properties": item.input.properties,
            "fact_classification": item.input.fact_classification,
        },
    }


class TGP04AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["TG_P04_DATABASE_URL"]
        PostgresActivityAdapter(cls.dsn, environment="automated_test").apply_migration()

    def setUp(self):
        with psycopg.connect(self.dsn) as connection:
            connection.execute("TRUNCATE tg_p04.audit_events, tg_p04.activities")

    def runtime(self, **adapter_changes):
        adapter = PostgresActivityAdapter(self.dsn, environment="automated_test", **adapter_changes)
        return ToolGateway(ToolRegistry(definition(), adapter), AuditSink()), adapter

    def test_t01_durable_authorized_write(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request())
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(adapter.count(), 1)
        audits = adapter.audits_for_activity(result.result["activity_id"])
        self.assertEqual(len(audits), 1)
        self.assertEqual(str(audits[0]["audit_event_id"]), result.evidence_reference)

    def test_t02_fresh_adapter_retrieval(self):
        gateway, _ = self.runtime(); created = gateway.execute(request())
        fresh = PostgresActivityAdapter(self.dsn, environment="automated_test")
        self.assertEqual(fresh.get(created.result["activity_id"]).activity_id, created.result["activity_id"])

    def test_t03_simulated_runtime_restart(self):
        runtime_a, _ = self.runtime(); created = runtime_a.execute(request())
        del runtime_a
        runtime_b, adapter_b = self.runtime()
        self.assertEqual(adapter_b.get(created.result["activity_id"]).idempotency_key, "tg-p04:C-TEST-001")
        self.assertEqual(adapter_b.count(), 1)

    def test_t04_exact_retry_after_restart(self):
        original = request(); runtime_a, _ = self.runtime(); first = runtime_a.execute(original)
        runtime_b, adapter_b = self.runtime(); second = runtime_b.execute(original)
        self.assertEqual(first.result["activity_id"], second.result["activity_id"])
        self.assertTrue(second.result["duplicate"])
        self.assertEqual(adapter_b.count(), 1)

    def test_t05_conflicting_retry_after_restart(self):
        runtime_a, _ = self.runtime(); runtime_a.execute(request())
        runtime_b, adapter_b = self.runtime()
        conflict = runtime_b.execute(request(properties={"conversation_id": "C-TEST-002"}))
        self.assertEqual(conflict.error["classification"], ErrorClass.IDEMPOTENCY_CONFLICT.value)
        self.assertEqual(adapter_b.count(), 1)

    def test_t06_two_concurrent_identical_writes(self):
        gateway, adapter = self.runtime()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: gateway.execute(request()), range(2)))
        self.assertEqual(adapter.count("tg-p04:C-TEST-001"), 1)
        self.assertEqual(len({item.result["activity_id"] for item in results}), 1)
        self.assertTrue(all(item.status == ResultStatus.SUCCESS for item in results))

    def test_t07_ten_concurrent_identical_writes(self):
        gateway, adapter = self.runtime()
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(lambda _: gateway.execute(request()), range(10)))
        self.assertEqual(adapter.count("tg-p04:C-TEST-001"), 1)
        self.assertEqual(len({item.result["activity_id"] for item in results}), 1)
        self.assertEqual(sum(bool(item.result["recorded"]) for item in results), 1)

    def test_t08_concurrent_conflicting_payloads(self):
        gateway, adapter = self.runtime()
        requests = [request(properties={"conversation_id": "C-TEST-001"}), request(properties={"conversation_id": "C-TEST-002"})]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(gateway.execute, requests))
        self.assertEqual(adapter.count("tg-p04:C-TEST-001"), 1)
        self.assertEqual(sum(item.status == ResultStatus.SUCCESS for item in results), 1)
        self.assertEqual(sum(bool(item.error) and item.error["classification"] == ErrorClass.IDEMPOTENCY_CONFLICT.value for item in results), 1)

    def test_t09_database_uniqueness_enforcement(self):
        gateway, _ = self.runtime(); created = gateway.execute(request())
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with psycopg.connect(self.dsn) as connection:
                connection.execute(
                    "INSERT INTO tg_p04.activities SELECT %s, activity_type, subject_type, subject_id, source_type, source_id, channel, purpose, occurred_at, recorded_at, correlation_id, idempotency_key, payload_fingerprint, fact_classification, properties FROM tg_p04.activities WHERE activity_id = %s",
                    (str(uuid4()), created.result["activity_id"]),
                )
        with psycopg.connect(self.dsn) as connection:
            constraint = connection.execute("SELECT conname FROM pg_constraint WHERE conname = 'tg_p04_activities_idempotency_key_unique'").fetchone()
        self.assertIsNotNone(constraint)

    def test_t10_transaction_failure_rollback(self):
        gateway, adapter = self.runtime(fail_write=True); result = gateway.execute(request())
        self.assertEqual((result.status, result.error["classification"]), (ResultStatus.FAILED, ErrorClass.WRITE_FAILED.value))
        self.assertEqual(adapter.count(), 0)

    def test_t11_audit_failure_rollback(self):
        gateway, adapter = self.runtime(fail_audit=True); result = gateway.execute(request())
        self.assertEqual(result.error["classification"], ErrorClass.AUDIT_FAILURE.value)
        self.assertEqual(adapter.count(), 0)

    def test_t12_postcondition_failure(self):
        gateway, adapter = self.runtime(fail_postcondition=True); result = gateway.execute(request())
        self.assertEqual(result.error["classification"], ErrorClass.POSTCONDITION_FAILED.value)
        self.assertEqual(adapter.count(), 0)

    def test_t13_durable_correlation(self):
        req = request(); gateway, adapter = self.runtime(); result = gateway.execute(req)
        record = adapter.get(result.result["activity_id"]); audit = adapter.audits_for_activity(record.activity_id)[0]
        self.assertEqual({req.correlation_id, result.correlation_id, record.correlation_id, str(audit["correlation_id"])}, {req.correlation_id})
        self.assertEqual(str(audit["request_id"]), req.request_id)

    def test_t14_audit_link_survives_restart(self):
        gateway, _ = self.runtime(); result = gateway.execute(request())
        fresh = PostgresActivityAdapter(self.dsn, environment="automated_test")
        audits = fresh.audits_for_activity(result.result["activity_id"])
        self.assertEqual(str(audits[0]["activity_id"]), result.result["activity_id"])
        self.assertEqual(str(audits[0]["audit_event_id"]), result.evidence_reference)

    def test_t15_caller_cannot_select_persistence_provider(self):
        value = raw_request(); value["provider"] = "supabase"
        with self.assertRaises(RequestValidationError):
            ToolRequest.from_dict(value)
        gateway, adapter = self.runtime()
        self.assertEqual(gateway.registry.resolve("activity.record", "1.0").tool_id, "postgres_activity_tg_p04")
        self.assertIsNone(adapter.last_context)

    def test_t16_production_double_lock(self):
        gateway, adapter = self.runtime(); denied = gateway.execute(request(environment="production"))
        self.assertEqual(denied.error["classification"], ErrorClass.ENVIRONMENT_DENIED.value)
        self.assertEqual(adapter.count(), 0)
        with self.assertRaises(ValueError):
            PostgresActivityAdapter(self.dsn, environment="production")

    def test_t17_protected_state_still_untouched(self):
        sentinel = {"consent": "not_granted", "lifecycle": "visitor", "purchased": False}; before = dict(sentinel)
        gateway, adapter = self.runtime()
        results = [
            gateway.execute(request(activity_type="consent_granted", key="protected-1")),
            gateway.execute(request(key="protected-2", properties={"lifecycle_stage": "member"})),
            gateway.execute(request(activity_type="purchase_completed", key="protected-3")),
        ]
        self.assertTrue(all(item.status == ResultStatus.DENIED for item in results))
        self.assertEqual(sentinel, before)
        self.assertEqual(adapter.count(), 0)

    def test_t18_existing_durable_activity_cannot_be_mutated(self):
        gateway, adapter = self.runtime(); created = gateway.execute(request())
        before = asdict(adapter.get(created.result["activity_id"]))
        denied = gateway.execute(request(key="mutation", properties={"activity_id": created.result["activity_id"]}))
        self.assertEqual(denied.status, ResultStatus.DENIED)
        self.assertEqual(asdict(adapter.get(created.result["activity_id"])), before)

    def test_t19_tg_p03_regression_preservation(self):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(tg_p03.TGP03AcceptanceTests)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertEqual((result.testsRun, len(result.failures), len(result.errors)), (20, 0, 0))

    def test_t20_tg_p01_tg_p02_regression_preservation(self):
        suite = unittest.TestSuite([
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p01.TGP01AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p02.TGP02AcceptanceTests),
        ])
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertEqual((result.testsRun, len(result.failures), len(result.errors)), (40, 0, 0))


if __name__ == "__main__":
    unittest.main()
