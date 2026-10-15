"""Operational non-production WordPress-to-Runtime round-trip verification.

Spins up the actual Python ProductionConversationRuntime HTTP service on loopback,
configures PHP WordPress ConversationProxy with local URL and shared secret,
and executes real turns from Python direct HTTP and from live PHP CLI through Python runtime and back.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
import time
import unittest
import uuid
from pathlib import Path

from src.budly_runtime.config import ProductionSettings
from src.budly_runtime.http_service import make_server
from src.budly_runtime.model import ProviderResult
from src.budly_runtime.production_runtime import ProductionConversationRuntime

ROOT = Path(__file__).resolve().parents[1]
SHARED_SECRET = "operational-test-secret-32-chars-long!"
CONFIG_BOOTSTRAP = "bootstrap-secret-must-be-32-chars-ok!"


class StagingModelDouble:
    def __init__(self) -> None:
        self.turns: list[dict] = []

    def generate(self, request) -> ProviderResult:
        self.turns.append(request)
        return ProviderResult(
            {
                "text": "Welcome to the Wake'n'Bake Lounge! You can explore the community, claim a free Lounge Pass, or join Member and Elite tiers.",
                "intent": "membership_guidance",
                "journey": "membership",
                "resulting_action": "continue_conversation",
                "selected_product_id": None,
                "requires_human": False,
            },
            "test_staging_adapter",
            "gpt-5.6-luna",
        )


class TestOperationalWPToRuntimeRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 1. Setup local production runtime settings
        settings = ProductionSettings(
            "staging",
            "127.0.0.1",
            0,
            SHARED_SECRET,
            "openai",
            "gpt-5.6-luna",
            "staging-fake-key",
            ROOT / "config",
        )
        cls.model = StagingModelDouble()
        cls.runtime = ProductionConversationRuntime(settings, ROOT, model_adapter=cls.model)
        cls.server = make_server(settings, ROOT, runtime=cls.runtime)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_direct_python_http_roundtrip(self):
        """Verify the Python HTTP runtime receives signed requests and returns valid grounded turns."""
        import urllib.request
        corr_id = str(uuid.uuid4())
        body = json.dumps({
            "conversation_id": "conv_direct_test_1",
            "message": "What tiers exist in the Lounge?",
            "page_context": {
                "schema_version": "1.0",
                "surface": "wakenbake_lounge",
                "view": "home",
                "source_host": "cccultivate.com",
            },
            "correlation_id": corr_id,
        }).encode("utf-8")
        stamp = str(int(time.time()))
        sig = hmac.new(SHARED_SECRET.encode("utf-8"), stamp.encode("utf-8") + b"." + body, hashlib.sha256).hexdigest()
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/conversation",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Budly-Timestamp": stamp,
                "X-Budly-Signature": sig,
                "X-Correlation-ID": corr_id,
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["success"])
            self.assertEqual(data["conversation_id"], "conv_direct_test_1")
            self.assertIn("Wake'n'Bake Lounge", data["response"]["text"])
            self.assertEqual(data["response"]["links"][0]["url"], "https://cccultivate.com/wakenbake-lounge-community/")

    def test_live_php_wordpress_conversation_proxy_to_python_runtime(self):
        """Execute genuine PHP CLI executing ConversationProxy calling the loopback runtime over HTTP."""
        php_code = f"""
define('ABSPATH', '{ROOT.as_posix()}/');
define('MINUTE_IN_SECONDS', 60);

class WP_REST_Response {{
    private $data;
    private $status;
    public function __construct($data, $status = 200) {{ $this->data = $data; $this->status = $status; }}
    public function get_data() {{ return $this->data; }}
    public function get_status() {{ return $this->status; }}
}}

class WP_REST_Request {{
    private $json_params;
    private $headers;
    public function __construct(array $json_params = array(), array $headers = array()) {{
        $this->json_params = $json_params;
        $this->headers = $headers;
    }}
    public function get_json_params() {{ return $this->json_params; }}
    public function get_header($key) {{
        foreach ($this->headers as $k => $v) {{
            if (strcasecmp($k, $key) === 0) return $v;
        }}
        return '';
    }}
}}

