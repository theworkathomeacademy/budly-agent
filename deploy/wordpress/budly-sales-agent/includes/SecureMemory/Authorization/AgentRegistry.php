<?php
namespace Budly\SecureMemory\Authorization;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class AgentRegistry {
    private $wpdb;
    public function __construct($database = null) {
        if ($database !== null) { $this->wpdb = $database; return; }
        global $wpdb; $this->wpdb = $wpdb;
    }
    public function authorize($agent_id, $scope, $namespace = null) {
        $sql = $this->wpdb->prepare('SELECT scopes_json,namespaces_json FROM ' . Config::table('agents') . ' WHERE agent_id = %s AND status = %s LIMIT 1', $agent_id, 'active');
        $row = $this->wpdb->get_row($sql, ARRAY_A);
        if (!$row) { return false; }
        $scopes = json_decode($row['scopes_json'], true);
        $namespaces = json_decode($row['namespaces_json'], true);
        if (!is_array($scopes) || !in_array($scope, $scopes, true)) { return false; }
        return $namespace === null || (is_array($namespaces) && in_array($namespace, $namespaces, true));
    }
}
