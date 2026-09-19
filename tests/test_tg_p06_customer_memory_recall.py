import io
import json
import os
import unittest
from dataclasses import asdict
from uuid import uuid4

import psycopg

from src.budly_runtime.postgres_memory_recall import PostgresMemoryRecallAdapter, memory_recall_capability_definition
from src.budly_runtime.postgres_preference import PostgresPreferenceAdapter, preference_capability_definition
from src.budly_runtime.postgres_relationship_fact import PostgresRelationshipFactAdapter, relationship_fact_capability_definition
from src.budly_runtime.tool_gateway import (
    Actor, AuditSink, CapabilityRef, CustomerMemoryRetrieveInput, ErrorClass,
    MemoryCurrentContext, MemoryLimits, ResultStatus, SessionMemoryUse, ToolGateway,
    ToolRegistry, ToolRequest, VerifiedMemorySubject, RequestValidationError,
)
from tests import test_tg_p01_tool_gateway as tg_p01
from tests import test_tg_p02_operational_metrics as tg_p02
from tests import test_tg_p03_activity_record as tg_p03
from tests import test_tg_p04_activity_persistence as tg_p04
from tests import test_tg_p05a_customer_preference as tg_p05a
from tests import test_tg_p05b_relationship_fact as tg_p05b


def recall_request(*, subject_id="P-TEST-001", identity_state="VERIFIED", use_state="ACTIVE",
                   storage_state="ACTIVE", marketing=False, purpose="product_assistance",
                   topic="botanical_coloring", intent="product_selection", entities=(), statements=None,
                   priority="NORMAL", mode="PRODUCT_DISCOVERY", explicit=False, challenge=False,
                   functional_limit=5, relational_limit=1, **changes):
    values = {
        "request_id": str(uuid4()), "correlation_id": str(uuid4()),
        "actor": Actor("budly-test", "budly_service"),
        "capability": CapabilityRef("customer.memory.retrieve", "1.0"),
        "purpose": purpose, "channel": "website_chat", "environment": "prototype",
        "input": CustomerMemoryRetrieveInput(
            VerifiedMemorySubject("synthetic_person", subject_id, identity_state),
            SessionMemoryUse(use_state, storage_state, marketing),
            MemoryCurrentContext(topic, intent, tuple(entities), dict(statements or {}), priority, mode, explicit, challenge),
            MemoryLimits(functional_limit, relational_limit),
        ),
    }
    values.update(changes)
    return ToolRequest(**values)


