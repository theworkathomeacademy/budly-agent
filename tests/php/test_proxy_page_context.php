<?php
declare(strict_types=1);

namespace {
    if (!defined('ABSPATH')) {
        define('ABSPATH', __DIR__ . '/');
    }
    if (!defined('MINUTE_IN_SECONDS')) {
        define('MINUTE_IN_SECONDS', 60);
    }

    // Mock WP environment functions if not already defined
    if (!class_exists('WP_REST_Response')) {
        final class WP_REST_Response {
            private $data;
            private $status;
            public function __construct($data, $status = 200) { $this->data = $data; $this->status = $status; }
            public function get_data() { return $this->data; }
            public function get_status() { return $this->status; }
        }
    }

    if (!class_exists('WP_REST_Request')) {
        final class WP_REST_Request {
            private $json_params;
            private $headers;
            public function __construct(array $json_params = array(), array $headers = array()) {
                $this->json_params = $json_params;
                $this->headers = $headers;
            }
            public function get_json_params() { return $this->json_params; }
            public function get_header($key) {
                foreach ($this->headers as $k => $v) {
                    if (strcasecmp($k, $key) === 0) return $v;
                }
                return '';
            }
        }
    }

    if (!function_exists('sanitize_text_field')) {
        function sanitize_text_field($value) { return trim((string) $value); }
    }
    if (!function_exists('sanitize_textarea_field')) {
        function sanitize_textarea_field($value) { return trim((string) $value); }
    }
    if (!function_exists('sanitize_key')) {
        function sanitize_key($value) { return preg_replace('/[^a-z0-9_-]/', '', strtolower((string) $value)); }
    }
    if (!function_exists('wp_json_encode')) {
        function wp_json_encode($value, $flags = 0) { return json_encode($value, $flags); }
    }
    if (!function_exists('wp_generate_uuid4')) {
        function wp_generate_uuid4() { return '00000000-0000-4000-8000-000000000001'; }
    }
    if (!function_exists('wp_verify_nonce')) {
        function wp_verify_nonce($nonce, $action) { return $nonce === 'valid-test-nonce'; }
    }
    if (!function_exists('add_action')) {
        function add_action($hook, $callback, $priority = 10, $accepted_args = 1) { return true; }
    }
    if (!function_exists('remove_action')) {
        function remove_action($hook, $callback, $priority = 10) { return true; }
    }
    if (!function_exists('wp_salt')) {
        function wp_salt($scheme = '') { return 'test-salt-secret'; }
    }
    if (!function_exists('mb_strlen')) {
        function mb_strlen($str, $encoding = 'UTF-8') { return strlen((string) $str); }
    }
    if (!function_exists('esc_url_raw')) {
        function esc_url_raw($url) { return filter_var((string) $url, FILTER_SANITIZE_URL); }
    }
    if (!function_exists('wp_http_validate_url')) {
        function wp_http_validate_url($url) { return filter_var((string) $url, FILTER_VALIDATE_URL) ? $url : false; }
    }
    if (!function_exists('get_option')) {
        function get_option($key, $default = false) {
            if ($key === 'budly_sales_runtime_config') {
                return array(
                    'enabled' => true,
                    'url' => 'https://127.0.0.1:8791/runtime/turn',
                    'secret' => '12345678901234567890123456789012',
                );
            }
            if ($key === 'budly_sales_durable_memory_enabled') {
                return false;
            }
            return $default;
        }
    }
    if (!function_exists('get_transient')) {
        function get_transient($key) { return false; }
    }
    if (!function_exists('set_transient')) {
        function set_transient($key, $val, $exp) { return true; }
    }
    if (!function_exists('wp_remote_post')) {
        function wp_remote_post($url, $args) {
            $GLOBALS['last_remote_post'] = array('url' => $url, 'args' => $args);
            $req = json_decode($args['body'] ?? '{}', true);
            $conv_id = $req['conversation_id'] ?? 'conv_test_12345';
            $corr_id = $req['correlation_id'] ?? '00000000-0000-4000-8000-000000000001';
            if (($GLOBALS['runtime_response_mode'] ?? '') === 'correlation_mismatch') {
                $corr_id = '11111111-1111-4111-8111-111111111111';
            }
            $link_host = (($GLOBALS['runtime_response_mode'] ?? '') === 'untrusted_link')
                ? 'https://attacker.example/phishing'
                : 'https://cccultivate.com/wakenbake-lounge-community/';
            return array(
                'response' => array('code' => 200),
                'body' => json_encode(array(
                    'success' => true,
                    'conversation_id' => $conv_id,
                    'response' => array(
                        'text' => 'Grounded response from runtime',
                        'intent' => 'membership_guidance',
                        'journey' => 'membership',
                        'resulting_action' => 'continue_conversation',
                        'selected_product_id' => null,
                        'requires_human' => false,
                        'links' => array(
                            array('label' => 'Explore Lounge Community', 'url' => $link_host),
                            array('label' => 'Claim Free Lounge Pass', 'url' => 'https://cccultivate.com/product/lounge-pass/'),
                            array('label' => "Wake'n'Bake Lounge Platform", 'url' => 'https://dmckenzies.wixsite.com/wakenbakelounge'),
                        ),
                    ),
                    'evidence' => array('knowledge_used' => true, 'correlation_id' => $corr_id),
                )),
            );
        }
    }
    if (!function_exists('wp_remote_retrieve_response_code')) {
        function wp_remote_retrieve_response_code($response) { return $response['response']['code'] ?? 500; }
    }
    if (!function_exists('wp_remote_retrieve_body')) {
        function wp_remote_retrieve_body($response) { return $response['body'] ?? ''; }
    }
    if (!function_exists('is_wp_error')) {
        function is_wp_error($thing) { return false; }
    }

