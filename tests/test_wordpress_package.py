import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy" / "wordpress" / "budly-sales-agent"


class WordPressPackageTests(unittest.TestCase):
    def test_required_plugin_files_exist(self):
        for relative in (
            "budly-sales-agent.php",
            "assets/budly-sales.js",
            "assets/budly-sales.css",
            "assets/budly-entry.js",
            "includes/tracking.php",
        ):
            self.assertTrue((PLUGIN / relative).is_file(), relative)

    def test_plugin_has_installable_header_and_shortcodes(self):
        php = (PLUGIN / "budly-sales-agent.php").read_text(encoding="utf-8")
        self.assertIn("Plugin Name: Budly Sales Agent", php)
        self.assertIn("add_shortcode('budly_sales_agent'", php)
        self.assertIn("add_shortcode('budly_sales_policies'", php)
        self.assertIn("wp_ajax_nopriv_budly_sales_handoff", php)

    def test_support_handoff_is_sanitized_and_rate_limited(self):
        php = (PLUGIN / "budly-sales-agent.php").read_text(encoding="utf-8")
        for required in ("check_ajax_referer", "sanitize_email", "sanitize_textarea_field", "set_transient", "wp_mail"):
            self.assertIn(required, php)
        self.assertEqual(1, len(re.findall(r"wp_mail\('budlysupport@gmail.com'", php)))

    def test_public_catalog_is_allowlisted_and_risk_routed(self):
        js = (PLUGIN / "assets" / "budly-sales.js").read_text(encoding="utf-8")
        self.assertIn("const allowed=new Set", js)
        self.assertIn("treat my", js)
        self.assertIn("I cannot diagnose, recommend treatment", js)
        self.assertNotIn("relieves pain", js.lower())

    def test_live_chat_has_membership_policy_and_conversation_starters(self):
        js = (PLUGIN / "assets" / "budly-sales.js").read_text(encoding="utf-8")
        self.assertIn("Membership begins as soon as the transaction finishes processing", js)
        self.assertIn("Using a membership discount counts as use", js)
        self.assertIn("Help me choose a product", js)
        self.assertIn("Shop within my budget", js)
        self.assertIn("Compare products", js)
        self.assertIn("Membership questions", js)
        self.assertIn("Wholesale inquiries", js)
        self.assertIn("Order, shipping, or human support", js)

    def test_tracking_is_first_party_and_consent_gated(self):
        tracking = (PLUGIN / "includes" / "tracking.php").read_text(encoding="utf-8")
        js = (PLUGIN / "assets" / "budly-sales.js").read_text(encoding="utf-8")
        self.assertIn("budly_sales_events", tracking)
        self.assertIn("budly_sales_customers", tracking)
        self.assertIn("budly_sales_conversations", tracking)
        self.assertIn("memory_consent", tracking)
        self.assertIn("budly_sales_sheet_webhook", tracking)
        self.assertIn("conversation_started", js)
        self.assertIn("product_clicked", js)


if __name__ == "__main__":
    unittest.main()
