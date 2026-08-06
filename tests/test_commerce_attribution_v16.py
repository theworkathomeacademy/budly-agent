import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy/wordpress/budly-sales-agent"


class CommerceAttributionV16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = (PLUGIN / "includes/SecureMemory/Config.php").read_text(encoding="utf-8")
        cls.migration = (PLUGIN / "includes/SecureMemory/Database/Migrator.php").read_text(encoding="utf-8")
        cls.adapter = (PLUGIN / "includes/Commerce/WooCommerceAdapter.php").read_text(encoding="utf-8")
        cls.repository = (PLUGIN / "includes/Commerce/CommerceRepository.php").read_text(encoding="utf-8")
        cls.attribution = (PLUGIN / "includes/Commerce/AttributionService.php").read_text(encoding="utf-8")
        cls.revenue = (PLUGIN / "includes/Commerce/RevenueService.php").read_text(encoding="utf-8")
        cls.routes = (PLUGIN / "includes/SecureMemory/Api/Routes.php").read_text(encoding="utf-8")

    def test_versions_are_separately_governed(self):
        self.assertIn("SCHEMA_VERSION = '1.4.0'", self.config)
        self.assertIn("BROS_RULE_VERSION = 'bros-rules-1.5.0.0'", self.config)
        self.assertIn("COMMERCE_CONFIG_VERSION = 'commerce-attribution-1.6.0.0'", self.config)

    def test_four_promoted_tables_are_additive_and_prefixed(self):
        for name in ("commerce_events", "order_links", "affiliate_attribution", "revenue_daily"):
            self.assertIn(f"Config::table('{name}')", self.migration)
            self.assertIn(f"'{name}'", self.config)

    def test_applied_migration_is_a_verified_no_op(self):
        self.assertIn("version_compare($installed_version, Config::SCHEMA_VERSION, '<')", self.migration)
        self.assertIn("array_slice($tables, $pre_commerce_table_count)", self.migration)
        self.assertIn("Required commerce table is missing after migration", self.migration)

    def test_financial_storage_is_fixed_precision_and_currency_scoped(self):
        self.assertGreaterEqual(self.migration.count("decimal(20,6)"), 10)
        self.assertIn("currency char(3)", self.migration)
        self.assertIn("daily_dimension", self.migration)
        self.assertIn("currency_date", self.migration)

    def test_external_event_key_is_unique_and_replay_checked(self):
        self.assertIn("UNIQUE KEY external_event_key", self.migration)
        self.assertIn("event_by_key($key)", self.adapter)
        self.assertIn("commerce.event_replay", self.adapter)
        self.assertIn("status'=>'duplicate'", self.adapter)

    def test_order_is_loaded_from_woocommerce_authority(self):
        self.assertIn("wc_get_order((int)$order_id)", self.adapter)
        self.assertIn("$order->get_total()", self.adapter)
        self.assertIn("$order->get_currency()", self.adapter)
        self.assertNotIn("$_POST", self.adapter)

    def test_clicks_and_browser_events_cannot_create_revenue(self):
        self.assertNotIn("product_clicked", self.adapter)
        self.assertNotIn("add_to_cart", self.adapter)
        self.assertIn("payment_completed", self.adapter)
        self.assertIn("order_completed", self.adapter)

    def test_revenue_requires_authoritative_order_status_and_corrections_reverse_net(self):
        self.assertIn("in_array($status,array('processing','completed'),true)", self.adapter)
        self.assertIn("recorded_net_total", self.adapter)
        self.assertIn("order_cancelled','order_failed", self.adapter)
        self.assertIn("gross_amount>0", self.repository)
        self.assertIn("(float)$event['gross_amount']>0", self.revenue)

    def test_refunds_use_server_order_refunds(self):
        self.assertIn("$order->get_refunds()", self.adapter)
        self.assertIn("$refund->get_total()", self.adapter)
        self.assertIn("order_refunded", self.adapter)

    def test_attribution_has_explicit_uncertainty_states(self):
        for state in ("attributed", "unattributed", "conflicted", "review_required"):
            self.assertIn(state, self.attribution)
        self.assertIn("customer_mismatch", self.attribution)

    def test_no_silent_identity_merge(self):
        self.assertIn("$customer_id!==", self.attribution)
        self.assertIn("customer_mismatch", self.attribution)

    def test_metrics_are_derived_from_verified_events_and_separated_by_currency(self):
        self.assertIn("verification_status=%s", self.repository)
        self.assertIn("currency=%s", self.repository)
        self.assertIn("currencies_for_day", self.revenue)
        self.assertNotIn("exchange", self.revenue.lower())

    def test_reports_are_capability_protected_and_bounded(self):
        self.assertIn("/admin/commerce/report", self.routes)
        self.assertIn("/admin/commerce/export", self.routes)
        self.assertIn("admin_permission()", self.routes)
        self.assertIn("admin_mutation($request", self.routes)
        self.assertIn("commerce.report_exported", self.routes)
        self.assertIn("commerce_admin_export", self.routes)
        self.assertIn("min(100", self.routes)
        self.assertIn("Currencies are never combined", self.routes)

    def test_woocommerce_degrades_safely(self):
        self.assertIn("woocommerce_unavailable", self.adapter)
        self.assertIn("missing_order", self.adapter)
        self.assertIn("commerce.event_rejected", self.adapter)

    def test_audit_covers_event_attribution_replay_and_report(self):
        joined = self.adapter + self.attribution + self.routes
        for event in ("commerce.event_verified", "commerce.event_replay", "commerce.attribution", "commerce.report_viewed"):
            self.assertIn(event, joined)

    def test_customer_facing_assets_are_not_referenced_by_commerce(self):
        joined = self.adapter + self.attribution + self.revenue + self.repository
        self.assertNotIn("ask-budly-page", joined)
        self.assertNotIn("budly-sales.js", joined)
        self.assertNotIn("budly-sales.css", joined)

    def test_build_manifest_contains_commerce_configuration(self):
        build = (ROOT / "scripts/build_plugin.py").read_text(encoding="utf-8")
        self.assertIn('COMMERCE_CONFIG_VERSION = "commerce-attribution-1.6.0.0"', build)
        self.assertIn('"commerce_configuration_version": COMMERCE_CONFIG_VERSION', build)


if __name__ == "__main__":
    unittest.main()
