<?php
namespace Budly\Runtime;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Database\Repository;
use Budly\SecureMemory\Decision\DecisionRepository;
use Budly\SecureMemory\Decision\DecisionService;
use Budly\SecureMemory\Consent\ConsentRepository;

if (!defined('ABSPATH')) { exit; }

final class ConversationProxy {
    const NAMESPACE = 'budly-runtime/v1';
    const MAX_REQUEST_BYTES = 16384;
    const MAX_MESSAGE_CHARS = 4000;
    const RUNTIME_TIMEOUT_SECONDS = 18;

    public static function register() {
        add_action('rest_api_init', array(__CLASS__, 'register_routes'));
    }

    public static function register_routes() {
        register_rest_route(self::NAMESPACE, '/conversation', array(
            'methods' => 'POST',
            'callback' => array(__CLASS__, 'conversation'),
            'permission_callback' => '__return_true',
        ));
        register_rest_route(self::NAMESPACE, '/configure', array(
            'methods' => 'POST',
            'callback' => array(__CLASS__, 'configure'),
            'permission_callback' => '__return_true',
        ));
    }

    public static function enabled() {
        if (defined('BUDLY_CONVERSATIONAL_RUNTIME_ENABLED')) {
            return BUDLY_CONVERSATIONAL_RUNTIME_ENABLED === true;
        }
        $stored = self::stored_configuration();
        return !empty($stored['enabled']);
    }

    public static function durable_memory_enabled() {
        return defined('BUDLY_DURABLE_MEMORY_ENABLED') && BUDLY_DURABLE_MEMORY_ENABLED === true;
    }

    public static function configure(\WP_REST_Request $request) {
        $timestamp = (string) $request->get_header('X-Budly-Timestamp');
        $signature = (string) $request->get_header('X-Budly-Signature');
        $body = (string) $request->get_body();
        $params = $request->get_json_params();
        if (!is_array($params) || empty($params['runtime_secret']) || empty($params['runtime_url'])) {
            return self::error('INVALID_REQUEST', 'Runtime configuration is incomplete.', 400);
        }
        $secret = (string) $params['runtime_secret'];
        $url = esc_url_raw((string) $params['runtime_url']);
        $enabled = !empty($params['runtime_enabled']);
        if (strlen($secret) < 32 || (!wp_http_validate_url($url) && !filter_var($url, FILTER_VALIDATE_URL))) {
            return self::error('INVALID_REQUEST', 'Runtime configuration values are invalid.', 400);
        }
        if (strpos($url, 'https://') !== 0 && !preg_match('#^http://(?:127\.0\.0\.1|localhost)(?::\d+)?/#', $url)) {
            return self::error('INVALID_REQUEST', 'Runtime URL must use HTTPS.', 400);
        }
        $sent = (int) $timestamp;
        if (abs(time() - $sent) > 300) {
            return self::error('AUTHENTICATION_FAILED', 'Signature timestamp is outside the allowed window.', 401);
        }
        $expected = hash_hmac('sha256', $timestamp . '.' . $body, $secret);
        if (!hash_equals($expected, $signature)) {
            return self::error('AUTHENTICATION_FAILED', 'HMAC signature verification failed.', 401);
        }
        $config = array(
            'enabled' => $enabled,
            'url' => $url,
            'secret' => $secret,
            'updated_at' => time(),
        );
        update_option('budly_sales_runtime_config', $config, false);
        return new \WP_REST_Response(array(
            'success' => true,
            'data' => array(
                'runtime_enabled' => $enabled,
                'runtime_url' => $url,
                'status' => 'configured'
            )
        ), 200);
    }

