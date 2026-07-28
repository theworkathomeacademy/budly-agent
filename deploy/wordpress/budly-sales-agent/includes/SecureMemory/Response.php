<?php
namespace Budly\SecureMemory;

if (!defined('ABSPATH')) { exit; }

final class Response {
    private static function meta($request_id = '') {
        return array(
            'request_id' => $request_id ?: Validation::request_id(),
            'api_version' => Config::API_VERSION,
            'timestamp' => gmdate('c'),
        );
    }

    public static function success($data = array(), $status = 200, $request_id = '') {
        return new \WP_REST_Response(array(
            'success' => true,
            'data' => $data,
            'meta' => self::meta($request_id),
        ), $status);
    }

    public static function error($code, $message, $status, $request_id = '', $details = array()) {
        return new \WP_REST_Response(array(
            'success' => false,
            'error' => array(
                'code' => sanitize_key($code) ? strtoupper($code) : Errors::INTERNAL_ERROR,
                'message' => sanitize_text_field($message),
                'details' => is_array($details) ? $details : array(),
            ),
            'meta' => self::meta($request_id),
        ), $status);
    }
}
