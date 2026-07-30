import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PLUGIN=ROOT/"deploy"/"wordpress"/"budly-sales-agent"

class Phase6CustomerExperienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(PLUGIN/"assets"/"budly-secure-memory.js").read_text(encoding="utf-8")
        cls.css=(PLUGIN/"assets"/"budly-sales.css").read_text(encoding="utf-8")
        cls.php=(PLUGIN/"budly-sales-agent.php").read_text(encoding="utf-8")

    def test_customer_module_uses_only_versioned_secure_memory_rest_api(self):
        self.assertIn("budly-identity/v1",self.php)
        self.assertIn("credentials:'same-origin'",self.js)
        self.assertIn("Content-Type']='application/json'",self.js)
        self.assertIn("X-Budly-CSRF",self.js)
        self.assertNotIn("admin-ajax",self.js)
        self.assertNotIn("localStorage",self.js)
        self.assertNotIn("sessionStorage",self.js)

    def test_approved_customer_journey_states_are_present(self):
        for copy in (
            "Verify your email","Check your inbox","Verification successful",
            "What Budly remembers","Use This Information","Start Fresh",
            "Memory enabled","Privacy settings","Nothing is saved yet",
            "Delete remembered information","Your remembered information has been deleted",
            "Your verification expired","Could not complete that step",
        ):
            self.assertIn(copy,self.js)

    def test_verification_has_resend_and_distinct_safe_error_states(self):
        self.assertIn("data-memory-resend",self.js)
        for code in ("SESSION_EXPIRED","VERIFICATION_LOCKED","CODE_EXPIRED","INVALID_CODE","RATE_LIMITED"):
            self.assertIn(code,self.js)
        self.assertIn("autocomplete=\"one-time-code\"",self.js)
        self.assertIn("pattern=\"[0-9]{6}\"",self.js)

    def test_preview_text_is_rendered_as_text_not_customer_html(self):
        self.assertIn("textContent=value",self.js)
        self.assertIn("document.createTextNode(message)",self.js)
        self.assertNotIn("summary.topic+'<",self.js)

    def test_privacy_choices_are_independent_and_plain_language(self):
        for consent in ("memory_storage","memory_use","marketing"):
            self.assertIn(consent,self.js)
        self.assertIn("Security and verification emails are not marketing",self.js)
        self.assertIn("apply immediately",self.js)

    def test_deletion_requires_confirmation_and_explains_retained_security_records(self):
        self.assertIn("delete_confirmation",self.js)
        self.assertIn("cannot be undone",self.js)
        self.assertIn("security and audit records may remain",self.js)
        self.assertIn("scope:'all_customer_memory'",self.js)

    def test_loading_empty_error_and_accessibility_behaviors_exist(self):
        self.assertIn("aria-busy",self.js)
        self.assertIn("Nothing is saved yet",self.js)
        self.assertIn("aria-label",self.js)
        self.assertIn("?.focus()",self.js)
        self.assertIn(":focus-visible",self.css)
        self.assertIn("prefers-reduced-motion:reduce",self.css)
        self.assertIn("min-height:48px",self.css)
        self.assertIn("@media(max-width:600px)",self.css)

    def test_customer_correction_selective_delete_and_export_are_available(self):
        self.assertIn("data-correct",self.js)
        self.assertIn("data-delete-item",self.js)
        self.assertIn("Export My Data",self.js)
        self.assertIn("application/json",self.js)

    def test_legacy_sales_submit_handler_is_blocked_during_memory_flow(self):
        self.assertIn("root.dataset.memoryActive='1'",self.js)
        self.assertIn("stopImmediatePropagation",self.js)
        self.assertIn("budly-memory-submit",self.js)
        self.assertIn("delete root.dataset.memoryActive",self.js)

if __name__=="__main__":unittest.main()
