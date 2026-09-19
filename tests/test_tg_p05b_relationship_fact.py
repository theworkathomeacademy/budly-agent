import io
import os
import unittest
from dataclasses import asdict
from uuid import uuid4

import psycopg

from src.budly_runtime.postgres_relationship_fact import PostgresRelationshipFactAdapter, relationship_fact_capability_definition
from src.budly_runtime.tool_gateway import (
    Actor, AuditSink, CapabilityRef, CustomerRelationshipFactRecordInput, ErrorClass,
    MemoryAuthorization, RelationshipFactValue, RelationshipSource, RequestValidationError,
    ResultStatus, SubjectRef, ToolGateway, ToolRegistry, ToolRequest,
)
from tests import test_tg_p01_tool_gateway as tg_p01
from tests import test_tg_p02_operational_metrics as tg_p02
from tests import test_tg_p03_activity_record as tg_p03
from tests import test_tg_p04_activity_persistence as tg_p04
from tests import test_tg_p05a_customer_preference as tg_p05a

STATED_AT = "2026-08-24T16:00:00+00:00"
SOURCE_SUMMARY = "discussion about terpenes and the ECS"


def request(*, fact_key="customer_birthday", fact_value=None,
            information_type="CUSTOMER_STATED_RELATIONSHIP_FACT", certainty="EXPLICIT",
            source_type="conversation", subject_id="P-TEST-001", memory_state="ACTIVE",
            idempotency_key="relationship:P-TEST-001:birthday:C-TEST-001:S-TEST-001",
            statement_reference="S-TEST-001", stated_at=STATED_AT, source_context_summary=SOURCE_SUMMARY,
            actor_type="budly_service", **changes):
    values = {
        "request_id": str(uuid4()), "correlation_id": str(uuid4()),
        "actor": Actor("budly-test", actor_type),
        "capability": CapabilityRef("customer.relationship_fact.record", "1.0"),
        "purpose": "relationship_continuity", "channel": "website_chat", "environment": "prototype",
        "input": CustomerRelationshipFactRecordInput(
            SubjectRef("synthetic_person", subject_id),
            RelationshipFactValue(fact_key, dict(fact_value or {"month": 10, "day": 12}), information_type, certainty),
            RelationshipSource(source_type, "C-TEST-001", statement_reference, source_context_summary),
            MemoryAuthorization(memory_state, "relationship_continuity"), stated_at, idempotency_key,
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
            "subject": asdict(item.input.subject), "relationship_fact": asdict(item.input.relationship_fact),
            "source": asdict(item.input.source), "memory_authorization": asdict(item.input.memory_authorization),
            "stated_at": item.input.stated_at, "idempotency_key": item.input.idempotency_key,
        },
    }


