<?php
namespace Budly\SecureMemory\Consent;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class ConsentRepository {
    private $wpdb;

    public function __construct($database = null) {
        if ($database !== null) { $this->wpdb = $database; return; }
        global $wpdb;
        $this->wpdb = $wpdb;
    }

    public function all_for_customer($customer_id) {
        $sql = $this->wpdb->prepare(
            'SELECT consent_type,status,consent_version,source,updated_at FROM ' . Config::table('consent') . ' WHERE customer_id = %d',
            $customer_id
        );
        return $this->wpdb->get_results($sql, ARRAY_A);
    }

    public function status($customer_id, $type) {
        $sql = $this->wpdb->prepare(
            'SELECT status FROM ' . Config::table('consent') . ' WHERE customer_id = %d AND consent_type = %s LIMIT 1',
            $customer_id, $type
        );
        return $this->wpdb->get_var($sql);
    }

    public function granted_record($customer_id, $type) {
        $sql = $this->wpdb->prepare(
            'SELECT consent_id,status,consent_version,updated_at FROM ' . Config::table('consent') . ' WHERE customer_id = %d AND consent_type = %s AND status = %s LIMIT 1',
            $customer_id, $type, 'granted'
        );
        return $this->wpdb->get_row($sql, ARRAY_A);
    }

    public function update_many($customer_id, array $changes, $version, $source, $now) {
        $this->wpdb->query('START TRANSACTION');
        try {
            foreach ($changes as $type => $status) {
                $consent_id = 'con_' . bin2hex(random_bytes(12));
                $sql = $this->wpdb->prepare(
                    'INSERT INTO ' . Config::table('consent') . ' (consent_id,customer_id,consent_type,status,consent_version,source,updated_at) VALUES (%s,%d,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE status = VALUES(status), consent_version = VALUES(consent_version), source = VALUES(source), updated_at = VALUES(updated_at)',
                    $consent_id, $customer_id, $type, $status, $version, $source, $now
                );
                if ($this->wpdb->query($sql) === false) { throw new \RuntimeException('Consent update failed.'); }
                $history = array(
                    'history_id'=>'cnh_' . bin2hex(random_bytes(12)), 'customer_id'=>$customer_id,
                    'consent_type'=>$type, 'status'=>$status, 'consent_version'=>$version,
                    'source'=>$source, 'actor_type'=>'customer', 'created_at'=>$now,
                );
                if ($this->wpdb->insert(Config::table('consent_history'), $history) === false) {
                    throw new \RuntimeException('Consent history persistence failed.');
                }
            }
            $this->wpdb->query('COMMIT');
        } catch (\Throwable $error) {
            $this->wpdb->query('ROLLBACK');
            throw $error;
        }
    }
}
