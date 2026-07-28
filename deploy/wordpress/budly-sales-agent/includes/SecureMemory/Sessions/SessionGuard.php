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
            $expired = $session['error'] === 'SESSION_EXPIRED';
            return Response::error($expired ? Errors::SESSION_EXPIRED : Errors::AUTHENTICATION_REQUIRED, $expired ? 'Your session has expired. Please verify your email again.' : 'A verified customer session is required.', 401);
        }
        if ($require_csrf && !$service->csrf_is_valid($session, $request->get_header('X-Budly-CSRF'))) {
            return Response::error(Errors::CSRF_VALIDATION_FAILED, 'The security token is missing or invalid.', 403);
        }
        return $session;
    }
}
