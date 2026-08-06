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

    def test_secure_memory_foundation_modules_exist(self):
        for relative in (
            "includes/SecureMemory/Bootstrap.php",
            "includes/SecureMemory/Config.php",
            "includes/SecureMemory/Errors.php",
            "includes/SecureMemory/Response.php",
            "includes/SecureMemory/Validation.php",
            "includes/SecureMemory/Database/Migrator.php",
            "includes/SecureMemory/Database/Repository.php",
            "includes/SecureMemory/Audit/AuditService.php",
        ):
            self.assertTrue((PLUGIN / relative).is_file(), relative)

    def test_secure_memory_migration_covers_approved_foundation_tables(self):
        migration = (
            PLUGIN / "includes" / "SecureMemory" / "Database" / "Migrator.php"
        ).read_text(encoding="utf-8")
        for logical_table in (
            "customers",
            "preferences",
            "conversation_memory",
            "consent",
            "consent_history",
            "verification_requests",
            "sessions",
            "audit",
            "schema_migrations",
            "agents",
        ):
            self.assertIn(f"Config::table('{logical_table}')", migration)
        self.assertIn("dbDelta", migration)
        self.assertIn("SCHEMA_VERSION", migration)
        self.assertNotIn("serialize(", migration)

    def test_foundation_centralizes_api_contract_and_safe_audit(self):
        base = PLUGIN / "includes" / "SecureMemory"
        config = (base / "Config.php").read_text(encoding="utf-8")
        errors = (base / "Errors.php").read_text(encoding="utf-8")
        response = (base / "Response.php").read_text(encoding="utf-8")
        repository = (base / "Database" / "Repository.php").read_text(encoding="utf-8")
        audit = (base / "Audit" / "AuditService.php").read_text(encoding="utf-8")
        self.assertIn("budly-identity/v1", config)
        self.assertIn("SESSION_EXPIRED", errors)
        self.assertIn("'success' => true", response)
        self.assertIn("'success' => false", response)
        self.assertIn("$this->wpdb->prepare", repository)
        self.assertIn("metadata_json", audit)
        self.assertIn("preg_replace('/[^a-z0-9._-]/'", audit)
        for forbidden in ("code", "token", "password", "secret", "authorization", "cookie"):
            self.assertIn(forbidden, audit)
        self.assertIn("self::scrub($value)", audit)

    def test_verification_service_enforces_approved_security_boundaries(self):
        base = PLUGIN / "includes" / "SecureMemory"
        service = (base / "Verification" / "VerificationService.php").read_text(encoding="utf-8")
        repository = (base / "Verification" / "VerificationRepository.php").read_text(encoding="utf-8")
        routes = (base / "Api" / "Routes.php").read_text(encoding="utf-8")
        for required in (
            "random_int(0, 999999)",
            "wp_hash_password($code)",
            "VERIFICATION_TTL_SECONDS",
            "verification_email",
            "verification_ip",
            "verification_resend_cooldown_seconds",
            "invalidate_open_for_email",
            "If this address is eligible, we've sent a verification code.",
            "unset($code)",
        ):
            self.assertIn(required, service)
        for required in ("START TRANSACTION", "FOR UPDATE", "wp_check_password", "consumed_at", "COMMIT", "ROLLBACK"):
            self.assertIn(required, repository)
        self.assertIn("/auth/request-code", routes)
        self.assertIn("/auth/verify", routes)
        self.assertIn("application/json", (base / "Validation.php").read_text(encoding="utf-8"))
        self.assertNotIn("'code'=>", service)
        config = (base / "Config.php").read_text(encoding="utf-8")
        self.assertIn("VERIFICATION_RESEND_COOLDOWN_SECONDS", config)
        self.assertIn("budly_memory_verification_resend_cooldown_seconds", config)
        self.assertIn("count_since('email_hash', $email_hash, $cooldown_since) > 0", service)

    def test_email_transport_is_replaceable_and_transactional_only(self):
        base = PLUGIN / "includes" / "SecureMemory" / "Email"
        interface = (base / "EmailTransport.php").read_text(encoding="utf-8")
        transport = (base / "WordPressMailTransport.php").read_text(encoding="utf-8")
        self.assertIn("interface EmailTransport", interface)
        self.assertIn("send_verification_code", interface)
        self.assertIn("send_test", interface)
        self.assertIn("wp_mail", transport)
        self.assertIn("No customer memory is included", transport)
        self.assertNotIn("sale", transport.lower())

    def test_sessions_are_server_side_expiring_revocable_and_cookie_protected(self):
        base = PLUGIN / "includes" / "SecureMemory"
        service = (base / "Sessions" / "SessionService.php").read_text(encoding="utf-8")
        repository = (base / "Sessions" / "SessionRepository.php").read_text(encoding="utf-8")
        guard = (base / "Sessions" / "SessionGuard.php").read_text(encoding="utf-8")
        routes = (base / "Api" / "Routes.php").read_text(encoding="utf-8")
        for required in (
            "random_bytes(32)", "token_hash", "SESSION_IDLE_SECONDS",
            "SESSION_ABSOLUTE_SECONDS", "'secure'=>true", "'httponly'=>true",
            "'samesite'=>'Strict'", "csrf_is_valid", "unset($token)",
        ):
            self.assertIn(required, service)
        self.assertIn("if ($result === false)", repository)
        self.assertIn("SELECT COUNT(*)", repository)
        self.assertIn("status = %s AND revoked_at IS NULL", repository)
        self.assertNotIn("'token'=>", service)
        for required in ("find_by_token_hash", "revoke_all_for_customer", "revoked_at IS NULL"):
            self.assertIn(required, repository)
        self.assertIn("X-Budly-CSRF", guard)
        self.assertIn("AUTHENTICATION_REQUIRED", guard)
        self.assertIn("CSRF_VALIDATION_FAILED", guard)
        self.assertIn("SessionService::instance()->create", routes)
        self.assertIn("/auth/session", routes)
        self.assertIn("/auth/logout", routes)
        self.assertIn("instanceof \\WP_REST_Response", routes)
        self.assertGreaterEqual(routes.count("if (!is_ssl())"), 2)

    def test_session_identity_is_never_accepted_from_customer_input(self):
        base = PLUGIN / "includes" / "SecureMemory"
        routes = (base / "Api" / "Routes.php").read_text(encoding="utf-8")
        guard = (base / "Sessions" / "SessionGuard.php").read_text(encoding="utf-8")
        self.assertNotIn("$params['customer_id']", routes)
        self.assertIn("$session", guard)
        self.assertIn("customer_id", (base / "Sessions" / "SessionService.php").read_text(encoding="utf-8"))

    def test_three_consent_types_are_independent_transactional_and_fail_closed(self):
        base = PLUGIN / "includes" / "SecureMemory"
        service = (base / "Consent" / "ConsentService.php").read_text(encoding="utf-8")
        repository = (base / "Consent" / "ConsentRepository.php").read_text(encoding="utf-8")
        routes = (base / "Api" / "Routes.php").read_text(encoding="utf-8")
        for consent_type in ("memory_storage", "memory_use", "marketing"):
            self.assertIn(consent_type, service)
        self.assertIn("return false", service)
        self.assertIn("=== 'granted'", service)
        self.assertIn("CONSENT_VERSION", service)
        for required in ("START TRANSACTION", "consent_history", "COMMIT", "ROLLBACK", "ON DUPLICATE KEY UPDATE"):
            self.assertIn(required, repository)
        self.assertIn("SessionGuard::require_session($request, true)", routes)
        self.assertIn("(int) $session['customer_id']", routes)
        self.assertNotIn("$params['customer_id']", routes)

    def test_consent_update_rejects_unknown_status_source_and_version(self):
        service = (PLUGIN / "includes" / "SecureMemory" / "Consent" / "ConsentService.php").read_text(encoding="utf-8")
        self.assertIn("UPDATE_STATUSES", service)
        self.assertIn("SOURCES", service)
        self.assertIn("RESOURCE_CONFLICT", service)
        self.assertIn("hash_equals(Config::CONSENT_VERSION", service)

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
        self.assertIn('aria-label="First name"', js)
        self.assertIn('aria-label="Email for this conversation"', js)
        self.assertIn('aria-label="Phone (optional)"', js)
        self.assertIn('aria-label="Tell me what you’re looking for"', js)
        self.assertIn('aria-label="Your answer"', js)
        css = (PLUGIN / "assets" / "budly-sales.css").read_text(encoding="utf-8")
        self.assertIn(".budly-composer{display:grid;grid-template-columns:1fr}", css)

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

    def test_legacy_ajax_recall_is_not_registered(self):
        tracking = (PLUGIN / "includes" / "tracking.php").read_text(encoding="utf-8")
        plugin = (PLUGIN / "budly-sales-agent.php").read_text(encoding="utf-8")
        self.assertNotIn("add_action('wp_ajax_budly_sales_request_recall'", tracking)
        self.assertNotIn("add_action('wp_ajax_nopriv_budly_sales_request_recall'", tracking)
        self.assertNotIn("add_action('wp_ajax_budly_sales_verify_recall'", tracking)
        self.assertNotIn("add_action('wp_ajax_nopriv_budly_sales_verify_recall'", tracking)
        self.assertNotIn("recallNonce", plugin)
        self.assertIn("Secure recall is REST/session based", tracking)
        self.assertIn("Version: 1.6.0", plugin)

    def test_recall_interface_preserves_privacy(self):
        js = (PLUGIN / "assets" / "budly-sales.js").read_text(encoding="utf-8")
        self.assertIn("Returning customer? Verify your email", js)
        self.assertIn("budly_sales_request_recall", js)
        self.assertIn("budly_sales_verify_recall", js)
        self.assertIn("identity_verified", js)
        self.assertIn("history_recalled", js)

    def test_public_tracking_cannot_write_identity_consent_or_memory(self):
        tracking = (PLUGIN / "includes" / "tracking.php").read_text(encoding="utf-8")
        handler = tracking.split("function budly_sales_track_event()", 1)[1].split(
            "add_action('wp_ajax_budly_sales_track'", 1
        )[0]
        self.assertNotIn("memory_consent", handler)
        self.assertNotIn("tables['customers']", handler)
        self.assertNotIn("tables['conversations']", handler)
        self.assertNotIn("budly_sales_identity_hash(", handler)
        self.assertIn("'email_hash' => ''", handler)
        self.assertIn("'phone_hash' => ''", handler)
        self.assertIn("'summary'=>'" + "'", handler)


if __name__ == "__main__":
    unittest.main()
