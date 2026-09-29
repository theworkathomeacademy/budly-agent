import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"deploy"/"wordpress"/"budly-sales-agent"

class Phase7AdministrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.routes=(BASE/"includes"/"SecureMemory"/"Api"/"Routes.php").read_text(encoding="utf-8")
  cls.service=(BASE/"includes"/"SecureMemory"/"Admin"/"AdminService.php").read_text(encoding="utf-8")
  cls.repo=(BASE/"includes"/"SecureMemory"/"Admin"/"AdminRepository.php").read_text(encoding="utf-8")
  cls.page=(BASE/"includes"/"SecureMemory"/"Admin"/"AdminPage.php").read_text(encoding="utf-8")
  cls.script=(BASE/"assets"/"budly-secure-memory-admin.js").read_text(encoding="utf-8")

 def test_all_approved_admin_endpoints_exist(self):
  for endpoint in ("/admin/health","/admin/audit","/admin/revoke-session","/admin/revoke-all","/admin/test-email"):
   self.assertIn(endpoint,self.routes)

 def test_admin_reads_and_mutations_require_capability(self):
  self.assertIn("current_user_can('manage_options')",self.routes)
  self.assertGreaterEqual(self.routes.count("ADMIN_PERMISSION_REQUIRED"),3)
  self.assertIn("current_user_can('manage_options')",self.page)
  self.assertIn("'manage_options'",self.page)

 def test_admin_mutations_require_rest_nonce(self):
  helper=self.routes.split("private static function admin_mutation",1)[1]
  self.assertIn("X-WP-Nonce",helper)
  self.assertIn("wp_verify_nonce",helper)
  self.assertIn("CSRF_VALIDATION_FAILED",helper)

 def test_session_revocation_uses_identifiers_not_raw_tokens(self):
  self.assertIn("session_id",self.service)
  self.assertIn("revoke_all_for_customer",self.service)
  self.assertNotIn("token_hash",self.service)
  self.assertNotIn("session_token",self.service)
  self.assertIn("Raw session tokens",self.page)

 def test_every_administrative_mutation_is_audited_with_wordpress_actor(self):
  self.assertIn("get_current_user_id()",self.service)
  for event in ("admin.session_revoked","admin.customer_sessions_revoked","admin.test_email"):
   self.assertIn(event,self.service)

 def test_health_is_safe_aggregate_status(self):
  for field in ("schema_version","api_version","active_sessions","revoked_sessions","delivery_failures","active_memory","last_cleanup"):
   self.assertIn(field,self.service)
  self.assertNotIn("SELECT email",self.service)
  self.assertNotIn("summary_json",self.service)

 def test_audit_queries_are_filtered_bounded_and_paginated(self):
  for field in ("event_type","severity","actor_type","result","date_from","date_to"):
   self.assertIn(field,self.repo)
  self.assertIn("LIMIT %d OFFSET %d",self.repo)
  self.assertIn("min(100,$per_page)",self.service)
  self.assertIn("ORDER BY created_at DESC",self.repo)

 def test_admin_page_and_external_script_are_registered(self):
  self.assertIn("add_management_page",self.page)
  self.assertIn("budly-secure-memory-admin.js",self.page)
  self.assertIn("wp_create_nonce('wp_rest')",self.page)
  self.assertTrue((BASE/"assets"/"budly-secure-memory-admin.js").is_file())

 def test_admin_audit_ui_exposes_conversation_and_decoded_metadata_read_only(self):
  self.assertIn("item.conversation_id",self.script)
  self.assertIn("JSON.stringify(item.metadata??{},null,2)",self.script)
  self.assertIn("document.createElement('details')",self.script)
  self.assertIn("metadata.textContent",self.script)
  self.assertIn("data-audit-conversation",self.page)
  self.assertIn("data-audit-filter",self.page)
  self.assertNotIn("contentEditable",self.script)

 def test_audit_visibility_preserves_admin_boundary_and_api_contract(self):
  handler=self.routes.split("public static function admin_audit",1)[1].split("public static function admin_revoke_session",1)[0]
  self.assertIn("self::admin_permission()",handler)
  self.assertIn("ADMIN_PERMISSION_REQUIRED",handler)
  self.assertIn("audit_log($filters",handler)
  self.assertNotIn("conversation_id",handler)
  self.assertNotIn("POST",handler)
  self.assertNotIn("DELETE",handler)
  self.assertIn("/admin/audit?per_page=100",self.script)
  self.assertIn("item.conversation_id===query",self.script)

 def test_customer_facing_ask_budly_is_not_part_of_admin_audit_ui(self):
  self.assertNotIn("budly-sales.js",self.page)
  self.assertNotIn("data-budly-sales",self.page)

if __name__=="__main__":unittest.main()
