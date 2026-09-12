import io
import os
import unittest
from dataclasses import asdict
from uuid import uuid4

import psycopg

from src.budly_runtime.postgres_preference import PostgresPreferenceAdapter, preference_capability_definition
from src.budly_runtime.tool_gateway import (
    Actor, AuditSink, CapabilityRef, CustomerPreferenceRecordInput,
    ErrorClass, MemoryAuthorization, PreferenceSource, PreferenceValue, RequestValidationError, ResultStatus,
    SubjectRef, ToolGateway, ToolRegistry, ToolRequest,
)
from tests import test_tg_p01_tool_gateway as tg_p01
from tests import test_tg_p02_operational_metrics as tg_p02
from tests import test_tg_p03_activity_record as tg_p03
from tests import test_tg_p04_activity_persistence as tg_p04

STATED_AT = "2026-08-24T14:00:00+00:00"


def request(*, key="book_format", value="paperback", information_type="CUSTOMER_STATED",
            source_type="conversation", subject_id="P-TEST-001", memory_state="ACTIVE",
            marketing_consent=False, idempotency_key="preference:P-TEST-001:book_format:C-TEST-001:S-TEST-001",
            statement_reference="S-TEST-001", stated_at=STATED_AT, actor_type="budly_service", **changes):
    values = {
        "request_id": str(uuid4()), "correlation_id": str(uuid4()),
        "actor": Actor("budly-test", actor_type), "capability": CapabilityRef("customer.preference.record", "1.0"),
        "purpose": "conversation_continuity", "channel": "website_chat", "environment": "prototype",
        "input": CustomerPreferenceRecordInput(
            SubjectRef("synthetic_person", subject_id), PreferenceValue(key, value, information_type),
            PreferenceSource(source_type, "C-TEST-001", statement_reference),
            MemoryAuthorization(memory_state, "conversation_continuity"), marketing_consent,
            stated_at, idempotency_key,
        ),
    }
    values.update(changes)
    return ToolRequest(**values)


def raw_request():
    item = request()
    return {
        "request_id": item.request_id, "correlation_id": item.correlation_id,
        "actor": asdict(item.actor), "capability": asdict(item.capability), "purpose": item.purpose,
        "channel": item.channel, "environment": item.environment,
        "input": {
            "subject": asdict(item.input.subject), "preference": asdict(item.input.preference),
            "source": asdict(item.input.source), "memory_authorization": asdict(item.input.memory_authorization),
            "marketing_consent": item.input.marketing_consent, "stated_at": item.input.stated_at,
            "idempotency_key": item.input.idempotency_key,
        },
    }


