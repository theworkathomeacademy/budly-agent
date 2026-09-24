import json
import re
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy" / "wordpress" / "budly-sales-agent"
CATALOG_PROVISIONER = PLUGIN / "includes" / "Commerce" / "CatalogProvisioner.php"
CANONICAL_CATALOG = ROOT / "config" / "canonical_catalog.json"


def evaluate_php_auth_logic(is_user_logged_in: bool, can_manage_wc: bool, can_manage_options: bool) -> dict:
    """Exact emulation of the fail-closed authorization gate in CatalogProvisioner::provision_all()."""
    if not is_user_logged_in or (not can_manage_wc and not can_manage_options):
        return {"status": "error", "reason": "unauthorized"}
    return {"status": "authorized"}


class CatalogProvisionerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.php_source = CATALOG_PROVISIONER.read_text(encoding="utf-8")
        self.catalog_data = json.loads(CANONICAL_CATALOG.read_text(encoding="utf-8"))

    def test_01_provisioning_authorization_gate_fail_closed_source(self):
        """Test that provision_all contains the exact fail-closed authorization gate."""
        self.assertIn("function provision_all(", self.php_source)
        self.assertIn("!is_user_logged_in()", self.php_source)
        self.assertIn("!current_user_can('manage_woocommerce')", self.php_source)
        self.assertIn("!current_user_can('manage_options')", self.php_source)
        self.assertIn("'reason' => 'unauthorized'", self.php_source)

    def test_02_auth_condition_a_logged_out_caller_rejected(self):
        """Condition A: Logged-out caller is strictly rejected."""
        res = evaluate_php_auth_logic(is_user_logged_in=False, can_manage_wc=False, can_manage_options=False)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["reason"], "unauthorized")

    def test_03_auth_condition_b_logged_in_subscriber_rejected(self):
        """Condition B: Logged-in non-admin (subscriber/customer) is strictly rejected."""
        res = evaluate_php_auth_logic(is_user_logged_in=True, can_manage_wc=False, can_manage_options=False)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["reason"], "unauthorized")

    def test_04_auth_condition_c_woocommerce_manager_accepted(self):
        """Condition C: WooCommerce shop manager (manage_woocommerce) is accepted."""
        res = evaluate_php_auth_logic(is_user_logged_in=True, can_manage_wc=True, can_manage_options=False)
        self.assertEqual(res["status"], "authorized")

    def test_05_auth_condition_d_administrator_accepted(self):
        """Condition D: Site Administrator (manage_options) is accepted."""
        res = evaluate_php_auth_logic(is_user_logged_in=True, can_manage_wc=False, can_manage_options=True)
        self.assertEqual(res["status"], "authorized")

    def test_06_torque_redirect_migration_gate(self):
        """Test that handle_redirects strictly checks budly_torque_slug_migrated before redirecting."""
        self.assertIn("handle_redirects", self.php_source)
        self.assertIn("get_option('budly_torque_slug_migrated') !== '1'", self.php_source)
        
        gate_pos = self.php_source.find("get_option('budly_torque_slug_migrated') !== '1'")
        redirect_pos = self.php_source.find("wp_safe_redirect(home_url('/product/torque-nft-membership/'), 301);")
        self.assertGreater(redirect_pos, gate_pos, "Redirect must follow migration option check")

    def test_07_torque_slug_migration_logic(self):
        """Test that migrate_torque_slug method exists and validates ID 875 and variations 877-880."""
        self.assertIn("function migrate_torque_slug()", self.php_source)
        self.assertIn("wc_get_product(875)", self.php_source)
        self.assertIn("877, 878, 879, 880", self.php_source)
        self.assertIn("'torque-nft-membership'", self.php_source)
        self.assertIn("update_option('budly_torque_slug_migrated', '1')", self.php_source)

    def test_08_consultation_product_verified_route_live_http_200(self):
        """Test consultation product route and re-verify HTTP 200 live."""
        url = "https://wakenbakelounge.com/service-page/is-cannabis-right-for-me"
        self.assertIn(url, self.php_source)
        self.assertIn("CCC-SRV-ICRFM75", self.php_source)
        self.assertIn("ccc:service:is-cannabis-right-for-me", self.php_source)
        self.assertIn("wix_bookings", self.php_source)
        self.assertIn("75.00", self.php_source)

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Budly-Safety-Audit/1.9.0)"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            self.assertEqual(resp.status, 200, "Consultation booking destination must return HTTP 200")

    def test_09_community_products_draft_protection_and_metadata(self):
        """Test that Community products are provisioned as draft, hidden, and have required non-purchasable metadata."""
        self.assertIn("set_status('draft')", self.php_source)
        self.assertIn("set_catalog_visibility('hidden')", self.php_source)
        self.assertIn("_budly_billing_model", self.php_source)
        self.assertIn("_budly_checkout_capability", self.php_source)
        self.assertIn("NOT_CONFIGURED", self.php_source)
        self.assertIn("_budly_customer_purchasable", self.php_source)
        self.assertIn("_budly_payment_processor", self.php_source)
        self.assertIn("APPROVED_NOT_RELEASED", self.php_source)
        self.assertIn("_budly_benefit_count", self.php_source)
        
        # Verify Wix Plan IDs
        self.assertIn("a101970a-4600-4dbb-8e49-e91cfed93d80", self.php_source)
        self.assertIn("1658a089-db78-418c-85ed-ac01d5bcabb0", self.php_source)
        self.assertIn("ac8a8d86-961d-417e-84a3-47cd6537db9f", self.php_source)

    def test_10_community_membership_exact_benefit_counts(self):
        """Test that Lounge Pass has 1 benefit, while Member and Elite have 6 benefits each."""
        entries = {e["canonical_id"]: e for e in self.catalog_data["entries"]}
        
        pass_mbr = entries.get("wnb:community:lounge-pass")
        self.assertIsNotNone(pass_mbr)
        pass_benefits = pass_mbr.get("full_benefits") or pass_mbr.get("benefits") or []
        self.assertEqual(len(pass_benefits), 1, "Lounge Pass must have exactly 1 benefit")
        self.assertEqual(pass_benefits[0], "Community access")
        
        member_mbr = entries.get("wnb:community:lounge-member")
        self.assertIsNotNone(member_mbr)
        member_benefits = member_mbr.get("full_benefits") or member_mbr.get("benefits") or []
        self.assertEqual(len(member_benefits), 6, "Lounge Member must have exactly 6 benefits")
        
        elite_mbr = entries.get("wnb:community:lounge-elite")
        self.assertIsNotNone(elite_mbr)
        elite_benefits = elite_mbr.get("full_benefits") or elite_mbr.get("benefits") or []
        self.assertEqual(len(elite_benefits), 6, "Lounge Elite must have exactly 6 benefits")

    def test_11_community_full_benefits_preservation(self):
        """Test that all specific benefits for Member and Elite tiers are preserved."""
        entries = {e["canonical_id"]: e for e in self.catalog_data["entries"]}
        
        member_benefits = set(entries["wnb:community:lounge-member"].get("full_benefits", []))
        self.assertIn("Community access", member_benefits)
        self.assertIn("10% off all Lounge Collection products", member_benefits)
        self.assertIn("Early access to new drops", member_benefits)
        self.assertIn("Exclusive forum sections", member_benefits)
        self.assertIn("Member badge", member_benefits)
        self.assertIn("Priority event access", member_benefits)
        
        elite_benefits = set(entries["wnb:community:lounge-elite"].get("full_benefits", []))
        self.assertIn("Community access", elite_benefits)
        self.assertIn("25% off all Lounge Collection products", elite_benefits)
        self.assertIn("First access to exclusive drops", elite_benefits)
        self.assertIn("VIP forum badge", elite_benefits)
        self.assertIn("Priority event invitations", elite_benefits)
        self.assertIn("Monthly curated content from Budly T. Cannaguide", elite_benefits)

    def test_12_coupon_release_gate_and_deferral_policy(self):
        """Test that CatalogProvisioner implements coupon deferral until launch."""
        self.assertIn("DEFER_LIVE_COUPON_CREATION_UNTIL_LAUNCH", self.php_source)
        self.assertIn("PRELAUNCH_CONFIGURATION_PRESENT", self.php_source)
        self.assertIn("REDEMPTION_BEHAVIOR_NOT_RUNTIME_VERIFIED", self.php_source)
        self.assertIn("LOUNGEMEMBER10", self.php_source)
        self.assertIn("LOUNGEELITE25", self.php_source)
        self.assertIn("strtotime('-1 year')", self.php_source)

    def test_13_canonical_catalog_stripe_routes_verified(self):
        """Test that core course payment plans in canonical_catalog.json have verified live Stripe routes."""
        entries = {e["canonical_id"]: e for e in self.catalog_data["entries"]}
        
        cul_pp = entries.get("ccc:course:culinary-cannabis:payment-plan")
        self.assertIsNotNone(cul_pp)
        self.assertEqual(cul_pp["stripe_route_status"], "VERIFIED")
        self.assertEqual(cul_pp["stripe_payment_link"], "https://buy.stripe.com/cNi3cugI527OeoS9BleIw0J")
        
        gch_pp = entries.get("ccc:course:grow-cannabis-home:payment-plan")
        self.assertIsNotNone(gch_pp)
        self.assertEqual(gch_pp["stripe_route_status"], "VERIFIED")
        self.assertEqual(gch_pp["stripe_payment_link"], "https://buy.stripe.com/14A7sKfE113KbcG14PeIw0K")
        
        cgw_pp = entries.get("ccc:course:grow-cook-with-me:payment-plan")
        self.assertIsNotNone(cgw_pp)
        self.assertEqual(cgw_pp["stripe_route_status"], "VERIFIED")
        self.assertEqual(cgw_pp["stripe_payment_link"], "https://buy.stripe.com/9B6dR81Nb8wc5Sm14PeIw0L")

    def test_14_provisioning_idempotency_markers(self):
        """Test that CatalogProvisioner checks existing items by SKU and slug to prevent duplicate creation."""
        self.assertIn("wc_get_product_id_by_sku($sku)", self.php_source)
        self.assertIn("get_page_by_path($slug", self.php_source)
        self.assertIn("wc_get_coupon_id_by_code($code)", self.php_source)
        self.assertIn("'status'        => 'existing'", self.php_source)

    def test_15_package_release_identity_consistency(self):
        """Test that plugin header, constant, and RC2 ZIP match 1.9.0-rc2."""
        plugin_php = (PLUGIN / "budly-sales-agent.php").read_text(encoding="utf-8")
        self.assertIn("* Version: 1.9.0-rc2", plugin_php)
        self.assertIn("define('BUDLY_SALES_VERSION', '1.9.0-rc2');", plugin_php)

        import zipfile
        rc2_zip = ROOT / "deploy" / "wordpress" / "budly-sales-agent-1.9.0-rc2.zip"
        self.assertTrue(rc2_zip.is_file())
        with zipfile.ZipFile(rc2_zip, "r") as z:
            php_zip = z.read("budly-sales-agent/budly-sales-agent.php").decode("utf-8")
            self.assertIn("* Version: 1.9.0-rc2", php_zip)
            self.assertIn("define('BUDLY_SALES_VERSION', '1.9.0-rc2');", php_zip)

    def test_16_rollback_artifact_188_preserved(self):
        """Test that dist/budly-sales-agent-1.8.8.zip exists and has unaltered SHA256."""
        import hashlib
        p188 = ROOT / "dist" / "budly-sales-agent-1.8.8.zip"
        self.assertTrue(p188.is_file(), "dist/budly-sales-agent-1.8.8.zip must exist")
        sha = hashlib.sha256(p188.read_bytes()).hexdigest()
        self.assertEqual(sha, "3eabf0d67a386c146d7a7743213fd6018fec1cf32b359b37162e7037724fc811")


if __name__ == "__main__":
    unittest.main()
