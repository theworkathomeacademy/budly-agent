<?php
namespace Budly\SecureMemory;

if (!defined('ABSPATH')) { exit; }

final class Validation {
    public static function normalize_email($email) {
        return strtolower(trim(sanitize_email((string) $email)));
    }

    public static function email_hash($email) {
        $normalized = self::normalize_email($email);
        return $normalized ? hash_hmac('sha256', $normalized, wp_salt('auth')) : '';
    }

    public static function request_id() {
        return 'req_' . bin2hex(random_bytes(12));
    }

    public static function opaque_id($prefix) {
        return sanitize_key($prefix) . '_' . bin2hex(random_bytes(13));
    }

    public static function bounded_text($value, $max) {
        $value = sanitize_text_field((string) $value);
        if (strlen($value) > $max) {
            throw new \InvalidArgumentException('Value exceeds the allowed length.');
        }
        return $value;
    }

    public static function json_request(\WP_REST_Request $request) {
        $content_type = strtolower((string) $request->get_header('content-type'));
        if (strpos($content_type, 'application/json') !== 0) {
            return new \WP_Error(Errors::INVALID_REQUEST, 'Content-Type must be application/json.', array('status'=>415));
        }
        $raw = (string) $request->get_body();
        if (strlen($raw) > Config::MAX_JSON_BYTES) {
            return new \WP_Error(Errors::INVALID_REQUEST, 'The request is too large.', array('status'=>413));
        }
        $params = $request->get_json_params();
        if (!is_array($params)) {
            return new \WP_Error(Errors::INVALID_REQUEST, 'The JSON request is invalid.', array('status'=>400));
        }
        return $params;
    }
}
