import io
import os
import unittest

import psycopg

from src.budly_runtime.conversation_harness import ConversationHarness
from src.budly_runtime.postgres_memory_recall import PostgresMemoryRecallAdapter, memory_recall_capability_definition
from src.budly_runtime.postgres_preference import PostgresPreferenceAdapter, preference_capability_definition
from src.budly_runtime.postgres_relationship_fact import PostgresRelationshipFactAdapter, relationship_fact_capability_definition
from src.budly_runtime.tool_gateway import AuditSink, ToolGateway, ToolHealth, ToolRegistry
from tests import test_tg_p01_tool_gateway as tg_p01
from tests import test_tg_p02_operational_metrics as tg_p02
from tests import test_tg_p03_activity_record as tg_p03
from tests import test_tg_p04_activity_persistence as tg_p04
from tests import test_tg_p05a_customer_preference as tg_p05a
from tests import test_tg_p05b_relationship_fact as tg_p05b
from tests import test_tg_p06_customer_memory_recall as tg_p06


class TGP07AcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.activity_dsn = os.environ["TG_P04_DATABASE_URL"]
        cls.preference_dsn = os.environ["TG_P05A_DATABASE_URL"]
        cls.relationship_dsn = os.environ["TG_P05B_DATABASE_URL"]
        cls.recall_dsn = os.environ["TG_P06_DATABASE_URL"]
        PostgresPreferenceAdapter(cls.preference_dsn, environment="automated_test").apply_migration()
        PostgresRelationshipFactAdapter(cls.relationship_dsn, environment="automated_test").apply_migration()
        PostgresMemoryRecallAdapter(cls.preference_dsn, cls.relationship_dsn, cls.recall_dsn, environment="automated_test").apply_migration()

    def setUp(self):
        with psycopg.connect(self.preference_dsn) as connection:
            connection.execute("TRUNCATE tg_p05a.preference_audit_events, tg_p05a.customer_preferences")
        with psycopg.connect(self.relationship_dsn) as connection:
            connection.execute("TRUNCATE tg_p05b.relationship_fact_audit_events, tg_p05b.relationship_facts")
        with psycopg.connect(self.recall_dsn) as connection:
            connection.execute("TRUNCATE tg_p06.memory_recall_audit_events")

    def harness(self, *, preference_fail=False, recall_state=ToolHealth.HEALTHY):
        preference = PostgresPreferenceAdapter(self.preference_dsn, environment="automated_test", fail_write=preference_fail)
        relationship = PostgresRelationshipFactAdapter(self.relationship_dsn, environment="automated_test")
        recall = PostgresMemoryRecallAdapter(self.preference_dsn, self.relationship_dsn, self.recall_dsn, environment="automated_test", state=recall_state)
        harness = ConversationHarness(
            ToolGateway(ToolRegistry(preference_capability_definition(), preference), AuditSink()),
            ToolGateway(ToolRegistry(relationship_fact_capability_definition(), relationship), AuditSink()),
            ToolGateway(ToolRegistry(memory_recall_capability_definition(), recall), AuditSink()),
        )
        return harness, preference, relationship, recall

    def test_t01_ephemeral_preference_stays_session_only(self):
        harness, preference, _, _ = self.harness(); session = harness.start_session("P-TEST-001")
        harness.receive_turn(session, "For this conversation, keep it short.", topic="current_style", intent="ephemeral_instruction", ephemeral_updates={"response_length": "short"})
        result = harness.record_preference(session, "conversation_style", "concise", explicit_customer_statement=False)
        self.assertEqual((session.ephemeral_context["response_length"], result["status"], preference.count()), ("short", "EPHEMERAL_ONLY", 0))

    def test_t02_explicit_durable_preference_routes_through_tg_p05a(self):
        harness, preference, _, _ = self.harness(); session = harness.start_session("P-TEST-001")
        result = harness.record_preference(session, "book_format", "paperback", explicit_customer_statement=True)
        self.assertTrue(result["saved"]); self.assertEqual(preference.count(), 1)
        self.assertEqual(session.capability_results[-1]["capability_id"], "customer.preference.record")

    def test_t03_later_session_retrieves_durable_preference(self):
        harness, _, _, _ = self.harness(); first = harness.start_session("P-TEST-001")
        harness.record_preference(first, "book_format", "paperback", explicit_customer_statement=True)
        later = harness.start_session("P-TEST-001"); recall = harness.recall(later, purpose="product_assistance", topic="book_edition", intent="product_selection")
        self.assertEqual(recall.functional_context[0]["value"], "paperback")
        self.assertNotEqual(first.session_id, later.session_id)

    def test_t04_silent_use_is_respected(self):
        harness, _, _, _ = self.harness(); first = harness.start_session("P-TEST-001")
        harness.record_preference(first, "conversation_style", "concise", explicit_customer_statement=True)
        later = harness.start_session("P-TEST-001"); recall = harness.recall(later, purpose="product_assistance", topic="book_edition", intent="product_selection")
        self.assertEqual(recall.response_instructions["style"]["conversation_style"], "concise")
        self.assertEqual(recall.response_instructions["contextual_references"], [])

    def test_t05_changed_preference_wins_and_supersedes(self):
        harness, preference, _, _ = self.harness(); first = harness.start_session("P-TEST-001")
        harness.record_preference(first, "book_format", "paperback", explicit_customer_statement=True)
        current = harness.start_session("P-TEST-001")
        harness.receive_turn(current, "I switched to hardcover.", topic="book_edition", intent="preference_change", current_statements={"book_format": "hardcover"})
        before = harness.recall(current, purpose="product_assistance", topic="book_edition", intent="product_selection")
        self.assertNotIn("paperback", {item["value"] for item in before.functional_context})
        result = harness.record_preference(current, "book_format", "hardcover", explicit_customer_statement=True)
        history = preference.history("P-TEST-001", "book_format")
        self.assertTrue(result["saved"]); self.assertEqual([(row.preference_value, row.status) for row in history], [("paperback", "SUPERSEDED"), ("hardcover", "ACTIVE")])

    def test_t06_later_session_uses_new_preference(self):
        harness, _, _, _ = self.harness(); one = harness.start_session("P-TEST-001")
        harness.record_preference(one, "book_format", "paperback", explicit_customer_statement=True)
        two = harness.start_session("P-TEST-001"); harness.record_preference(two, "book_format", "hardcover", explicit_customer_statement=True)
        three = harness.start_session("P-TEST-001"); recall = harness.recall(three, purpose="product_assistance", topic="book_edition", intent="product_selection")
        self.assertEqual([item["value"] for item in recall.functional_context if item["key"] == "book_format"], ["hardcover"])

    def test_t07_explicit_relationship_fact_routes_through_tg_p05b(self):
        harness, _, relationship, _ = self.harness(); session = harness.start_session("P-TEST-001")
        result = harness.record_relationship_fact(session, "upcoming_graduation", {"related_person_first_name": "Maya", "related_person_relationship": "daughter", "event_period": "spring", "is_minor": True}, explicit_customer_statement=True)
        changed = harness.start_session("P-TEST-001")
        updated = harness.record_relationship_fact(changed, "upcoming_graduation", {"related_person_first_name": "Maya", "related_person_relationship": "daughter", "event_period": "december", "is_minor": True}, explicit_customer_statement=True)
        history = relationship.history("P-TEST-001", "upcoming_graduation")
        self.assertTrue(result["saved"] and updated["saved"])
        self.assertEqual([(row.event_date_or_period, row.status) for row in history], [("spring", "SUPERSEDED"), ("december", "UPCOMING")])
        self.assertEqual(history[1].supersedes_fact_id, history[0].relationship_fact_id)
        self.assertIn("december", changed.ephemeral_context["upcoming_graduation"])
        self.assertEqual(session.capability_results[-1]["capability_id"], "customer.relationship_fact.record")

    def test_t08_unrelated_later_conversation_suppresses_relationship_fact(self):
        harness, _, _, _ = self.harness(); one = harness.start_session("P-TEST-001")
        harness.record_relationship_fact(one, "upcoming_graduation", {"related_person_first_name": "Maya", "related_person_relationship": "daughter", "event_period": "spring"}, explicit_customer_statement=True)
        later = harness.start_session("P-TEST-001")
        for topic, intent in (("terpenes", "education_question"), ("ecs", "education_question"), ("botanical_book", "product_selection")):
            self.assertEqual(harness.recall(later, purpose="education_assistance" if intent == "education_question" else "product_assistance", topic=topic, intent=intent).relationship_context, ())

    def test_t09_natural_bridge_enables_bounded_relationship_recall(self):
        harness, _, _, _ = self.harness(); one = harness.start_session("P-TEST-001")
        harness.record_relationship_fact(one, "upcoming_graduation", {"related_person_first_name": "Maya", "related_person_relationship": "daughter", "event_period": "spring"}, explicit_customer_statement=True)
        later = harness.start_session("P-TEST-001"); recall = harness.recall(later, purpose="product_assistance", topic="graduation_gift", intent="gift_for_daughter", entities=("Maya", "daughter"))
        self.assertEqual((len(recall.relationship_context), recall.relationship_context[0]["key"]), (1, "upcoming_graduation"))

    def test_t10_repeated_behavior_does_not_create_preference(self):
        harness, preference, _, _ = self.harness(); session = harness.start_session("P-TEST-001")
        for _ in range(5):
            hypothesis = harness.observe_behavior(session, "book_format", "paperback")
        self.assertEqual((hypothesis["observations"], hypothesis["authoritative"], preference.count()), (5, False, 0))

    def test_t11_explicit_confirmation_converts_hypothesis_to_preference(self):
        harness, preference, _, _ = self.harness(); session = harness.start_session("P-TEST-001")
        for _ in range(5): harness.observe_behavior(session, "content_format", "video")
        result = harness.record_preference(session, "content_format", "video", explicit_customer_statement=True, remember_requested=True)
        self.assertTrue(result["saved"]); self.assertEqual(preference.count(), 1)

    def test_t12_repeated_identical_durable_fact_does_not_multiply_truth(self):
        harness, preference, _, _ = self.harness(); one = harness.start_session("P-TEST-001")
        first = harness.record_preference(one, "book_format", "paperback", explicit_customer_statement=True)
        later = harness.start_session("P-TEST-001"); second = harness.record_preference(later, "book_format", "paperback", explicit_customer_statement=True)
        self.assertTrue(first["saved"]); self.assertEqual(second["status"], "ALREADY_CURRENT"); self.assertEqual(preference.count(), 1)

    def test_t13_start_fresh_suppresses_saved_memory(self):
        harness, preference, relationship, _ = self.harness(); one = harness.start_session("P-TEST-001")
        harness.record_preference(one, "book_format", "paperback", explicit_customer_statement=True)
        harness.record_relationship_fact(one, "customer_birthday", {"month": 10, "day": 12}, explicit_customer_statement=True)
        fresh = harness.start_session("P-TEST-001", memory_use_mode="START_FRESH")
        recall = harness.recall(fresh, purpose="explicit_memory_review", topic="memory_review", intent="show_saved_memory", explicit_memory_request=True)
        self.assertEqual((recall.functional_context, recall.relationship_context), ((), ()))
        self.assertEqual((preference.count(), relationship.count()), (1, 1))

    def test_t14_later_use_memory_restores_eligible_recall(self):
        harness, _, _, _ = self.harness(); one = harness.start_session("P-TEST-001")
        harness.record_preference(one, "book_format", "paperback", explicit_customer_statement=True)
        self.assertEqual(harness.recall(harness.start_session("P-TEST-001", memory_use_mode="START_FRESH"), purpose="product_assistance", topic="book_edition", intent="product_selection").functional_context, ())
        active = harness.start_session("P-TEST-001", memory_use_mode="ACTIVE")
        self.assertEqual(harness.recall(active, purpose="product_assistance", topic="book_edition", intent="product_selection").functional_context[0]["value"], "paperback")

    def test_t15_interleaved_customers_are_isolated(self):
        harness, _, _, _ = self.harness(); a = harness.start_session("P-TEST-001"); b = harness.start_session("P-TEST-002")
        harness.record_preference(a, "book_format", "paperback", explicit_customer_statement=True)
        harness.record_preference(b, "book_format", "hardcover", explicit_customer_statement=True)
        c = harness.start_session("P-TEST-001")
        a_values = [item["value"] for item in harness.recall(c, purpose="product_assistance", topic="book_edition", intent="product_selection").functional_context]
        b_values = [item["value"] for item in harness.recall(b, purpose="product_assistance", topic="book_edition", intent="product_selection").functional_context]
        self.assertEqual((a_values, b_values), (["paperback"], ["hardcover"]))
        self.assertEqual(len(set(a.correlation_ids + b.correlation_ids + c.correlation_ids)), len(a.correlation_ids + b.correlation_ids + c.correlation_ids))

    def test_t16_current_correction_beats_retrieved_memory(self):
        harness, preference, _, _ = self.harness(); one = harness.start_session("P-TEST-001")
        harness.record_preference(one, "book_format", "paperback", explicit_customer_statement=True)
        current = harness.start_session("P-TEST-001"); harness.receive_turn(current, "Hardcover for this one.", topic="book_edition", intent="product_selection", current_statements={"book_format": "hardcover"})
        recall = harness.recall(current, purpose="product_assistance", topic="book_edition", intent="product_selection")
        self.assertEqual(recall.functional_context, ()); self.assertEqual(current.current_statements["book_format"], "hardcover"); self.assertEqual(preference.count(), 1)

    def test_t17_failed_memory_write_is_not_claimed_as_saved(self):
        harness, preference, _, _ = self.harness(preference_fail=True); session = harness.start_session("P-TEST-001")
        result = harness.record_preference(session, "book_format", "paperback", explicit_customer_statement=True)
        self.assertEqual((result["saved"], result["claim_saved"], preference.count()), (False, False, 0))

    def test_t18_failed_recall_does_not_produce_fabricated_memory(self):
        harness, _, _, _ = self.harness(recall_state=ToolHealth.UNAVAILABLE); session = harness.start_session("P-TEST-001")
        recall = harness.recall(session, purpose="product_assistance", topic="book_edition", intent="product_selection")
        self.assertFalse(recall.memory_available); self.assertEqual((recall.functional_context, recall.relationship_context), ((), ()))
        self.assertTrue(recall.response_instructions["must_not_claim_recollection"])

    def test_t19_historical_raw_transcript_not_required(self):
        harness, _, _, _ = self.harness(); one = harness.start_session("P-TEST-001")
        harness.receive_turn(one, "Let's discuss terpenes.", topic="terpenes", intent="education_question")
        harness.record_preference(one, "education_style", "step_by_step", explicit_customer_statement=True)
        summary = one.bounded_summary
        later = harness.start_session("P-TEST-001"); recall = harness.recall(later, purpose="education_assistance", topic="ecs", intent="education_question")
        self.assertEqual(recall.functional_context[0]["value"], "step_by_step")
        self.assertEqual(later.turns, []); self.assertNotIn("Let's discuss", summary); self.assertEqual(summary, "terpenes")

    def test_t20_predecessor_regression_preservation(self):
        suite = unittest.TestSuite([
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p01.TGP01AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p02.TGP02AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p03.TGP03AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p04.TGP04AcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p05a.TGP05AAcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p05b.TGP05BAcceptanceTests),
            unittest.defaultTestLoader.loadTestsFromTestCase(tg_p06.TGP06AcceptanceTests),
        ])
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertEqual((result.testsRun, len(result.failures), len(result.errors)), (140, 0, 0))


if __name__ == "__main__":
    unittest.main()