    public static function conversation(\WP_REST_Request $request) {
        if (!self::enabled()) return self::error('RUNTIME_DISABLED', 'The conversational runtime is disabled.', 503);
        if (self::durable_memory_enabled()) return self::error('CONFIGURATION_INVALID', 'Durable memory is unavailable in this release.', 503);
        $nonce = $request->get_header('X-WP-Nonce');
        if (!$nonce || !wp_verify_nonce($nonce, 'wp_rest')) return self::error('CSRF_VALIDATION_FAILED', 'The request security token is invalid.', 403);
        $content_length = (int) $request->get_header('Content-Length');
        if ($content_length < 2 || $content_length > self::MAX_REQUEST_BYTES) return self::error('INVALID_REQUEST', 'The request is invalid.', 400);
        if (!self::rate_allowed()) return self::error('RATE_LIMITED', 'Please wait before sending more messages.', 429);
        $params = $request->get_json_params();
        if (!is_array($params) || array_diff(array_keys($params), array('conversation_id','message','reset'))) return self::error('INVALID_REQUEST', 'The request is invalid.', 400);
        $conversation = sanitize_text_field((string)($params['conversation_id'] ?? ''));
        $message = sanitize_textarea_field((string)($params['message'] ?? ''));
        $reset = !empty($params['reset']);
        if (!preg_match('/^conv_[A-Za-z0-9_-]{6,55}$/', $conversation) || mb_strlen($message) < 1 || mb_strlen($message) > self::MAX_MESSAGE_CHARS) {
            return self::error('INVALID_REQUEST', 'The request is invalid.', 400);
        }
        $configuration = self::configuration();
        if (isset($configuration['error'])) return self::error('RUNTIME_UNAVAILABLE', 'The conversational runtime is unavailable.', 503);
        $correlation = wp_generate_uuid4();
        $runtime_request = array(
            'conversation_id' => $conversation,
            'message' => $message,
            'correlation_id' => $correlation,
            'channel' => 'ccc_website',
            'reset' => $reset,
            'use_durable_memory' => false,
            'deterministic_context' => self::deterministic_context($conversation, $message),
        );
        $body = wp_json_encode($runtime_request, JSON_UNESCAPED_SLASHES);
        $timestamp = (string) time();
        $signature = hash_hmac('sha256', $timestamp . '.' . $body, $configuration['secret']);
        $http_args = array(
            'timeout' => self::RUNTIME_TIMEOUT_SECONDS,
            'redirection' => 0,
            'headers' => array(
                'Content-Type' => 'application/json',
                'User-Agent' => 'BudlySalesAgent/1.8.8',
                'X-Budly-Timestamp' => $timestamp,
                'X-Budly-Signature' => $signature,
                'X-Correlation-ID' => $correlation,
            ),
            'body' => $body,
        );
        $resolve_hook = function($handle, $r, $url) {
            if (defined('CURLOPT_RESOLVE')) {
                $host = (string) parse_url($url, PHP_URL_HOST);
                if ($host === 'runtime.cccultivate.com') {
                    @curl_setopt($handle, CURLOPT_RESOLVE, array(
                        'runtime.cccultivate.com:443:104.21.36.216',
                        'runtime.cccultivate.com:443:172.67.199.195',
                        'runtime.cccultivate.com:443:104.21.36.185',
                    ));
                }
            }
        };
        add_action('http_api_curl', $resolve_hook, 10, 3);
        $remote = wp_remote_post($configuration['url'], $http_args);
        remove_action('http_api_curl', $resolve_hook, 10);
        if (is_wp_error($remote) && function_exists('wp_safe_remote_post')) {
            $remote = wp_safe_remote_post($configuration['url'], $http_args);
        }
        if (is_wp_error($remote)) {
            self::audit($correlation, 'failure', 'RUNTIME_UNAVAILABLE');
            return self::error('RUNTIME_UNAVAILABLE', 'The conversational runtime is temporarily unavailable.', 503, $correlation);
        }
        $status = (int) wp_remote_retrieve_response_code($remote);
        $decoded = json_decode((string) wp_remote_retrieve_body($remote), true);
        if ($status !== 200 || !self::valid_runtime_response($decoded, $conversation, $correlation, $runtime_request['deterministic_context'])) {
            self::audit($correlation, 'failure', 'RUNTIME_RESPONSE_INVALID');
            return self::error('RUNTIME_RESPONSE_INVALID', 'The conversational response could not be validated.', 503, $correlation);
        }
        self::audit($correlation, 'success', '');
        return new \WP_REST_Response(array(
            'success' => true,
            'data' => array(
                'conversation_id' => $conversation,
                'response' => $decoded['response'],
                'evidence' => array('correlation_id' => $correlation, 'knowledge_used' => !empty($decoded['evidence']['knowledge_used'])),
            ),
        ), 200);
    }

    private static function configuration() {
        $url = defined('BUDLY_CONVERSATIONAL_RUNTIME_URL') ? esc_url_raw(BUDLY_CONVERSATIONAL_RUNTIME_URL) : '';
        $secret = defined('BUDLY_CONVERSATIONAL_RUNTIME_SECRET') ? (string) BUDLY_CONVERSATIONAL_RUNTIME_SECRET : '';
        if (!$url || strlen($secret) < 32) {
            $stored = self::stored_configuration();
            if (empty($url) && !empty($stored['url'])) {
                $url = esc_url_raw($stored['url']);
            }
            if (empty($secret) && !empty($stored['secret'])) {
                $secret = (string) $stored['secret'];
            }
        }
        if (!$url || strlen($secret) < 32 || (!wp_http_validate_url($url) && !filter_var($url, FILTER_VALIDATE_URL))) return array('error' => true);
        if (strpos($url, 'https://') !== 0 && !preg_match('#^http://(?:127\.0\.0\.1|localhost)(?::\d+)?/#', $url)) return array('error' => true);
        return array('url' => rtrim($url, '/') . '/v1/conversation', 'secret' => $secret);
    }

    private static function stored_configuration() {
        $option = get_option('budly_sales_runtime_config', array());
        if (!is_array($option)) {
            return array();
        }
        return array(
            'enabled' => !empty($option['enabled']),
            'url' => isset($option['url']) ? (string) $option['url'] : '',
            'secret' => isset($option['secret']) ? (string) $option['secret'] : '',
        );
    }

