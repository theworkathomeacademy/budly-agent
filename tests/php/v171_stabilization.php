<?php
declare(strict_types=1);

namespace {
    define('ABSPATH', __DIR__ . '/');
    define('ARRAY_A', 'ARRAY_A');

    final class WP_REST_Response {
        private $data;
        private $status;
        public function __construct($data, $status = 200) { $this->data = $data; $this->status = $status; }
        public function get_data() { return $this->data; }
        public function get_status() { return $this->status; }
    }

    final class WP_REST_Request {
        private $params;
        private $headers;
        public function __construct(array $params = array(), array $headers = array()) { $this->params = $params; $this->headers = $headers; }
        public function get_param($key) { return $this->params[$key] ?? null; }
        public function get_header($key) { return $this->headers[$key] ?? ''; }
        public function get_query_params() { return $this->params; }
    }

    function sanitize_text_field($value) { return trim((string) $value); }
    function sanitize_key($value) { return preg_replace('/[^a-z0-9_-]/', '', strtolower((string) $value)); }
    function wp_json_encode($value) { return json_encode($value); }
    function current_time($type, $gmt = false) { return '2026-08-10 12:00:00'; }
    function wp_generate_uuid4() { static $i = 0; return sprintf('00000000-0000-4000-8000-%012d', ++$i); }
    function wp_salt($scheme = '') { return 'test-salt'; }
    function get_option($key, $default = false) { return $default; }
    function current_user_can($capability) { return $GLOBALS['is_admin'] ?? false; }
    function get_current_user_id() { return ($GLOBALS['is_admin'] ?? false) ? 99 : 0; }
    function wp_verify_nonce($nonce, $action) { return $nonce === 'valid-nonce'; }

    final class FakeWpdb {
        public $prefix = 'wp_';
        public $conversation = array();
        public $relationships = array();
        public $journey = array();

        public function prepare($query, ...$args) {
            foreach ($args as $arg) {
                $replacement = is_numeric($arg) ? (string) $arg : "'" . addslashes((string) $arg) . "'";
                $query = preg_replace('/%[ds]/', $replacement, $query, 1);
            }
            return $query;
        }
        public function get_row($query, $output = null) {
            if (strpos($query, 'budly_conversation_state') !== false && preg_match('/customer_id = (\d+).*conversation_id = \'([^\']+)\'/', $query, $m)) {
                $key = $m[1] . '|' . $m[2];
                return isset($this->conversation[$key]) ? $this->conversation[$key] : null;
            }
            if (strpos($query, 'budly_relationship_health') !== false && preg_match('/customer_id = (\d+)/', $query, $m)) {
                $row = $this->relationships[(int) $m[1]] ?? null;
                if (!$row) { return null; }
                return $output === ARRAY_A ? $row : (object) $row;
            }
            return null;
        }
        public function get_var($query) {
            if (strpos($query, 'SELECT id FROM') !== false && preg_match('/customer_id = (\d+).*conversation_id = \'([^\']+)\'/', $query, $m)) {
                return isset($this->conversation[$m[1] . '|' . $m[2]]) ? 1 : null;
            }
            if (strpos($query, 'COUNT(*)') !== false && strpos($query, 'budly_conversation_state') !== false) {
                return count(array_filter($this->conversation, fn($row) => $row['current_state'] !== 'completed'));
            }
            if (strpos($query, 'AVG(confidence_score)') !== false) {
                $active = array_values(array_filter($this->conversation, fn($row) => $row['current_state'] !== 'completed'));
                return $active ? array_sum(array_column($active, 'confidence_score')) / count($active) : null;
            }
            return null;
        }
        public function get_results($query, $output = null) {
            if (strpos($query, 'GROUP BY lifecycle_stage') !== false) {
                $counts = array();
                foreach ($this->relationships as $row) { $counts[$row['lifecycle_stage']] = ($counts[$row['lifecycle_stage']] ?? 0) + 1; }
                return array_map(fn($stage, $count) => array('lifecycle_stage' => $stage, 'stage_count' => $count), array_keys($counts), array_values($counts));
            }
            return array();
        }
        public function insert($table, $data) {
            if (str_ends_with($table, 'budly_conversation_state')) {
                $data['id'] = 1;
                $this->conversation[$data['customer_id'] . '|' . $data['conversation_id']] = $data;
            } elseif (str_ends_with($table, 'budly_relationship_health')) {
                $data['id'] = count($this->relationships) + 1;
                $this->relationships[(int) $data['customer_id']] = $data;
            } elseif (str_ends_with($table, 'budly_member_journey')) {
                $this->journey[] = $data;
            }
            return 1;
        }
        public function update($table, $data, $where) {
            if (str_ends_with($table, 'budly_conversation_state')) {
                foreach ($this->conversation as $key => $row) { if (($row['id'] ?? 0) === $where['id']) { $this->conversation[$key] = array_merge($row, $data); } }
            } elseif (str_ends_with($table, 'budly_relationship_health')) {
                foreach ($this->relationships as $customer => $row) { if (($row['id'] ?? 0) === $where['id']) { $this->relationships[$customer] = array_merge($row, $data); } }
            }
            return 1;
        }
    }

    $wpdb = new FakeWpdb();
    $root = dirname(__DIR__, 2) . '/deploy/wordpress/budly-sales-agent/';
}

namespace Budly\SecureMemory\Sessions {
    final class SessionService {
        public static $result = array('error' => 'AUTHENTICATION_REQUIRED');
        public static function instance() { return new self(); }
        public function validate($touch = true) { return self::$result; }
        public function csrf_is_valid($session, $header) { return $header === 'valid-csrf'; }
    }
}

