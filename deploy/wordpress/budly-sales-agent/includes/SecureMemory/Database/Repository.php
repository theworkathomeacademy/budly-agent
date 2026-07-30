<?php
namespace Budly\SecureMemory\Database;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class Repository {
    private $wpdb;

    public function __construct($database = null) {
        if ($database !== null) {
            $this->wpdb = $database;
            return;
        }
        global $wpdb;
        $this->wpdb = $wpdb;
    }

    public function insert($table, array $values, array $formats = array()) {
        $result = $this->wpdb->insert(Config::table($table), $values, $formats ?: null);
        if ($result === false) { throw new \RuntimeException('Database insert failed.'); }
        return (int) $this->wpdb->insert_id;
    }

    public function update($table, array $values, array $where, array $formats = array(), array $where_formats = array()) {
        $result = $this->wpdb->update(Config::table($table), $values, $where, $formats ?: null, $where_formats ?: null);
        if ($result === false) { throw new \RuntimeException('Database update failed.'); }
        return (int) $result;
    }

    public function one_by($table, $column, $value) {
        $allowed_columns = array('id','public_id','request_id','session_id','token_hash','email_hash','agent_id','version');
        if (!in_array($column, $allowed_columns, true)) {
            throw new \InvalidArgumentException('Unsupported lookup column.');
        }
        $sql = $this->wpdb->prepare('SELECT * FROM ' . Config::table($table) . " WHERE {$column} = %s LIMIT 1", $value);
        return $this->wpdb->get_row($sql, ARRAY_A);
    }

    public function query($sql, array $args = array(), $output = ARRAY_A) {
        if (!$args) { throw new \InvalidArgumentException('Prepared query arguments are required.'); }
        return $this->wpdb->get_results($this->wpdb->prepare($sql, $args), $output);
    }
}
