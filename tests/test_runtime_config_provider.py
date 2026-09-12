from __future__ import annotations

import hashlib
import hmac
import time
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy/wordpress/budly-sales-agent"


class RuntimeConfigurationProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proxy = (PLUGIN / "includes/Runtime/ConversationProxy.php").read_text(encoding="utf-8")
        cls.plugin = (PLUGIN / "budly-sales-agent.php").read_text(encoding="utf-8")
        cls.js = (PLUGIN / "assets/budly-sales.js").read_text(encoding="utf-8")

    def test_resolution_order_constants_then_options_then_fail_closed(self):
        self.assertIn("defined('BUDLY_CONVERSATIONAL_RUNTIME_ENABLED')", self.proxy)
        self.assertIn("defined('BUDLY_CONVERSATIONAL_RUNTIME_URL')", self.proxy)
        self.assertIn("defined('BUDLY_CONVERSATIONAL_RUNTIME_SECRET')", self.proxy)
        self.assertIn("self::stored_configuration()", self.proxy)
        self.assertIn("get_option('budly_sales_runtime_config'", self.proxy)
        self.assertIn("return array('error' => true)", self.proxy)

    def test_configure_route_requires_authenticated_hmac_and_validates_inputs(self):
        self.assertIn("register_rest_route(self::NAMESPACE, '/configure'", self.proxy)
        self.assertIn("hash_hmac('sha256', $timestamp . '.' . $body, $secret)", self.proxy)
        self.assertIn("hash_equals($expected, $signature)", self.proxy)
        self.assertIn("update_option('budly_sales_runtime_config', $config, false)", self.proxy)
        self.assertIn("strlen($secret) < 32", self.proxy)
        self.assertIn("wp_http_validate_url($url)", self.proxy)

    def test_secret_is_never_leaked_in_configure_response_or_client_payload(self):
        self.assertIn("'runtime_enabled' => $enabled", self.proxy)
        self.assertIn("'runtime_url' => $url", self.proxy)
        self.assertNotIn("'runtime_secret' => $secret", self.proxy)
        self.assertNotIn("budly_sales_runtime_config", self.js)
        self.assertNotIn("prod_hmac", self.js)
        self.assertNotIn("prod_hmac", self.plugin)

    def test_durable_memory_remains_strictly_false(self):
        self.assertIn("'use_durable_memory' => false", self.proxy)
        self.assertIn("'durableMemoryEnabled' => false", self.plugin)


if __name__ == "__main__":
    unittest.main()
