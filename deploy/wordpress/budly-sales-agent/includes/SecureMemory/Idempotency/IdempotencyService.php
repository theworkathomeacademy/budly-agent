<?php
namespace Budly\SecureMemory\Idempotency;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class IdempotencyService {
    private $wpdb;
    public function __construct($database = null) {
        if ($database !== null) { $this->wpdb = $database; return; }
        global $wpdb; $this->wpdb = $wpdb;
    }
    public function replay($customer_id, $endpoint, $key, array $payload) {
        if (!is_string($key) || !preg_match('/^[A-Za-z0-9._:-]{16,80}$/', $key)) { return null; }
        $sql = $this->wpdb->prepare('SELECT request_hash,response_json FROM ' . Config::table('idempotency') . ' WHERE customer_id = %d AND endpoint = %s AND idempotency_key = %s AND expires_at > %s LIMIT 1', $customer_id, $endpoint, $key, current_time('mysql', true));
        $row = $this->wpdb->get_row($sql, ARRAY_A);
        if (!$row) { return null; }
        $hash = hash('sha256', wp_json_encode($payload));
        if (!hash_equals($row['request_hash'], $hash)) { return array('__conflict'=>true); }
        $decoded = json_decode($row['response_json'], true);
        return is_array($decoded) ? $decoded : array('__conflict'=>true);
    }
    public function claim($customer_id,$session_id,$endpoint,$key,array $payload){
        if(!is_string($key)||!preg_match('/^[A-Za-z0-9._:-]{16,80}$/',$key))return true;
        $result=$this->wpdb->query($this->wpdb->prepare('INSERT IGNORE INTO '.Config::table('idempotency').' (customer_id,session_id,endpoint,idempotency_key,request_hash,response_json,created_at,expires_at) VALUES (%d,%s,%s,%s,%s,%s,%s,%s)',$customer_id,$session_id,$endpoint,$key,hash('sha256',wp_json_encode($payload)),'',current_time('mysql',true),gmdate('Y-m-d H:i:s',time()+86400)));
        return $result===1;
    }
    public function remember($customer_id, $session_id, $endpoint, $key, array $payload, array $response) {
        if (!is_string($key) || !preg_match('/^[A-Za-z0-9._:-]{16,80}$/', $key)) { return; }
        $this->wpdb->query($this->wpdb->prepare('UPDATE '.Config::table('idempotency').' SET response_json=%s WHERE customer_id=%d AND endpoint=%s AND idempotency_key=%s AND request_hash=%s',wp_json_encode($response),$customer_id,$endpoint,$key,hash('sha256',wp_json_encode($payload))));
    }
    public function release($customer_id,$endpoint,$key,array $payload){if(!is_string($key)||!preg_match('/^[A-Za-z0-9._:-]{16,80}$/',$key))return;$this->wpdb->query($this->wpdb->prepare('DELETE FROM '.Config::table('idempotency').' WHERE customer_id=%d AND endpoint=%s AND idempotency_key=%s AND request_hash=%s AND response_json=%s',$customer_id,$endpoint,$key,hash('sha256',wp_json_encode($payload)),''));}
}