class TGP06AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preference_dsn = os.environ["TG_P05A_DATABASE_URL"]
        cls.relationship_dsn = os.environ["TG_P05B_DATABASE_URL"]
        cls.audit_dsn = os.environ["TG_P06_DATABASE_URL"]
        PostgresPreferenceAdapter(cls.preference_dsn, environment="automated_test").apply_migration()
        PostgresRelationshipFactAdapter(cls.relationship_dsn, environment="automated_test").apply_migration()
        PostgresMemoryRecallAdapter(cls.preference_dsn, cls.relationship_dsn, cls.audit_dsn, environment="automated_test").apply_migration()

    def setUp(self):
        with psycopg.connect(self.preference_dsn) as connection:
            connection.execute("TRUNCATE tg_p05a.preference_audit_events, tg_p05a.customer_preferences")
        with psycopg.connect(self.relationship_dsn) as connection:
            connection.execute("TRUNCATE tg_p05b.relationship_fact_audit_events, tg_p05b.relationship_facts")
        with psycopg.connect(self.audit_dsn) as connection:
            connection.execute("TRUNCATE tg_p06.memory_recall_audit_events")

    def runtime(self):
        adapter = PostgresMemoryRecallAdapter(self.preference_dsn, self.relationship_dsn, self.audit_dsn, environment="automated_test")
        return ToolGateway(ToolRegistry(memory_recall_capability_definition(), adapter), AuditSink()), adapter

    def seed_preference(self, **changes):
        adapter = PostgresPreferenceAdapter(self.preference_dsn, environment="automated_test")
        gateway = ToolGateway(ToolRegistry(preference_capability_definition(), adapter), AuditSink())
        return gateway.execute(tg_p05a.request(**changes))

    def seed_fact(self, **changes):
        adapter = PostgresRelationshipFactAdapter(self.relationship_dsn, environment="automated_test")
        gateway = ToolGateway(ToolRegistry(relationship_fact_capability_definition(), adapter), AuditSink())
        return gateway.execute(tg_p05b.request(**changes))

    def test_t01_verified_customer_retrieves_relevant_preference(self):
        self.seed_preference(); gateway, _ = self.runtime(); result = gateway.execute(recall_request())
        self.assertEqual(result.status, ResultStatus.SUCCESS)
        self.assertEqual(result.result["functional_context"][0]["key"], "book_format")

    def test_t02_unverified_customer_gets_no_protected_memory(self):
        self.seed_preference(); gateway, adapter = self.runtime(); result = gateway.execute(recall_request(identity_state="UNVERIFIED"))
        self.assertEqual(result.error["classification"], ErrorClass.IDENTITY_VERIFICATION_REQUIRED.value)
        self.assertIsNone(adapter.last_context)

    def test_t03_storage_permission_without_session_use_permission(self):
        self.seed_preference(); gateway, _ = self.runtime(); result = gateway.execute(recall_request(use_state="NOT_GRANTED", storage_state="ACTIVE"))
        self.assertEqual(result.error["classification"], ErrorClass.MEMORY_USE_PERMISSION_REQUIRED.value)

    def test_t04_marketing_consent_does_not_grant_recall(self):
        self.seed_preference(); gateway, _ = self.runtime(); result = gateway.execute(recall_request(use_state="NOT_GRANTED", marketing=True))
        self.assertEqual(result.error["classification"], ErrorClass.MEMORY_USE_PERMISSION_REQUIRED.value)
        fresh = gateway.execute(recall_request(use_state="START_FRESH", marketing=True))
        self.assertEqual((fresh.result["functional_context"], fresh.result["relationship_context"]), ([], []))
        self.assertTrue(fresh.result["instructions"]["start_fresh"])

    def test_t05_cross_customer_retrieval_denied(self):
        self.seed_preference(); gateway, adapter = self.runtime(); result = gateway.execute(recall_request(subject_id="P-TEST-002"))
        self.assertEqual(result.error["classification"], ErrorClass.SUBJECT_SCOPE_DENIED.value)
        self.assertIsNone(adapter.last_context)

    def test_t06_withdrawn_memory_excluded(self):
        self.seed_preference(); gateway, _ = self.runtime(); result = gateway.execute(recall_request(use_state="WITHDRAWN"))
        self.assertEqual(result.error["classification"], ErrorClass.MEMORY_PERMISSION_WITHDRAWN.value)

    def test_t07_product_help_retrieves_functional_preference(self):
        self.seed_preference(); gateway, _ = self.runtime(); result = gateway.execute(recall_request())
        item = result.result["functional_context"][0]
        self.assertEqual((item["functional_class"], item["key"], item["value"]), ("FUNCTIONAL", "book_format", "paperback"))

    def test_t08_product_help_excludes_unrelated_relationship_facts(self):
        self.seed_fact(fact_key="related_person_first_name", fact_value={"first_name": "Maya", "relationship": "daughter", "is_minor": True}, idempotency_key="relationship:p06:maya")
        gateway, _ = self.runtime(); result = gateway.execute(recall_request(topic="entourage_effect", intent="education_question"))
        self.assertEqual(result.result["relationship_context"], [])

    def test_t09_functional_preference_can_be_silent_use(self):
        self.seed_preference(key="conversation_style", value="concise", idempotency_key="preference:p06:style")
        gateway, _ = self.runtime(); result = gateway.execute(recall_request())
        item = next(item for item in result.result["functional_context"] if item["key"] == "conversation_style")
        self.assertEqual((item["recall_mode"], item["surface_permission"]), ("SILENT_USE", False))

    def test_t10_functional_history_can_be_contextual_reference(self):
        self.seed_preference(); gateway, _ = self.runtime(); result = gateway.execute(recall_request())
        self.assertEqual(result.result["functional_context"][0]["recall_mode"], "CONTEXTUAL_REFERENCE")

    def test_t11_relational_memory_without_natural_bridge_not_surfaced(self):
        self.seed_fact(fact_key="related_person_first_name", fact_value={"first_name": "Maya", "relationship": "daughter", "is_minor": True}, idempotency_key="relationship:p06:maya")
        gateway, _ = self.runtime(); result = gateway.execute(recall_request(topic="entourage_effect", intent="education_question"))
        self.assertEqual(result.result["relationship_context"], [])

    def test_t12_relational_memory_with_natural_bridge_may_surface(self):
        self.seed_fact(fact_key="upcoming_graduation", fact_value={"related_person_first_name": "Maya", "related_person_relationship": "daughter", "event_period": "spring"}, idempotency_key="relationship:p06:graduation")
        gateway, _ = self.runtime(); result = gateway.execute(recall_request(topic="graduation_gift", intent="gift_for_daughter", entities=("Maya", "daughter")))
        item = result.result["relationship_context"][0]
        self.assertEqual((item["key"], item["recall_mode"], item["permitted_use"]), ("upcoming_graduation", "CONTEXTUAL_REFERENCE", "relationship_continuity_only"))

    def test_t13_explicit_do_you_remember_enables_transparent_recall(self):
        self.seed_preference(); self.seed_fact()
        gateway, _ = self.runtime(); result = gateway.execute(recall_request(purpose="explicit_memory_review", topic="memory_review", intent="show_saved_memory", explicit=True))
        modes = {item["recall_mode"] for item in result.result["functional_context"] + result.result["relationship_context"]}
        self.assertEqual(modes, {"TRANSPARENT_REVIEW"})

    def test_t14_stale_age_event_qualified_or_suppressed(self):
        self.seed_fact(fact_key="related_person_age", fact_value={"first_name": "Maya", "relationship": "daughter", "is_minor": True, "stated_age": 10}, stated_at="2024-01-01T00:00:00+00:00", idempotency_key="relationship:p06:stale-age")
        gateway, _ = self.runtime(); result = gateway.execute(recall_request(purpose="relationship_conversation", topic="maya_age", intent="family_conversation", entities=("Maya",)))
        item = result.result["relationship_context"][0]
        self.assertEqual((item["freshness"], item["surface_permission"], item["qualification"]), ("STALE_REQUIRES_QUALIFICATION", False, "do_not_present_as_current_certainty"))

    def test_t15_sensitive_restricted_memory_never_enters_context(self):
        denied = self.seed_fact(fact_key="medical_diagnosis", fact_value={"condition": "synthetic"}, idempotency_key="relationship:p06:rx")
        self.assertEqual(denied.error["classification"], ErrorClass.RELATIONSHIP_FACT_SENSITIVITY_DENIED.value)
        gateway, _ = self.runtime(); result = gateway.execute(recall_request(purpose="explicit_memory_review", topic="memory_review", intent="show_saved_memory", explicit=True))
        self.assertEqual(result.result["relationship_context"], [])

    def test_t16_memory_budget_prevents_over_retrieval(self):
        seeds = [("book_format", "paperback"), ("content_format", "text"), ("education_style", "concise"), ("conversation_style", "guided"), ("support_style", "self_service"), ("shopping_style", "guided")]
        for index, (key, value) in enumerate(seeds, 1):
            self.seed_preference(key=key, value=value, idempotency_key=f"preference:p06:{index}", statement_reference=f"S-TEST-{index:03d}")
        self.seed_fact(); self.seed_fact(fact_key="relationship_anniversary", fact_value={"month": 6, "day": 15}, idempotency_key="relationship:p06:anniversary", statement_reference="S-TEST-002")
        gateway, _ = self.runtime(); result = gateway.execute(recall_request(purpose="explicit_memory_review", topic="memory_review", intent="show_saved_memory", explicit=True, functional_limit=3, relational_limit=1))
        self.assertLessEqual(len(result.result["functional_context"]), 3)
        self.assertLessEqual(len(result.result["relationship_context"]), 1)

    def test_t17_current_customer_correction_overrides_stored_memory(self):
        self.seed_preference(); before = self._source_counts()
        gateway, _ = self.runtime(); result = gateway.execute(recall_request(statements={"book_format": "hardcover"}))
        self.assertNotIn("book_format", {item["key"] for item in result.result["functional_context"]})
        self.assertEqual(self._source_counts(), before)

    def test_t18_raw_transcript_internal_metadata_never_returned(self):
        self.seed_preference(); self.seed_fact()
        gateway, _ = self.runtime(); result = gateway.execute(recall_request(purpose="explicit_memory_review", topic="memory_review", intent="show_saved_memory", explicit=True, challenge=True))
        serialized = json.dumps(result.result).lower()
        for forbidden in ("raw_transcript", "payload_fingerprint", "database", "provider", "audit_event_id", "hidden_reasoning", "idempotency"):
            self.assertNotIn(forbidden, serialized)
        raw = asdict(recall_request())
        raw["actor"] = asdict(recall_request().actor); raw["capability"] = asdict(recall_request().capability)
        raw["input"]["raw_transcript"] = "synthetic conversation"
        with self.assertRaises(RequestValidationError):
            ToolRequest.from_dict(raw)
        raw = asdict(recall_request()); raw["actor"] = asdict(recall_request().actor); raw["capability"] = asdict(recall_request().capability)
        raw["provider"] = "postgres"
        with self.assertRaises(RequestValidationError):
            ToolRequest.from_dict(raw)

    def test_t19_recall_decision_and_audit_correlate(self):
        self.seed_preference(); item = recall_request(); gateway, adapter = self.runtime(); result = gateway.execute(item)
        audit = adapter.audits(item.correlation_id)[0]
        self.assertEqual({str(audit["correlation_id"]), result.correlation_id, item.correlation_id}, {item.correlation_id})
        self.assertEqual((audit["functional_count"], audit["relationship_count"]), (1, 0))
        self.assertEqual(audit["recall_modes"], ["CONTEXTUAL_REFERENCE"])
        self.assertEqual(str(audit["audit_event_id"]), result.evidence_reference)

    def test_t20_tg_p01_through_tg_p05b_regression_preservation(self):
        suite = unittest.TestSuite([
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p01.TGP01AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p02.TGP02AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p03.TGP03AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p04.TGP04AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p05a.TGP05AAcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p05b.TGP05BAcceptanceTests),
        ])
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertEqual((result.testsRun, len(result.failures), len(result.errors)), (120, 0, 0))

    def _source_counts(self):
        with psycopg.connect(self.preference_dsn) as connection:
            preferences = connection.execute("SELECT COUNT(*) FROM tg_p05a.customer_preferences").fetchone()[0]
        with psycopg.connect(self.relationship_dsn) as connection:
            facts = connection.execute("SELECT COUNT(*) FROM tg_p05b.relationship_facts").fetchone()[0]
        return preferences, facts


if __name__ == "__main__":
    unittest.main()