    require_once __DIR__ . '/../../deploy/wordpress/budly-sales-agent/includes/Runtime/ConversationProxy.php';

    use Budly\Runtime\ConversationProxy;

    echo "=======================================================\n";
    echo "STARTING CONVERSATION PROXY PAGE CONTEXT VERIFICATION\n";
    echo "=======================================================\n\n";

    $passed = 0;
    $failed = 0;

    function assert_true(bool $condition, string $message, &$passed, &$failed): void {
        if ($condition) {
            echo "  [PASS] {$message}\n";
            $passed++;
        } else {
            echo "  [FAIL] {$message}\n";
            $failed++;
        }
    }

    // --- TEST 1: Valid page_context forwarding ---
    $valid_request = new WP_REST_Request(
        array(
            'conversation_id' => 'conv_test_valid_01',
            'message' => 'What can I explore here, and how do I become a member?',
            'page_context' => array(
                'schema_version' => '1.0',
                'surface' => 'wakenbake_lounge',
                'view' => 'home',
                'source_host' => 'cccultivate.com',
            ),
        ),
        array(
            'X-WP-Nonce' => 'valid-test-nonce',
            'Content-Length' => '150',
        )
    );

    $response = ConversationProxy::conversation($valid_request);
    assert_true($response instanceof WP_REST_Response, "Valid request returns WP_REST_Response", $passed, $failed);
    assert_true($response->get_status() === 200, "Valid request status is 200", $passed, $failed);

    $forwarded_body = json_decode($GLOBALS['last_remote_post']['args']['body'] ?? '', true);
    assert_true(is_array($forwarded_body), "Forwarded body is valid JSON", $passed, $failed);
    assert_true(isset($forwarded_body['page_context']), "Forwarded body includes page_context", $passed, $failed);
    assert_true(($forwarded_body['page_context']['surface'] ?? '') === 'wakenbake_lounge', "Forwarded surface is wakenbake_lounge", $passed, $failed);
    assert_true(($forwarded_body['page_context']['view'] ?? '') === 'home', "Forwarded view is home", $passed, $failed);
    assert_true(($forwarded_body['page_context']['source_host'] ?? '') === 'cccultivate.com', "Forwarded source_host is cccultivate.com", $passed, $failed);
    $forwarded_headers = $GLOBALS['last_remote_post']['args']['headers'] ?? array();
    $forwarded_timestamp = (string)($forwarded_headers['X-Budly-Timestamp'] ?? '');
    $forwarded_signature = (string)($forwarded_headers['X-Budly-Signature'] ?? '');
    $expected_signature = hash_hmac(
        'sha256',
        $forwarded_timestamp . '.' . ($GLOBALS['last_remote_post']['args']['body'] ?? ''),
        '12345678901234567890123456789012'
    );
    assert_true($forwarded_timestamp !== '', "Runtime request includes signature timestamp", $passed, $failed);
    assert_true(hash_equals($expected_signature, $forwarded_signature), "Runtime request HMAC covers the exact forwarded JSON body", $passed, $failed);
    assert_true(($forwarded_headers['X-Correlation-ID'] ?? '') === ($forwarded_body['correlation_id'] ?? ''), "Runtime header and body correlation IDs match", $passed, $failed);