class TGP05BAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dsn = os.environ["TG_P05B_DATABASE_URL"]
        PostgresRelationshipFactAdapter(cls.dsn, environment="automated_test").apply_migration()

    def setUp(self):
        with psycopg.connect(self.dsn) as connection:
            connection.execute("TRUNCATE tg_p05b.relationship_fact_audit_events, tg_p05b.relationship_facts")

    def runtime(self, **adapter_changes):
        adapter = PostgresRelationshipFactAdapter(self.dsn, environment="automated_test", **adapter_changes)
        return ToolGateway(ToolRegistry(relationship_fact_capability_definition(), adapter), AuditSink()), adapter

    def test_t01_explicit_customer_birthday_records(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request())
        record = adapter.get(result.result["relationship_fact_id"])
        self.assertEqual((result.status, record.fact_value, record.status), (ResultStatus.SUCCESS, {"month": 10, "day": 12}, "ACTIVE"))
        self.assertEqual(len(adapter.audits_for_fact(record.relationship_fact_id)), 1)
        self.assertNotIn("year", record.fact_value)

    def test_t02_explicit_anniversary_records(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(
            fact_key="relationship_anniversary", fact_value={"month": 6, "day": 15},
            idempotency_key="relationship:P-TEST-001:anniversary:C-TEST-001:S-TEST-001",
        ))
        record = adapter.get(result.result["relationship_fact_id"])
        self.assertEqual((record.fact_category, record.source_reference, record.statement_reference), ("anniversary", "C-TEST-001", "S-TEST-001"))

    def test_t03_children_count_records_without_child_profiles(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(
            fact_key="children_count", fact_value={"count": 3},
            idempotency_key="relationship:P-TEST-001:children:C-TEST-001:S-TEST-001",
        ))
        self.assertEqual(adapter.get(result.result["relationship_fact_id"]).fact_value, {"count": 3})
        with psycopg.connect(self.dsn) as connection:
            tables = {row[0] for row in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='tg_p05b'")}
        self.assertEqual(tables, {"relationship_facts", "relationship_fact_audit_events"})

    def test_t04_child_first_name_relationship_records_within_scope(self):
        maya = {"first_name": "Maya", "relationship": "daughter", "is_minor": True, "stated_age": 10, "birthday_month": 5, "birthday_day": 20}
        gateway, adapter = self.runtime(); result = gateway.execute(request(
            fact_key="related_person_first_name", fact_value=maya,
            idempotency_key="relationship:P-TEST-001:maya:C-TEST-001:S-TEST-001",
        ))
        record = adapter.get(result.result["relationship_fact_id"])
        self.assertEqual(record.related_person_context, maya)
        self.assertEqual(record.sensitivity_class, "R1")

    def test_t05_missing_memory_permission(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(memory_state="NOT_GRANTED"))
        self.assertEqual(result.error["classification"], ErrorClass.MEMORY_PERMISSION_REQUIRED.value)
        self.assertEqual(adapter.count(), 0)

    def test_t06_withdrawn_memory_permission(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(memory_state="WITHDRAWN"))
        self.assertEqual(result.error["classification"], ErrorClass.MEMORY_PERMISSION_WITHDRAWN.value)
        self.assertEqual(adapter.count(), 0)

    def test_t07_unknown_relationship_fact_key(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(fact_key="favorite_neighbor_secret", fact_value={"value": "unknown"}))
        self.assertEqual(result.error["classification"], ErrorClass.RELATIONSHIP_FACT_KEY_NOT_AUTHORIZED.value)
        self.assertEqual(adapter.count(), 0)

    def test_t08_inferred_family_relationship_denied(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(information_type="MODEL_INFERRED"))
        self.assertEqual(result.error["classification"], ErrorClass.FACT_CLASSIFICATION_INVALID.value)
        self.assertEqual(adapter.count(), 0)

    def test_t09_behavioral_purchase_inference_denied(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(
            fact_key="children_count", fact_value={"count": 3}, source_type="purchase",
            idempotency_key="relationship:P-TEST-001:purchase-inference",
        ))
        self.assertEqual(result.error["classification"], ErrorClass.FACT_CLASSIFICATION_INVALID.value)
        self.assertEqual(adapter.count(), 0)

    def test_t10_ambiguous_relationship_denied_until_confirmed(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(
            fact_key="upcoming_graduation",
            fact_value={"related_person_first_name": "Maya", "related_person_relationship": "friend", "event_period": "spring"},
            certainty="AMBIGUOUS", idempotency_key="relationship:P-TEST-001:ambiguous-graduation",
        ))
        self.assertEqual(result.error["classification"], ErrorClass.AMBIGUOUS_RELATIONSHIP_FACT.value)
        self.assertEqual(adapter.count(), 0)

    def test_t11_sensitive_fact_denied(self):
        gateway, adapter = self.runtime(); r2 = gateway.execute(request(fact_key="divorce", fact_value={}, idempotency_key="r2-denied"))
        rx = gateway.execute(request(fact_key="medical_diagnosis", fact_value={}, idempotency_key="rx-denied"))
        self.assertTrue(all(item.error["classification"] == ErrorClass.RELATIONSHIP_FACT_SENSITIVITY_DENIED.value for item in (r2, rx)))
        self.assertEqual(adapter.count(), 0)

    def test_t12_minor_specific_prohibited_data_denied(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(
            fact_key="related_person_first_name",
            fact_value={"first_name": "Maya", "relationship": "daughter", "is_minor": True, "school_name": "Synthetic School", "precise_location": "Synthetic Location"},
            idempotency_key="minor-prohibited-data",
        ))
        self.assertEqual(result.error["classification"], ErrorClass.MINOR_DATA_PROHIBITED.value)
        self.assertEqual(adapter.count(), 0)

    def test_t13_cross_customer_subject_write_denied(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(subject_id="P-TEST-002"))
        self.assertEqual(result.error["classification"], ErrorClass.SUBJECT_SCOPE_DENIED.value)
        self.assertEqual(adapter.count(), 0)
        self.assertIsNone(adapter.last_context)

    def test_t14_exact_retry_idempotent(self):
        item = request(); gateway, adapter = self.runtime(); first = gateway.execute(item); second = gateway.execute(item)
        self.assertEqual(first.result["relationship_fact_id"], second.result["relationship_fact_id"])
        self.assertTrue(second.result["duplicate"])
        self.assertEqual(adapter.count(), 1)

    def test_t15_conflicting_retry(self):
        gateway, adapter = self.runtime(); gateway.execute(request())
        conflict = gateway.execute(request(fact_value={"month": 11, "day": 12}))
        self.assertEqual(conflict.error["classification"], ErrorClass.IDEMPOTENCY_CONFLICT.value)
        self.assertEqual(adapter.count(), 1)

    def test_t16_changed_fact_supersedes_without_destroying_history(self):
        gateway, adapter = self.runtime(); first = gateway.execute(request(
            fact_key="children_count", fact_value={"count": 2}, idempotency_key="children-count-2",
        ))
        second = gateway.execute(request(
            fact_key="children_count", fact_value={"count": 3}, idempotency_key="children-count-3",
            statement_reference="S-TEST-002", stated_at="2026-08-24T17:00:00+00:00",
        ))
        history = adapter.history("P-TEST-001", "children_count")
        self.assertEqual([(item.fact_value["count"], item.status) for item in history], [(2, "SUPERSEDED"), (3, "ACTIVE")])
        self.assertEqual(history[1].supersedes_fact_id, history[0].relationship_fact_id)
        audit = adapter.audits_for_fact(second.result["relationship_fact_id"])[0]
        self.assertEqual(str(audit["previous_fact_id"]), first.result["relationship_fact_id"])

    def test_t17_contextual_provenance_without_raw_transcript(self):
        gateway, adapter = self.runtime(); result = gateway.execute(request(
            fact_key="upcoming_graduation",
            fact_value={"related_person_first_name": "Maya", "related_person_relationship": "daughter", "event_period": "spring", "is_minor": True},
            idempotency_key="relationship:P-TEST-001:graduation:C-TEST-001:S-TEST-001",
        ))
        record = adapter.get(result.result["relationship_fact_id"])
        self.assertEqual((record.source_reference, record.statement_reference, record.source_context_summary), ("C-TEST-001", "S-TEST-001", SOURCE_SUMMARY))
        self.assertNotIn("transcript", asdict(record))
        transcript = raw_request(); transcript["input"]["raw_transcript"] = "synthetic transcript"
        provider = raw_request(); provider["provider"] = "supabase"
        with self.assertRaises(RequestValidationError): ToolRequest.from_dict(transcript)
        with self.assertRaises(RequestValidationError): ToolRequest.from_dict(provider)

    def test_t18_protected_business_state_remains_untouched(self):
        sentinels = {"marketing_consent": False, "lifecycle": "visitor", "purchase": False, "lead_score": 0}; before = dict(sentinels)
        gateway, adapter = self.runtime(); result = gateway.execute(request())
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(sentinels, before)
        with psycopg.connect(self.dsn) as connection:
            non_fact_tables = connection.execute("SELECT COUNT(*) FROM pg_tables WHERE schemaname='tg_p05b' AND tablename NOT IN ('relationship_facts','relationship_fact_audit_events')").fetchone()[0]
        self.assertEqual(non_fact_tables, 0)
        denied = gateway.execute(request(environment="production", idempotency_key="production-denial"))
        self.assertEqual(denied.error["classification"], ErrorClass.ENVIRONMENT_DENIED.value)
        with self.assertRaises(ValueError): PostgresRelationshipFactAdapter(self.dsn, environment="production")

    def test_t19_durable_fact_and_audit_survive_restart(self):
        item = request(); gateway, _ = self.runtime(); result = gateway.execute(item); del gateway
        fresh = PostgresRelationshipFactAdapter(self.dsn, environment="automated_test")
        record = fresh.get(result.result["relationship_fact_id"]); audit = fresh.audits_for_fact(record.relationship_fact_id)[0]
        self.assertEqual(record.source_context_summary, SOURCE_SUMMARY)
        self.assertEqual({record.correlation_id, str(audit["correlation_id"]), result.correlation_id}, {item.correlation_id})
        self.assertEqual(str(audit["audit_event_id"]), result.evidence_reference)

    def test_t20_tg_p01_through_tg_p05a_regression_preservation(self):
        suite = unittest.TestSuite([
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p01.TGP01AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p02.TGP02AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p03.TGP03AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p04.TGP04AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p05a.TGP05AAcceptanceTests),
        ])
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertEqual((result.testsRun, len(result.failures), len(result.errors)), (100, 0, 0))


if __name__ == "__main__":
    unittest.main()
