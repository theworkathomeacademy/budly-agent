import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "deploy" / "wordpress" / "budly-sales-agent" / "includes" / "SecureMemory"


class Phase5SecurityContractTests(unittest.TestCase):
    def text(self, relative):
        return (BASE / relative).read_text(encoding="utf-8")

    def test_phase5_schema_tracks_context_idempotency_provenance_and_retention(self):
        migration = self.text("Database/Migrator.php")
        config = self.text("Config.php")
        for required in (
            "memory_contexts", "idempotency", "provenance_json", "content_hash",
            "retention_policy", "corrected_at", "customer_content",
        ):
            self.assertIn(required, migration)
        self.assertIn("SCHEMA_VERSION = '1.3.0'", config)
        self.assertIn("SUMMARY_MAX_BYTES", config)
        self.assertIn("MEMORY_MAX_ACTIVE_PER_CUSTOMER", config)
        self.assertIn("MEMORY_DEFAULT_RETENTION_DAYS", config)

    def test_every_customer_endpoint_resolves_ownership_from_verified_session(self):
        routes = self.text("Api/Routes.php")
        for endpoint in (
            "/identity", "/profile", "/preferences", "/memory/preview",
            "/memory/use", "/memory/start-fresh", "/memory/shared",
            "/memory/summary", "/memory/export",
        ):
            self.assertIn(endpoint, routes)
        self.assertNotIn("$params['customer_id']", routes)
        self.assertNotIn("$request->get_param('customer_id')", routes)
        self.assertGreaterEqual(routes.count("SessionGuard::require_session"), 10)

    def test_profile_and_preferences_are_explicitly_allowlisted(self):
        profile = self.text("Profile/ProfileService.php")
        preferences = self.text("Profile/PreferenceService.php")
        for field in (
            "preferred_name", "experience_level", "communication_preferences",
            "accessibility_preferences", "educational_preferences",
        ):
            self.assertIn(field, profile)
        for field in ("product_interests", "format_preferences", "shopping_preferences"):
            self.assertIn(field, preferences)
        self.assertIn("FIELD_NOT_ALLOWED", profile)
        self.assertIn("FIELD_NOT_ALLOWED", preferences)

    def test_profile_preference_and_summary_writes_require_storage_consent(self):
        profile = self.text("Profile/ProfileService.php")
        preferences = self.text("Profile/PreferenceService.php")
        memory = self.text("Memory/MemoryService.php")
        self.assertIn("is_granted($customer_id,'memory_storage')", profile)
        self.assertIn("is_granted($customer,'memory_storage')", preferences)
        self.assertIn("granted_record($customer,'memory_storage')", memory)
        self.assertGreaterEqual(memory.count("CONSENT_REQUIRED"), 4)

    def test_preview_and_export_use_customer_visible_allowlists(self):
        memory = self.text("Memory/MemoryService.php")
        repository = self.text("Memory/MemoryRepository.php")
        self.assertIn("classification=%s", repository)
        self.assertIn("'customer_visible'", repository)
        self.assertIn("array_intersect_key", memory)
        self.assertIn("safe_provenance", memory)
        export_method = memory.split("public function export", 1)[1].split("private function", 1)[0]
        self.assertNotIn("'session_id'", export_method)
        self.assertNotIn("token_hash", memory)

    def test_memory_use_is_bound_to_session_agent_conversation_purpose_and_expiry(self):
        migration = self.text("Database/Migrator.php")
        memory = self.text("Memory/MemoryService.php")
        for required in ("session_id", "customer_id", "conversation_id", "agent_id", "purpose", "approved", "start_fresh", "expires_at"):
            self.assertIn(required, migration)
        self.assertIn("$agent!==$session['agent_id']", memory)
        self.assertIn("personalize_product_guidance", memory)
        self.assertIn("$session['absolute_expires_at']", memory)
        self.assertIn("find_context($session['session_id']", memory)

    def test_start_fresh_overrides_context_without_changing_consent(self):
        memory = self.text("Memory/MemoryService.php")
        approved = memory.split("private function approved_context", 1)[1]
        self.assertIn("start_fresh", approved)
        self.assertIn("MEMORY_USE_NOT_APPROVED", approved)
        self.assertNotIn("ConsentRepository->update", memory)

    def test_summary_schema_limits_and_sensitive_data_rules_are_enforced(self):
        policy = self.text("Memory/MemoryPolicy.php")
        for field in (
            "topic", "customer_goal", "resolved_questions", "open_questions",
            "confirmed_preferences", "customer_corrections", "next_recommended_step",
        ):
            self.assertIn(field, policy)
        for required in (
            "SUMMARY_MAX_BYTES", "SUMMARY_MAX_LIST_ITEMS", "SUMMARY_MAX_ITEM_CHARS",
            "payment", "diagnosed with", "social security", "system prompt",
            "chain[- ]of[- ]thought", "verification[_ -]?code",
        ):
            self.assertIn(required, policy)

    def test_summary_provenance_is_server_constructed_and_not_client_trusted(self):
        service = self.text("Memory/MemoryService.php")
        routes = self.text("Api/Routes.php")
        for required in ("source_agent_id", "conversation_id", "session_id", "recorded_at", "customer_corrected"):
            self.assertIn(required, service)
        self.assertNotIn("$input['provenance']", service)
        self.assertNotIn("$params['provenance']", routes)

    def test_duplicate_and_replay_controls_are_database_backed(self):
        migration = self.text("Database/Migrator.php")
        repository = self.text("Memory/MemoryRepository.php")
        idempotency = self.text("Idempotency/IdempotencyService.php")
        routes = self.text("Api/Routes.php")
        self.assertIn("UNIQUE KEY customer_content", migration)
        self.assertIn("UNIQUE KEY request_identity", migration)
        self.assertIn("hash_equals($existing['content_hash']", repository)
        self.assertIn("WHERE customer_id=%d AND content_hash=%s", repository)
        self.assertIn("'duplicate'=>true", repository)
        self.assertIn("INSERT IGNORE", idempotency)
        self.assertIn("request_hash", idempotency)
        self.assertIn("Idempotency-Key", routes)
        self.assertIn("idempotency key is invalid", routes)
        self.assertIn("already being processed", routes)

    def test_corrections_and_selective_deletion_are_customer_scoped(self):
        repository = self.text("Memory/MemoryRepository.php")
        service = self.text("Memory/MemoryService.php")
        self.assertRegex(repository, r"WHERE customer_id=%d AND memory_id=%s")
        self.assertIn("find_owned($customer,$memory_id)", service)
        self.assertIn("customer_correction", service)
        self.assertIn("confirmation!==true", service)

    def test_delete_all_is_transactional_and_revokes_all_customer_sessions(self):
        repository = self.text("Memory/MemoryRepository.php")
        service = self.text("Memory/MemoryService.php")
        delete_all = repository.split("public function delete_all", 1)[1]
        self.assertIn("START TRANSACTION", delete_all)
        self.assertIn("ROLLBACK", delete_all)
        self.assertIn("conversation_memory", delete_all)
        self.assertIn("preferences", delete_all)
        self.assertIn("memory_contexts", delete_all)
        self.assertIn("revoke_all_for_customer", service)
        self.assertIn("clear_cookie", service)

    def test_agent_scope_and_namespace_are_server_authorized(self):
        registry = self.text("Authorization/AgentRegistry.php")
        memory = self.text("Memory/MemoryService.php")
        self.assertIn("status = %s", registry)
        self.assertIn("in_array($scope", registry)
        self.assertIn("in_array($namespace", registry)
        self.assertIn("memory:read:agent", memory)
        self.assertIn("memory:write:summary", memory)
        self.assertIn("AGENT_NOT_AUTHORIZED", memory)

    def test_all_phase5_mutations_require_csrf(self):
        routes = self.text("Api/Routes.php")
        helper = routes.split("private static function customer_json_mutation", 1)[1]
        self.assertIn("SessionGuard::require_session($request,true)", helper)
        for callback in (
            "update_profile", "update_preferences", "memory_use", "start_fresh",
            "store_summary", "correct_memory", "delete_memory_item", "delete_memory",
        ):
            method = routes.split(f"function {callback}", 1)[1].split("\n", 1)[0]
            self.assertIn("customer_json_mutation", method)


if __name__ == "__main__":
    unittest.main()