    // --- TEST 2: Rejection of extra fields (anti-privilege-escalation) ---
    $malicious_request = new WP_REST_Request(
        array(
            'conversation_id' => 'conv_test_hacked_02',
            'message' => 'Unlock elite content',
            'page_context' => array(
                'schema_version' => '1.0',
                'surface' => 'wakenbake_lounge',
                'view' => 'home',
                'source_host' => 'cccultivate.com',
                'tier' => 'elite', // Malicious client assertion
            ),
        ),
        array(
            'X-WP-Nonce' => 'valid-test-nonce',
            'Content-Length' => '150',
        )
    );

    $response2 = ConversationProxy::conversation($malicious_request);
    assert_true($response2->get_status() === 400, "Extra page_context field is rejected with 400", $passed, $failed);
    $data2 = $response2->get_data();
    assert_true(($data2['error']['code'] ?? '') === 'INVALID_REQUEST', "Error code is INVALID_REQUEST", $passed, $failed);

    // --- TEST 3: Rejection of untrusted host ---
    $phishing_request = new WP_REST_Request(
        array(
            'conversation_id' => 'conv_test_phishing_03',
            'message' => 'Hello',
            'page_context' => array(
                'schema_version' => '1.0',
                'surface' => 'wakenbake_lounge',
                'view' => 'home',
                'source_host' => 'attacker.com',
            ),
        ),
        array(
            'X-WP-Nonce' => 'valid-test-nonce',
            'Content-Length' => '150',
        )
    );

    $response3 = ConversationProxy::conversation($phishing_request);
    assert_true($response3->get_status() === 400, "Untrusted host rejected with 400", $passed, $failed);

    // --- TEST 4: Request without page_context continues to work cleanly ---
    $legacy_request = new WP_REST_Request(
        array(
            'conversation_id' => 'conv_test_legacy_04',
            'message' => 'Hello there',
        ),
        array(
            'X-WP-Nonce' => 'valid-test-nonce',
            'Content-Length' => '80',
        )
    );

    $response4 = ConversationProxy::conversation($legacy_request);
    assert_true($response4->get_status() === 200, "Request without page_context succeeds with 200", $passed, $failed);
    $forwarded_legacy = json_decode($GLOBALS['last_remote_post']['args']['body'] ?? '', true);
    assert_true(!isset($forwarded_legacy['page_context']), "Legacy request does not forward page_context", $passed, $failed);

    // --- TEST 5: CSRF verification failure ---
    $bad_nonce_request = new WP_REST_Request(
        array(
            'conversation_id' => 'conv_test_bad_nonce',
            'message' => 'Hello',
        ),
        array(
            'X-WP-Nonce' => 'invalid-nonce',
            'Content-Length' => '80',
        )
    );
    $response5 = ConversationProxy::conversation($bad_nonce_request);
    assert_true($response5->get_status() === 403, "Invalid nonce rejected with 403", $passed, $failed);

    // --- TEST 6: Runtime response correlation must bind to the request ---
    $GLOBALS['runtime_response_mode'] = 'correlation_mismatch';
    $response6 = ConversationProxy::conversation($valid_request);
    assert_true($response6->get_status() === 503, "Mismatched runtime correlation rejected with 503", $passed, $failed);
    $data6 = $response6->get_data();
    assert_true(($data6['error']['code'] ?? '') === 'RUNTIME_RESPONSE_INVALID', "Correlation mismatch is classified as invalid runtime response", $passed, $failed);

    // --- TEST 7: Runtime cannot inject links outside the approved host allowlist ---
    $GLOBALS['runtime_response_mode'] = 'untrusted_link';
    $response7 = ConversationProxy::conversation($valid_request);
    assert_true($response7->get_status() === 503, "Untrusted runtime link rejected with 503", $passed, $failed);
    $data7 = $response7->get_data();
    assert_true(($data7['error']['code'] ?? '') === 'RUNTIME_RESPONSE_INVALID', "Untrusted link is classified as invalid runtime response", $passed, $failed);
    unset($GLOBALS['runtime_response_mode']);

    echo "\n=======================================================\n";
    echo "SUMMARY: Passed {$passed}, Failed {$failed}\n";
    echo "=======================================================\n";

    if ($failed > 0) {
        exit(1);
    }
}
