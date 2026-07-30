import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"deploy"/"wordpress"/"budly-sales-agent"
SECURE=BASE/"includes"/"SecureMemory"

class Phase9SecurityHardeningTests(unittest.TestCase):
 def test_legacy_ajax_identity_and_memory_bypass_is_not_callable(self):
  tracking=(BASE/"includes"/"tracking.php").read_text(encoding="utf-8")
  for action in ("budly_sales_request_recall","budly_sales_verify_recall"):
   self.assertNotIn(f"add_action('wp_ajax_{action}'",tracking)
   self.assertNotIn(f"add_action('wp_ajax_nopriv_{action}'",tracking)

 def test_rest_security_requires_https_and_same_origin(self):
  security=(SECURE/"Security"/"RequestSecurity.php").read_text(encoding="utf-8")
  self.assertIn("!is_ssl()",security)
  self.assertIn("get_header('Origin')",security)
  self.assertIn("hash_equals",security)
  self.assertIn("CSRF_VALIDATION_FAILED",security)

 def test_sensitive_rest_responses_are_never_cacheable_or_frameable(self):
  security=(SECURE/"Security"/"RequestSecurity.php").read_text(encoding="utf-8")
  for header in ("no-store, private, max-age=0","no-cache","nosniff","no-referrer","DENY"):
   self.assertIn(header,security)

 def test_audit_scrubbing_is_recursive_bounded_and_secret_key_aware(self):
  audit=(SECURE/"Audit"/"AuditService.php").read_text(encoding="utf-8")
  self.assertIn("self::scrub($value)",audit)
  self.assertIn("authorization",audit)
  self.assertIn("cookie",audit)
  self.assertIn("strlen($text)>500",audit)
  self.assertNotIn("metadata_json' => wp_json_encode($context",audit)

 def test_ineligible_verification_does_not_persist_raw_email(self):
  service=(SECURE/"Verification"/"VerificationService.php").read_text(encoding="utf-8")
  self.assertIn("'email'=>$customer ? $normalized : ''",service)
  self.assertIn("email_hash",service)

 def test_public_analytics_is_rate_limited_and_remains_deidentified(self):
  tracking=(BASE/"includes"/"tracking.php").read_text(encoding="utf-8")
  handler=tracking.split("function budly_sales_track_event()",1)[1].split("add_action('wp_ajax_budly_sales_track'",1)[0]
  self.assertIn("get_transient($rate_key)",handler)
  self.assertIn("set_transient($rate_key",handler)
  self.assertIn("429",handler)
  self.assertIn("'email_hash' => ''",handler)
  self.assertIn("'phone_hash' => ''",handler)
  self.assertNotIn("tables['customers']",handler)

 def test_no_obvious_embedded_private_keys_or_generic_api_secrets(self):
  text="\n".join(p.read_text(encoding="utf-8",errors="ignore") for p in BASE.rglob("*") if p.is_file() and p.suffix in {".php",".js",".json",".md"})
  self.assertNotRegex(text,r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
  self.assertNotRegex(text,r"sk-[A-Za-z0-9]{32,}")
  self.assertNotRegex(text,r"AIza[0-9A-Za-z_-]{30,}")

if __name__=="__main__":unittest.main()
