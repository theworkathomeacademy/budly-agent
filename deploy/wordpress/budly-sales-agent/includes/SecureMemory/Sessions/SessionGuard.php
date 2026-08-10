<?php
namespace Budly\SecureMemory\Sessions;

use Budly\SecureMemory\Errors;
use Budly\SecureMemory\Response;

if (!defined('ABSPATH')) { exit; }

final class SessionGuard {
    public static function require_session(\WP_REST_Request $request, $require_csrf = false) {
        $service = SessionService::instance();
        $session = $service->validate(true);
        if (!empty($session['error'])) {
            $errors = array(
                'SESSION_EXPIRED' => array(Errors::SESSION_EXPIRED, 'Your session has expired. Please verify your email again.'),
                'SESSION_REVOKED' => array(Errors::SESSION_REVOKED, 'Your session is no longer active. Please verify your email again.'),
                'SESSION_INVALID' => array(Errors::SESSION_INVALID, 'Your session is invalid. Please verify your email again.'),
            );
            $failure = isset($errors[$session['error']])
                ? $errors[$session['error']]
                : array(Errors::AUTHENTICATION_REQUIRED, 'A verified customer session is required.');
            return Response::error($failure[0], $failure[1], 401);
        }
        if ($require_csrf && !$service->csrf_is_valid($session, $request->get_header('X-Budly-CSRF'))) {
            return Response::error(Errors::CSRF_VALIDATION_FAILED, 'The security token is missing or invalid.', 403);
        }
        return $session;
    }

    public static function verified_customer_id(\WP_REST_Request $request, $require_csrf = false) {
        $session = self::require_session($request, $require_csrf);
        if ($session instanceof \WP_REST_Response) {
            return $session;
        }

        if (!is_array($session) || !isset($session['customer_id']) || !is_numeric($session['customer_id']) || (int) $session['customer_id'] < 1) {
            return Response::error(
                Errors::AUTHENTICATION_REQUIRED,
                'A verified customer session is required.',
                401
            );
        }

        return (int) $session['customer_id'];
    }
}