function sanitize_text_field($value) {{ return trim((string) $value); }}
function sanitize_textarea_field($value) {{ return trim((string) $value); }}
function sanitize_key($value) {{ return preg_replace('/[^a-z0-9_-]/', '', strtolower((string) $value)); }}
function wp_json_encode($value, $flags = 0) {{ return json_encode($value, $flags); }}
function wp_generate_uuid4() {{ return '12345678-1234-4000-8000-123456789abc'; }}
function wp_verify_nonce($nonce, $action) {{ return true; }}
function add_action($hook, $callback, $priority = 10, $accepted_args = 1) {{ return true; }}
function remove_action($hook, $callback, $priority = 10) {{ return true; }}
function wp_salt($scheme = '') {{ return 'test-salt-secret-32-chars-ok!'; }}
function esc_url_raw($url) {{ return filter_var((string) $url, FILTER_SANITIZE_URL); }}
function wp_http_validate_url($url) {{ return filter_var((string) $url, FILTER_VALIDATE_URL) ? $url : false; }}
function is_wp_error($thing) {{ return false; }}
function wp_remote_retrieve_response_code($response) {{ return $response['response']['code'] ?? 0; }}
function wp_remote_retrieve_body($response) {{ return $response['body'] ?? ''; }}

$GLOBALS['_wp_options'] = array(
    'budly_sales_runtime_config' => array(
        'enabled' => true,
        'url' => 'http://127.0.0.1:{self.port}/',
        'secret' => '{SHARED_SECRET}',
    )
);

function get_option($key, $default = false) {{
    return $GLOBALS['_wp_options'][$key] ?? $default;
}}
function update_option($key, $val, $autoload = null) {{
    $GLOBALS['_wp_options'][$key] = $val;
    return true;
}}
function get_transient($key) {{ return false; }}
function set_transient($key, $val, $exp) {{ return true; }}

function wp_remote_post($url, $args) {{
    $headers = array();
    foreach ($args['headers'] as $k => $v) {{
        $headers[] = "$k: $v";
    }}
    $opts = array(
        'http' => array(
            'method' => 'POST',
            'header' => implode("\\r\\n", $headers),
            'content' => $args['body'],
            'timeout' => 5,
            'ignore_errors' => true,
        )
    );
    $ctx = stream_context_create($opts);
    $resp = @file_get_contents($url, false, $ctx);
    $code = 200;
    if (isset($http_response_header) && count($http_response_header) > 0) {{
        if (preg_match('#HTTP/\\S+\\s+(\\d+)#', $http_response_header[0], $m)) {{
            $code = (int) $m[1];
        }}
    }}
    return array(
        'response' => array('code' => $code),
        'body' => $resp,
    );
}}

require_once '{ROOT.as_posix()}/deploy/wordpress/budly-sales-agent/includes/Runtime/ConversationProxy.php';

$req = new WP_REST_Request(
    array(
        'conversation_id' => 'conv_roundtrip_test_9999',
        'message' => 'Tell me about the Wake n Bake Lounge community pass',
        'page_context' => array(
            'schema_version' => '1.0',
            'surface' => 'wakenbake_lounge',
            'view' => 'home',
            'source_host' => 'cccultivate.com'
        )
    ),
    array(
        'X-WP-Nonce' => 'valid-nonce',
        'Content-Length' => '250'
    )
);

$res = Budly\\Runtime\\ConversationProxy::conversation($req);
echo json_encode(array(
    'status' => $res->get_status(),
    'data' => $res->get_data(),
));
"""
        proc = subprocess.run(
            ["php", "-r", php_code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0, f"PHP error: {proc.stderr} | stdout: {proc.stdout}")
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], 200, f"Result was: {result}")
        self.assertTrue(result["data"]["success"])
        payload = result["data"]["data"]
        self.assertEqual(payload["conversation_id"], "conv_roundtrip_test_9999")
        self.assertIn("Wake'n'Bake Lounge", payload["response"]["text"])
        self.assertEqual(payload["evidence"]["correlation_id"], "12345678-1234-4000-8000-123456789abc")


if __name__ == "__main__":
    unittest.main()
