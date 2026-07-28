<?php
namespace Budly\SecureMemory\Sessions;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class SessionRepository {
    private $wpdb;

    public function __construct($database = null) {
        if ($database !== null) { $this->wpdb = $database; return; }
        global $wpdb;
        $this->wpdb = $wpdb;
    }

    public function create(array $record) {
        if ($this->wpdb->insert(Config::table('sessions'), $record) === false) {
            throw new \RuntimeException('Session persistence failed.');
        }
    }

    public function find_by_token_hash($token_hash) {
        $sql = $this->wpdb->prepare(
            'SELECT session_id,customer_id,token_hash,agent_id,status,created_at,last_seen_at,idle_expires_at,absolute_expires_at,revoked_at FROM ' . Config::table('sessions') . ' WHERE token_hash = %s LIMIT 1',
            $token_hash
        );
        return $this->wpdb->get_row($sql, ARRAY_A);
    }

    public function touch($session_id, $last_seen_at, $idle_expires_at) {
        $sql = $this->wpdb->prepare(
            'UPDATE ' . Config::table('sessions') . ' SET last_seen_at = %s, idle_expires_at = %s WHERE session_id = %s AND status = %s AND revoked_at IS NULL',
            $last_seen_at,
            $idle_expires_at,
            $session_id,
            'active'
        );
        $result = $this->wpdb->query($sql);
        if ($result === false) { return false; }
        if ($result === 1) { return true; }
        $active = $this->wpdb->prepare(
            'SELECT COUNT(*) FROM ' . Config::table('sessions') . ' WHERE session_id = %s AND status = %s AND revoked_at IS NULL',
            $session_id,
            'active'
        );
        return (int) $this->wpdb->get_var($active) === 1;
    }

    public function revoke($session_id, $reason, $now) {
        $sql = $this->wpdb->prepare(
            'UPDATE ' . Config::table('sessions') . ' SET status = %s, revoked_at = %s, revoke_reason = %s WHERE session_id = %s AND status = %s',
            'revoked', $now, sanitize_key($reason), $session_id, 'active'
        );
        return $this->wpdb->query($sql);
    }

    public function revoke_all_for_customer($customer_id, $reason, $now) {
        $sql = $this->wpdb->prepare(
            'UPDATE ' . Config::table('sessions') . ' SET status = %s, revoked_at = %s, revoke_reason = %s WHERE customer_id = %d AND status = %s',
            'revoked', $now, sanitize_key($reason), $customer_id, 'active'
        );
        return $this->wpdb->query($sql);
    }
}
