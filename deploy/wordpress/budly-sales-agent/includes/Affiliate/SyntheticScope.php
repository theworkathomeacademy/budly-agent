<?php
namespace Budly\Affiliate;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

/** Server-side G9E synthetic identity boundary. Client input is never read. */
final class SyntheticScope {
    const CLASSIFICATION = 'TEST_SYNTHETIC_NON_PRODUCTION_PERSON';
    const OPTION = 'budly_g9e_authoritative_synthetic_scope';

    public static function authorize_portal($wordpress_user_id) {
        $gate = FeatureFlags::enabled('affiliate_portal_enabled');
        $scope = get_option(self::OPTION, array());
        $allowed = false;
        $reason = 'GLOBAL_GATE_OFF';

        if ($gate) {
            if (!is_array($scope) || empty($scope['active']) || ($scope['classification'] ?? '') !== self::CLASSIFICATION) {
                $reason = 'TRUSTED_SYNTHETIC_SCOPE_MISSING_OR_INVALID';
            } elseif (empty($scope['expires_at']) || strtotime((string) $scope['expires_at']) <= time()) {
                $reason = 'TRUSTED_SYNTHETIC_SCOPE_EXPIRED';
            } elseif (current_user_can('manage_options')) {
                $reason = 'OWNER_AFFILIATE_IMPERSONATION_DENIED';
            } elseif ((int) ($scope['wordpress_user_id'] ?? 0) !== (int) $wordpress_user_id) {
                $reason = 'WORDPRESS_IDENTITY_MAPPING_MISMATCH';
            } elseif (empty($scope['affiliate_id']) || !preg_match('/^AFF-[0-9]{6}$/', (string) ($scope['affiliate_code'] ?? ''))) {
                $reason = 'AFFILIATE_SCOPE_MISMATCH';
            } else {
                $allowed = true;
                $reason = 'TRUSTED_SYNTHETIC_PORTAL_MATCH';
            }
        }

        self::audit('portal', $wordpress_user_id, $scope, $gate, $allowed, $reason);
        return array('allowed' => $allowed, 'reason' => $reason, 'scope' => $allowed ? $scope : array());
    }

    private static function audit($operation, $actor, $scope, $gate_state, $allowed, $reason) {
        global $wpdb;
        try {
            $wpdb->insert(
                Config::table('audit'),
                array(
                    'audit_id' => 'AUD-' . strtoupper(wp_generate_password(12, false, false)),
                    'event_type' => 'AFFILIATE_SYNTHETIC_SCOPE_' . ($allowed ? 'ALLOW' : 'DENY'),
                    'actor_type' => 'WORDPRESS_USER',
                    'actor_id' => (string) $actor,
                    'customer_reference' => sanitize_text_field((string) ($scope['affiliate_code'] ?? '')),
                    'payload_json' => wp_json_encode(array(
                        'operation' => $operation,
                        'synthetic_identity' => (string) ($scope['affiliate_code'] ?? ''),
                        'gate_name' => 'affiliate_portal_enabled',
                        'gate_state' => (bool) $gate_state,
                        'scope_result' => $allowed ? 'MATCH' : 'NO_MATCH',
                        'decision' => $allowed ? 'ALLOW' : 'DENY',
                        'reason' => $reason,
                        'timestamp' => current_time('mysql', true),
                    )),
                    'created_at' => current_time('mysql', true),
                ),
                array('%s','%s','%s','%s','%s','%s','%s')
            );
        } catch (\Throwable $ignored) {
            // Authorization remains fail-closed even when audit persistence fails.
        }
    }
}