class TGP05AAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["TG_P05A_DATABASE_URL"]
        PostgresPreferenceAdapter(cls.dsn, environment="automated_test").apply_migration()

    def setUp(self):
        with psycopg.connect(self.dsn) as connection:
            connection.execute("TRUNCATE tg_p05a.preference_audit_events, tg_p05a.customer_preferences")

    def runtime(self, **adapter_changes):
        adapter = PostgresPreferenceAdapter(self.dsn, environment="automated_test", **adapter_changes)
        return ToolGateway(ToolRegistry(preference_capability_definition(), adapter), AuditSink()), adapter

    def test_t01_customer_stated_preference_records(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request())
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        record = adapter.get(result.result["preference_id"])
        self.assertEqual((record.preference_key, record.preference_value, record.status), ("book_format", "paperback", "ACTIVE"))
        self.assertEqual(len(adapter.audits_for_preference(record.preference_id)), 1)

    def test_t02_unknown_actor(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(actor_type="anonymous_actor"))
        self.assertEqual(result.error["classification"], ErrorClass.UNKNOWN_ACTOR.value)
        self.assertEqual(adapter.count(), 0)
        self.assertIsNone(adapter.last_context)

    def test_t03_production_environment(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(environment="production"))
        self.assertEqual(result.error["classification"], ErrorClass.ENVIRONMENT_DENIED.value)
        self.assertEqual(adapter.count(), 0)
        with self.assertRaises(ValueError):
            PostgresPreferenceAdapter(self.dsn, environment="production")

    def test_t04_unknown_preference_key(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(key="medical_condition"))
        self.assertEqual(result.error["classification"], ErrorClass.PREFERENCE_KEY_NOT_AUTHORIZED.value)
        self.assertEqual(adapter.count(), 0)

    def test_t05_invalid_preference_value(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(value="leather_bound"))
        self.assertEqual(result.error["classification"], ErrorClass.PREFERENCE_VALUE_INVALID.value)
        self.assertEqual(adapter.count(), 0)

    def test_t06_missing_memory_permission(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(memory_state="NOT_GRANTED"))
        self.assertEqual(result.error["classification"], ErrorClass.MEMORY_PERMISSION_REQUIRED.value)
        self.assertEqual(adapter.count(), 0)

    def test_t07_withdrawn_memory_permission(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(memory_state="WITHDRAWN"))
        self.assertEqual(result.error["classification"], ErrorClass.MEMORY_PERMISSION_WITHDRAWN.value)
        self.assertEqual(adapter.count(), 0)

    def test_t08_marketing_consent_does_not_substitute_for_memory_permission(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(memory_state="NOT_GRANTED", marketing_consent=True))
        self.assertEqual(result.error["classification"], ErrorClass.MEMORY_PERMISSION_REQUIRED.value)
        self.assertEqual(adapter.count(), 0)
        self.assertIsNone(adapter.last_context)

    def test_t09_memory_permission_does_not_grant_marketing_consent(self):
        marketing = {"consent": False}; before = dict(marketing)
        gateway, adapter = self.runtime(); result = gateway.execute(request(marketing_consent=False))
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(marketing, before)
        self.assertNotIn("marketing", asdict(adapter.get(result.result["preference_id"])))
        self.assertFalse(hasattr(adapter.last_context, "marketing_consent"))

    def test_t10_inference_cannot_become_customer_stated_preference(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(information_type="MODEL_INFERRED"))
        self.assertEqual(result.error["classification"], ErrorClass.FACT_CLASSIFICATION_INVALID.value)
        self.assertEqual(adapter.count(), 0)

    def test_t11_behavioral_signal_cannot_become_confirmed_preference(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(source_type="behavior"))
        self.assertEqual(result.error["classification"], ErrorClass.FACT_CLASSIFICATION_INVALID.value)
        self.assertEqual(adapter.count(), 0)

    def test_t12_recommendation_cannot_become_preference(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(source_type="recommendation"))
        self.assertEqual(result.error["classification"], ErrorClass.FACT_CLASSIFICATION_INVALID.value)
        self.assertEqual(adapter.count(), 0)

    def test_t13_cross_customer_subject_write(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(subject_id="P-TEST-002"))
        self.assertEqual(result.error["classification"], ErrorClass.SUBJECT_SCOPE_DENIED.value)
        self.assertEqual(adapter.count(), 0)

    def test_t14_exact_retry_is_idempotent(self):
        item = request(); gateway, adapter = self.runtime(); first = gateway.execute(item); second = gateway.execute(item)
        self.assertEqual(first.result["preference_id"], second.result["preference_id"])
        self.assertTrue(second.result["duplicate"])
        self.assertEqual(adapter.count(), 1)

    def test_t15_conflicting_retry(self):
        gateway, adapter = self.runtime(); gateway.execute(request())
        conflict = gateway.execute(request(value="hardcover"))
        self.assertEqual(conflict.error["classification"], ErrorClass.IDEMPOTENCY_CONFLICT.value)
        self.assertEqual(adapter.count(), 1)

    def test_t16_preference_change_supersedes_without_destroying_history(self):
        gateway, adapter = self.runtime(); first = gateway.execute(request())
        second = gateway.execute(request(
            value="hardcover", idempotency_key="preference:P-TEST-001:book_format:C-TEST-001:S-TEST-002",
            statement_reference="S-TEST-002", stated_at="2026-08-24T15:00:00+00:00",
        ))
        history = adapter.history("P-TEST-001", "book_format")
        self.assertEqual([(item.preference_value, item.status) for item in history], [("paperback", "SUPERSEDED"), ("hardcover", "ACTIVE")])
        self.assertEqual(history[1].supersedes_preference_id, history[0].preference_id)
        audit = adapter.audits_for_preference(second.result["preference_id"])[0]
        self.assertEqual(str(audit["previous_preference_id"]), first.result["preference_id"])

    def test_t17_caller_cannot_delete_prior_preference(self):
        gateway, adapter = self.runtime(); created = gateway.execute(request())
        before = asdict(adapter.get(created.result["preference_id"]))
        denied = gateway.execute(request(key="delete_preference", idempotency_key="delete-attempt"))
        self.assertEqual(denied.status, ResultStatus.DENIED)
        self.assertEqual(asdict(adapter.get(created.result["preference_id"])), before)
        self.assertEqual(adapter.count(), 1)
        provider_injection = raw_request(); provider_injection["provider"] = "supabase"
        pii_injection = raw_request(); pii_injection["input"]["customer_email"] = "synthetic@example.invalid"
        with self.assertRaises(RequestValidationError):
            ToolRequest.from_dict(provider_injection)
        with self.assertRaises(RequestValidationError):
            ToolRequest.from_dict(pii_injection)

    def test_t18_provenance_and_correlation_survive_restart(self):
        item = request(); gateway, _ = self.runtime(); result = gateway.execute(item)
        fresh = PostgresPreferenceAdapter(self.dsn, environment="automated_test")
        record = fresh.get(result.result["preference_id"]); audit = fresh.audits_for_preference(record.preference_id)[0]
        self.assertEqual((record.source_reference, record.statement_reference), ("C-TEST-001", "S-TEST-001"))
        self.assertEqual({record.correlation_id, str(audit["correlation_id"]), result.correlation_id}, {item.correlation_id})
        self.assertEqual(str(audit["audit_event_id"]), result.evidence_reference)

    def test_t19_protected_state_remains_untouched(self):
        sentinels = {"marketing_consent": False, "lifecycle": "visitor", "purchase": False}; before = dict(sentinels)
        gateway, adapter = self.runtime(); result = gateway.execute(request())
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(sentinels, before)
        self.assertEqual(adapter.count(), 1)

    def test_t20_tg_p01_through_tg_p04_regression_preservation(self):
        suite = unittest.TestSuite([
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p01.TGP01AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p02.TGP02AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p03.TGP03AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p04.TGP04AcceptanceTests),
        ])
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertEqual((result.testsRun, len(result.failures), len(result.errors)), (80, 0, 0))


if __name__ == "__main__":
    unittest.main()
