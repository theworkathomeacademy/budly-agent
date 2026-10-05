<?php
namespace Budly\Affiliate;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class InvitationService {
    public static function create_invitation($email = '', $intended_class = 'STANDARD', $valid_days = 30) {
        global $wpdb;
        $invitation_id = 'INV-' . strtoupper(wp_generate_password(12, false, false));
        $raw_token = 'bros-inv-' . bin2hex(random_bytes(16));
        $token_hash = hash('sha256', $raw_token);
        $now = current_time('mysql', 1);
        $expires_at = gmdate('Y-m-d H:i:s', time() + ($valid_days * 86400));
        $table = Config::table('affiliate_invitations');

        $inserted = $wpdb->insert(
            $table,
            array(
                'invitation_id' => $invitation_id,
                'token_hash' => $token_hash,
                'recipient_email' => sanitize_email($email),
                'intended_class' => in_array($intended_class, array('STANDARD', 'STRATEGIC_PARTNER'), true) ? $intended_class : 'STANDARD',
                'status' => 'ACTIVE',
                'expires_at' => $expires_at,
                'created_at' => $now,
            ),
            array('%s', '%s', '%s', '%s', '%s', '%s', '%s')
        );

        if ($inserted === false) {
            return false;
        }

        return array(
            'invitation_id' => $invitation_id,
            'raw_token' => $raw_token,
            'token_hash' => $token_hash,
            'recipient_email' => $email,
            'intended_class' => $intended_class,
            'status' => 'ACTIVE',
            'expires_at' => $expires_at,
        );
    }

    public static function validate_token($raw_token) {
        global $wpdb;
        $raw_token = trim((string) $raw_token);
        if ($raw_token === '') {
            return array('valid' => false, 'reason' => 'EMPTY_TOKEN');
        }

        $token_hash = hash('sha256', $raw_token);
        $table = Config::table('affiliate_invitations');

        $row = $wpdb->get_row(
            $wpdb->prepare("SELECT * FROM {$table} WHERE token_hash = %s LIMIT 1", $token_hash),
            \ARRAY_A
        );

        if (!$row) {
            return array('valid' => false, 'reason' => 'INVALID_TOKEN');
        }

        if ($row['status'] === 'REVOKED') {
            return array('valid' => false, 'reason' => 'REVOKED_TOKEN');
        }

        if ($row['status'] === 'USED') {
            return array('valid' => false, 'reason' => 'ALREADY_USED');
        }

        $now_ts = time();
        $expires_ts = strtotime($row['expires_at'] . ' UTC');
        if ($expires_ts && $now_ts > $expires_ts) {
            return array('valid' => false, 'reason' => 'EXPIRED_TOKEN');
        }

        if ($row['status'] !== 'ACTIVE') {
            return array('valid' => false, 'reason' => 'INACTIVE_TOKEN');
        }

        return array(
            'valid' => true,
            'invitation_id' => $row['invitation_id'],
            'token_hash' => $row['token_hash'],
            'recipient_email' => $row['recipient_email'],
            'intended_class' => $row['intended_class'],
            'expires_at' => $row['expires_at'],
        );
    }

    public static function consume_token($token_hash, $application_key) {
        global $wpdb;
        $table = Config::table('affiliate_invitations');
        $now = current_time('mysql', 1);

        $updated = $wpdb->update(
            $table,
            array(
                'status' => 'USED',
                'used_application_id' => sanitize_text_field($application_key),
                'used_at' => $now,
            ),
            array('token_hash' => $token_hash, 'status' => 'ACTIVE'),
            array('%s', '%s', '%s'),
            array('%s', '%s')
        );

        return $updated !== false && $updated > 0;
    }

    public static function revoke_invitation($invitation_id) {
        global $wpdb;
        $table = Config::table('affiliate_invitations');
        return $wpdb->update(
            $table,
            array('status' => 'REVOKED'),
            array('invitation_id' => $invitation_id),
            array('%s'),
            array('%s')
        );
    }

    public static function ensure_pilot_invitations($count = 5) {
        global $wpdb;
        $table = Config::table('affiliate_invitations');
        $existing = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$table}");
        if ($existing >= $count) {
            return;
        }
        for ($i = $existing; $i < $count; $i++) {
            self::create_invitation('', 'STANDARD', 30);
        }
    }
}
