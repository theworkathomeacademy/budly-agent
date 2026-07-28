<?php
namespace Budly\SecureMemory\Verification;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class VerificationRepository {
    private $wpdb;

    public function __construct($database = null) {
        if ($database !== null) { $this->wpdb = $database; return; }
        global $wpdb;
        $this->wpdb = $wpdb;
    }

    public function customer_by_email_hash($email_hash) {
        $sql = $this->wpdb->prepare('SELECT id,public_id,status FROM ' . Config::table('customers') . ' WHERE email_hash = %s AND status = %s LIMIT 1', $email_hash, 'active');
        return $this->wpdb->get_row($sql, ARRAY_A);
    }

    public function count_since($column, $value, $since) {
        if (!in_array($column, array('email_hash','ip_hash'), true)) { throw new \InvalidArgumentException('Unsupported rate-limit key.'); }
        $sql = $this->wpdb->prepare('SELECT COUNT(*) FROM ' . Config::table('verification_requests') . " WHERE {$column} = %s AND created_at >= %s", $value, $since);
        return (int) $this->wpdb->get_var($sql);
    }

    public function invalidate_open_for_email($email_hash, $now) {
        $sql = $this->wpdb->prepare(
            'UPDATE ' . Config::table('verification_requests') . ' SET locked_at = %s WHERE email_hash = %s AND consumed_at IS NULL AND locked_at IS NULL',
            $now,
            $email_hash
        );
        return $this->wpdb->query($sql);
    }

    public function create(array $record) {
        $result = $this->wpdb->insert(Config::table('verification_requests'), $record);
        if ($result === false) { throw new \RuntimeException('Verification request persistence failed.'); }
    }

    public function set_delivery_status($request_id, $status) {
        return $this->wpdb->update(Config::table('verification_requests'), array('delivery_status'=>sanitize_key($status)), array('request_id'=>$request_id));
    }

    public function consume($request_id, $code, $now, $maximum_attempts) {
        $this->wpdb->query('START TRANSACTION');
        try {
            $sql = $this->wpdb->prepare('SELECT * FROM ' . Config::table('verification_requests') . ' WHERE request_id = %s FOR UPDATE', $request_id);
            $record = $this->wpdb->get_row($sql, ARRAY_A);
            if (!$record) { $this->wpdb->query('ROLLBACK'); return array('error'=>'INVALID_CODE'); }
            if (!empty($record['consumed_at'])) { $this->wpdb->query('ROLLBACK'); return array('error'=>'CODE_ALREADY_USED'); }
            if (!empty($record['locked_at']) || (int) $record['attempts'] >= $maximum_attempts) { $this->wpdb->query('ROLLBACK'); return array('error'=>'VERIFICATION_LOCKED'); }
            if (strtotime($record['expires_at'] . ' UTC') <= strtotime($now . ' UTC')) { $this->wpdb->query('ROLLBACK'); return array('error'=>'CODE_EXPIRED'); }
            if (!wp_check_password($code, $record['code_hash'])) {
                $attempts = (int) $record['attempts'] + 1;
                $locked_at = $attempts >= $maximum_attempts ? $now : null;
                $this->wpdb->update(Config::table('verification_requests'), array('attempts'=>$attempts,'locked_at'=>$locked_at), array('id'=>(int) $record['id']));
                $this->wpdb->query('COMMIT');
                return array('error'=>$locked_at ? 'VERIFICATION_LOCKED' : 'INVALID_CODE');
            }
            if (empty($record['customer_id'])) { $this->wpdb->query('ROLLBACK'); return array('error'=>'INVALID_CODE'); }
            $updated = $this->wpdb->query($this->wpdb->prepare(
                'UPDATE ' . Config::table('verification_requests') . ' SET consumed_at = %s WHERE id = %d AND consumed_at IS NULL',
                $now,
                (int) $record['id']
            ));
            if ($updated !== 1) { $this->wpdb->query('ROLLBACK'); return array('error'=>'CODE_ALREADY_USED'); }
            $this->wpdb->query('COMMIT');
            return array('customer_id'=>(int) $record['customer_id'],'request_id'=>$record['request_id']);
        } catch (\Throwable $error) {
            $this->wpdb->query('ROLLBACK');
            throw $error;
        }
    }
}
