import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "deploy/wordpress/budly-sales-agent/includes/SecureMemory"


class CommercialMemoryV15Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = (BASE / "CommercialMemory/CommercialMemoryPolicy.php").read_text(encoding="utf-8")
        cls.repo = (BASE / "CommercialMemory/CommercialMemoryRepository.php").read_text(encoding="utf-8")
        cls.service = (BASE / "CommercialMemory/CommercialMemoryService.php").read_text(encoding="utf-8")
        cls.context = (BASE / "CommercialMemory/CommercialContextBuilder.php").read_text(encoding="utf-8")
        cls.conversation = (BASE / "CommercialMemory/ConversationContextService.php").read_text(encoding="utf-8")
        cls.routes = (BASE / "Api/Routes.php").read_text(encoding="utf-8")
        cls.migration = (BASE / "Database/Migrator.php").read_text(encoding="utf-8")
        cls.decision = (BASE / "Decision/DecisionService.php").read_text(encoding="utf-8")

    def test_exact_governed_memory_types(self):
        for name in ("customer_interest", "product_interest", "preferred_format", "purchase_intent", "customer_goal", "customer_objection", "preferred_communication_style", "education_progress", "affiliate_interest", "membership_interest"):
            self.assertIn("'" + name + "'", self.policy)

    def test_no_free_form_memory_type(self):
        self.assertIn("in_array($type, self::TYPES, true)", self.policy)

    def test_memory_values_are_bounded_and_sensitive_screened(self):
        self.assertIn("mb_strlen($value) > 500", self.policy)
        self.assertIn("MemoryPolicy::contains_sensitive($value)", self.policy)

    def test_confidence_is_bounded(self):
        self.assertIn("$confidence < 0 || $confidence > 1", self.policy)

    def test_provenance_is_allowlisted(self):
        self.assertIn("const SOURCES", self.policy)
        self.assertIn("source_reference", self.policy)

    def test_schema_contains_required_object_fields(self):
        for field in ("memory_uuid", "customer_id", "namespace", "memory_type", "value_json", "confidence", "source_type", "observed_at", "consent_state", "expiration_policy", "audit_reference"):
            self.assertIn(field, self.migration)

    def test_migration_is_additive(self):
        self.assertIn("commercial_memory", self.migration)
        self.assertNotIn("DROP TABLE", self.migration.upper())

    def test_memory_creation_requires_storage_consent(self):
        self.assertIn("granted_record($customer,'memory_storage')", self.service)

    def test_memory_read_requires_use_consent(self):
        self.assertIn("is_granted($customer,'memory_use')", self.service)

    def test_customer_ownership_is_server_derived(self):
        self.assertIn("(int)$session['customer_id']", self.service)
        self.assertIn("find_owned($customer,$uuid)", self.service)

    def test_updates_create_new_versions(self):
        self.assertIn("supersede($prior,$record)", self.service)
        self.assertIn("(int)$prior['version']+1", self.service)

    def test_correction_has_governed_provenance(self):
        self.assertIn("customer_correction", self.service)
        self.assertIn("customer_confirmed", self.service)

    def test_deletion_is_tombstoned(self):
        self.assertIn("'value_json'=>'null'", self.repo)
        self.assertIn("'status'=>'deleted'", self.repo)

    def test_expiration_is_deterministic(self):
        self.assertIn("status='expired'", self.repo)
        self.assertIn("commercial_memory.expired", self.service)

    def test_consent_withdrawal_updates_active_objects(self):
        self.assertIn("update_consent_state", self.service)
        self.assertIn("commercial_memory.consent_withdrawn", self.service)

    def test_export_is_consent_gated_and_audited(self):
        self.assertIn("commercial_memory.exported", self.service)
        self.assertIn("'consent'=>$this->consent->read", self.service)

    def test_all_customer_mutations_are_csrf_session_and_rate_protected(self):
        self.assertIn("SessionGuard::require_session($request,true)", self.routes)
        self.assertIn("commercial_memory_write", self.routes)

    def test_admin_mutations_are_capability_and_nonce_protected(self):
        self.assertIn("current_user_can('manage_options')", self.routes)
        self.assertIn("wp_verify_nonce($nonce,'wp_rest')", self.routes)

    def test_admin_controls_include_search_correct_delete_export(self):
        for action in ("admin_commercial_memory", "admin_correct_commercial_memory", "admin_delete_commercial_memory", "admin_export_commercial_memory"):
            self.assertIn(action, self.routes)

    def test_conversation_summary_has_only_approved_fields(self):
        for field in ("topics_discussed", "products_discussed", "questions_asked", "recommendations_made", "customer_decisions", "human_escalations", "conversation_outcome", "next_recommended_action"):
            self.assertIn("'" + field + "'", self.policy)
        self.assertIn("array_diff(array_keys($value), $allowed)", self.policy)

    def test_conversation_summary_requires_storage_consent(self):
        self.assertIn("granted_record($customer,'memory_storage')", self.conversation)

    def test_context_has_fixed_explainable_shape(self):
        for key in ("verified_customer_profile", "conversation_history_summary", "relevant_memory_objects", "current_objective", "current_consent_state", "journey_stage", "known_exclusions", "known_preferences"):
            self.assertIn("'" + key + "'", self.context)

    def test_context_rejects_sensitive_objectives(self):
        self.assertIn("MemoryPolicy::contains_sensitive($objective)", self.context)

    def test_decision_evidence_records_memory_references_not_values(self):
        self.assertIn("commercial_memory_references", self.decision)
        self.assertIn("'uuid'=>", self.decision)
        self.assertNotIn("'commercial_memory_values'", self.decision)

    def test_known_exclusions_are_server_enforced(self):
        self.assertIn("'reason'=>'customer_exclusion'", self.decision)

    def test_rules_manifest_has_commercial_memory_version(self):
        rules = json.loads((ROOT / "config/bros_v1_5.json").read_text(encoding="utf-8"))
        self.assertEqual("bros-rules-1.5.0.0", rules["version"])
        self.assertEqual("commercial-memory-1.5.0.0", rules["commercial_memory"]["version"])
        self.assertFalse(rules["commercial_memory"]["free_form_ai_memory"])


if __name__ == "__main__":
    unittest.main()