    private static function deterministic_context($conversation, $message) {
        $lower = strtolower($message);
        $risk = preg_match('/\b(diagnose|treat|treatment|cure|cancer|dosage|dose|medication|hospital|under 18|under 21|legal advice)\b/', $lower);
        $commercial = preg_match('/\b(product|book|course|coloring|buy|price|cost|membership|wholesale|tincture|butter|oil)\b/', $lower);
        $journey = self::journey($lower);
        if (!$risk && !$commercial) return array('journey' => $journey, 'outcome' => 'conversation', 'selected_product_id' => null, 'resulting_action' => 'continue_conversation');
        try {
            $service = new DecisionService(new DecisionRepository(), new ConsentRepository(), new AuditService(new Repository()));
            return array_intersect_key($service->evaluate(array(
                'conversation_id' => $conversation,
                'journey' => $journey,
                'objective' => $message,
                'answers' => $commercial ? array($message, 'current catalog', 'customer conversation') : array(),
                'use_memory' => false,
            ), array()), array_flip(array('outcome','selected_product_id','confidence','resulting_action'))) + array('journey' => $journey);
        } catch (\Throwable $error) {
            return array('journey' => $journey, 'outcome' => 'human_review', 'selected_product_id' => null, 'resulting_action' => 'human_escalation');
        }
    }

    private static function journey($message) {
        if (preg_match('/\b(wholesale|bulk|white label|resell|business)\b/', $message)) return 'wholesale';
        if (preg_match('/\b(nft|membership|bronze|copper|titanium|platinum)\b/', $message)) return 'membership';
        if (preg_match('/\b(cook|culinary|infused oil)\b/', $message)) return 'culinary';
        if (preg_match('/\b(book|guide|learn|course|class|grow|botanical|coloring|terpene|endocannabinoid|ecs)\b/', $message)) return 'education';
        return 'wellness';
    }

    private static function valid_runtime_response($value, $conversation, $correlation, $deterministic) {
        if (!is_array($value) || ($value['success'] ?? false) !== true || ($value['conversation_id'] ?? '') !== $conversation) return false;
        if (($value['evidence']['correlation_id'] ?? '') !== $correlation || !is_array($value['response'] ?? null)) return false;
        $response = $value['response'];
        if (array_diff(array('text','intent','journey','resulting_action','selected_product_id','requires_human'), array_keys($response))) return false;
        if (!is_string($response['text']) || trim($response['text']) === '' || self::length($response['text']) > 4000) return false;
        if (!in_array($response['resulting_action'], array('continue_conversation','legacy_guided_flow','human_handoff','safe_no_match'), true)) return false;
        if (!is_bool($response['requires_human'])) return false;
        if (isset($response['links'])) {
            if (!is_array($response['links']) || count($response['links']) > 3) return false;
            foreach ($response['links'] as $link) {
                if (!is_array($link) || array_diff(array('label','url'), array_keys($link))) return false;
                $url = esc_url_raw((string) $link['url']);
                $host = strtolower((string) parse_url($url, PHP_URL_HOST));
                if (!$url || !in_array($host, array('cccultivate.com','wakenbakelounge.com','www.wakenbakelounge.com','dmckenzies.wixsite.com','learn.cccultivate.com'), true)) return false;
                if (trim((string) $link['label']) === '' || self::length((string) $link['label']) > 80) return false;
            }
        }
        $authoritative = $deterministic['selected_product_id'] ?? null;
        if ($response['selected_product_id'] !== null && $response['selected_product_id'] !== $authoritative) return false;
        if (($deterministic['outcome'] ?? '') === 'human_review' && (!$response['requires_human'] || $response['resulting_action'] !== 'human_handoff')) return false;
        return true;
    }

    private static function rate_allowed() {
        $ip = isset($_SERVER['REMOTE_ADDR']) ? (string) $_SERVER['REMOTE_ADDR'] : 'unknown';
        $key = 'budly_runtime_rate_' . hash_hmac('sha256', $ip, wp_salt('nonce'));
        $count = (int) get_transient($key);
        if ($count >= 60) return false;
        set_transient($key, $count + 1, MINUTE_IN_SECONDS);
        return true;
    }

    private static function audit($correlation, $status, $error) {
        try {(new AuditService(new Repository()))->record('runtime.conversation_turn','visitor','anonymous',$status,$status === 'success' ? 'informational' : 'warning',array('metadata'=>array('correlation_id'=>$correlation,'error_classification'=>$error,'durable_memory'=>false)));} catch (\Throwable $ignored) {}
    }

    private static function error($code, $message, $status, $correlation = '') {
        return new \WP_REST_Response(array('success'=>false,'error'=>array('code'=>$code,'message'=>$message),'meta'=>array('correlation_id'=>$correlation)), $status);
    }

    private static function length($value) {return function_exists('mb_strlen') ? mb_strlen($value, 'UTF-8') : strlen($value);}
}
