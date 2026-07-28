import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"deploy"/"wordpress"/"budly-sales-agent"

class Phase8CleanupOperationsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.cleanup=(BASE/"includes"/"SecureMemory"/"Cleanup"/"CleanupService.php").read_text(encoding="utf-8")
  cls.config=(BASE/"includes"/"SecureMemory"/"Config.php").read_text(encoding="utf-8")
  cls.bootstrap=(BASE/"includes"/"SecureMemory"/"Bootstrap.php").read_text(encoding="utf-8")
  cls.routes=(BASE/"includes"/"SecureMemory"/"Api"/"Routes.php").read_text(encoding="utf-8")
  cls.page=(BASE/"includes"/"SecureMemory"/"Admin"/"AdminPage.php").read_text(encoding="utf-8")

 def test_daily_cleanup_is_scheduled_and_removed_on_deactivation(self):
  self.assertIn("wp_schedule_event",self.bootstrap)
  self.assertIn("'daily'",self.bootstrap)
  self.assertIn("wp_next_scheduled",self.bootstrap)
  self.assertIn("wp_unschedule_event",self.bootstrap)
  plugin=(BASE/"budly-sales-agent.php").read_text(encoding="utf-8")
  self.assertIn("register_deactivation_hook",plugin)

 def test_retention_defaults_are_configurable_operational_values(self):
  for required in ("VERIFICATION_ARTIFACT_RETENTION_DAYS = 7","SESSION_RECORD_RETENTION_DAYS = 30","MEMORY_DEFAULT_RETENTION_DAYS = 365","get_option('budly_memory_'"):
   self.assertIn(required,self.config)

 def test_cleanup_is_bounded_and_uses_prepared_queries(self):
  self.assertIn("CLEANUP_BATCH_SIZE",self.cleanup)
  self.assertIn("LIMIT %d",self.cleanup)
  self.assertIn("$this->wpdb->prepare",self.cleanup)
  self.assertIn("Config::table($logical)",self.cleanup)

 def test_only_expired_temporary_records_are_deleted(self):
  for table in ("verification_requests","sessions","memory_contexts","idempotency"):
   self.assertIn(f"'{table}'",self.cleanup)
  self.assertNotIn("delete_batch('consent'",self.cleanup)
  self.assertNotIn("delete_batch('consent_history'",self.cleanup)
  self.assertNotIn("delete_batch('audit'",self.cleanup)
  self.assertNotIn("delete_batch('conversation_memory'",self.cleanup)

 def test_cleanup_records_success_failure_summary_and_preservation(self):
  for required in ("cleanup.completed","cleanup.failed","budly_secure_memory_last_cleanup","duration_ms","customer_memory'=>true","consent_history'=>true"):
   self.assertIn(required,self.cleanup)

 def test_manual_cleanup_is_capability_and_nonce_protected(self):
  self.assertIn("/admin/run-cleanup",self.routes)
  method=self.routes.split("function admin_run_cleanup",1)[1].split("\n",1)[0]
  self.assertIn("admin_mutation",method)
  self.assertIn("data-run-cleanup",self.page)
  admin_js=(BASE/"assets"/"budly-secure-memory-admin.js").read_text(encoding="utf-8")
  self.assertIn("/admin/run-cleanup",admin_js)
  self.assertIn("X-WP-Nonce",admin_js)

if __name__=="__main__":unittest.main()
