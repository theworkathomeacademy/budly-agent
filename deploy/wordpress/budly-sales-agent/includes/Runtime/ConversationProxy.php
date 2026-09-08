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
    }

    public static function enabled() {
        return defined('BUDLY_CONVERSATIONAL_RUNTIME_ENABLED') && BUDLY_CONVERSATIONAL_RUNTIME_ENABLED === true;
    }

    public static function durable_memory_enabled() {
        return defined('BUDLY_DURABLE_MEMORY_ENABLED') && BUDLY_DURABLE_MEMORY_ENABLED === true;
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
        if (!preg_match('/^conv_[A-Za-z0-9_-]{6,55}$/', $conversation) || $message === '' || self::length($message) > self::MAX_MESSAGE_CHARS) {
            return self::error('INVALID_REQUEST', 'The conversation request is invalid.', 400);
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
        $remote = wp_safe_remote_post($configuration['url'], array(
            'timeout' => self::RUNTIME_TIMEOUT_SECONDS,
            'redirection' => 0,
            'headers' => array(
                'Content-Type' => 'application/json',
                'X-Budly-Timestamp' => $timestamp,
                'X-Budly-Signature' => $signature,
                'X-Correlation-ID' => $correlation,
            ),
            'body' => $body,
        ));
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
        if (!$url || strlen($secret) < 32 || !wp_http_validate_url($url)) return array('error' => true);
        if (strpos($url, 'https://') !== 0 && !preg_match('#^http://(?:127\.0\.0\.1|localhost)(?::\d+)?/#', $url)) return array('error' => true);
        return array('url' => rtrim($url, '/') . '/v1/conversation', 'secret' => $secret);
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