namespace {
    require_once $root . 'includes/SecureMemory/Config.php';
    require_once $root . 'includes/SecureMemory/Errors.php';
    require_once $root . 'includes/SecureMemory/Validation.php';
    require_once $root . 'includes/SecureMemory/Response.php';
    require_once $root . 'includes/SecureMemory/Sessions/SessionGuard.php';
    require_once $root . 'includes/Conversation/ConversationManager.php';
    require_once $root . 'includes/Lifecycle/LifecycleEngine.php';
    require_once $root . 'includes/SecureMemory/Api/Routes.php';

    function check($condition, $message) { if (!$condition) { throw new RuntimeException($message); } }

    use Budly\Conversation\ConversationManager;
    use Budly\Lifecycle\LifecycleEngine;
    use Budly\SecureMemory\Api\Routes;
    use Budly\SecureMemory\Sessions\SessionGuard;
    use Budly\SecureMemory\Sessions\SessionService;

    foreach (array('AUTHENTICATION_REQUIRED', 'SESSION_EXPIRED', 'SESSION_INVALID', 'SESSION_REVOKED') as $error) {
        SessionService::$result = array('error' => $error);
        $response = SessionGuard::verified_customer_id(new WP_REST_Request());
        check($response instanceof WP_REST_Response && $response->get_status() === 401, "{$error} did not fail closed");
        $expected = $error === 'AUTHENTICATION_REQUIRED' ? 'AUTHENTICATION_REQUIRED' : $error;
        check($response->get_data()['error']['code'] === $expected, "{$error} semantics were not preserved");
    }
    SessionService::$result = array();
    check(SessionGuard::verified_customer_id(new WP_REST_Request()) instanceof WP_REST_Response, 'Unverified identity did not fail closed');
    SessionService::$result = array('customer_id' => 42, 'session_id' => 'session-42');
    check(SessionGuard::verified_customer_id(new WP_REST_Request()) === 42, 'Verified customer was not resolved from session');
    check(SessionGuard::verified_customer_id(new WP_REST_Request(), true) instanceof WP_REST_Response, 'Mutation without CSRF did not fail closed');

    SessionService::$result = array('error' => 'AUTHENTICATION_REQUIRED');
    $response = Routes::conversation_state(new WP_REST_Request(array('conversation_id' => 'other-customer')));
    check($response->get_status() === 401 && count($wpdb->conversation) === 0, 'Route fell back to customer 1');

    SessionService::$result = array('customer_id' => 42, 'session_id' => 'session-42');
    $response = Routes::update_conversation_state(new WP_REST_Request(array('conversation_id' => 'conv-42', 'state' => 'exploring'), array('X-Budly-CSRF' => 'valid-csrf')));
    check($response->get_status() === 200 && isset($wpdb->conversation['42|conv-42']), 'Verified conversation mutation did not persist');
    check(!isset($wpdb->conversation['1|conv-42']), 'Conversation mutation crossed customer boundary');

    check(ConversationManager::select_next_adaptive_question(array('shopping_goal' => 'education'))['attribute'] === 'experience_level', 'Known answer was repeated');
    check(ConversationManager::select_next_adaptive_question(array(), 'budget')['attribute'] === 'budget_range', 'Journey did not affect information value');
    check(ConversationManager::select_next_adaptive_question(array(), 'general', 0.95) === null, 'High confidence did not stop questioning');
    check(ConversationManager::select_next_adaptive_question(array('shopping_goal'=>1,'experience_level'=>1,'preferred_format'=>1,'budget_range'=>1,'purchase_timeline'=>1)) === null, 'Exhausted questions did not stop');
    check(count(ConversationManager::canonical_patterns()) === 10, 'Canonical patterns are incomplete');

    $metrics = ConversationManager::health_metrics();
    check($metrics['active_conversations'] === 1 && $metrics['avg_confidence'] === 1.0, 'Conversation metrics are not data-derived');
    $wpdb->conversation = array();
    check(ConversationManager::health_metrics()['avg_confidence'] === 0.0, 'Empty conversation metrics are not truthful');

    $stages = LifecycleEngine::canonical_stages();
    for ($i = 1; $i < count($stages); $i++) {
        $result = LifecycleEngine::transition_stage(42, $stages[$i], array('test' => true), 'audit-test');
        check($result['lifecycle_stage'] === $stages[$i], 'Valid lifecycle transition failed');
    }
    $thrown = false;
    try { LifecycleEngine::transition_stage(77, LifecycleEngine::STAGE_LEADER); } catch (DomainException $e) { $thrown = true; }
    check($thrown, 'Invalid lifecycle jump was accepted');
    $distribution = LifecycleEngine::stage_distribution();
    check($distribution['Leader'] === 1 && $distribution['Visitor'] === 0, 'Lifecycle distribution is not data-derived');

    $GLOBALS['is_admin'] = false;
    check(Routes::admin_conversation_health(new WP_REST_Request())->get_status() === 403, 'Admin metrics allowed unauthorized access');
    $GLOBALS['is_admin'] = true;
    check(Routes::admin_lifecycle(new WP_REST_Request())->get_status() === 200, 'Authorized lifecycle aggregate failed');

    require_once $root . 'includes/SecureMemory/Bootstrap.php';
    $bootstrap = file_get_contents($root . 'includes/SecureMemory/Bootstrap.php');
    check(strpos($bootstrap, "../Conversation/ConversationManager.php") !== false, 'Conversation loader missing');
    check(strpos($bootstrap, "../Lifecycle/LifecycleEngine.php") !== false, 'Lifecycle loader missing');

    echo "v1.7.1 PHP stabilization behavior: PASS\n";
}
