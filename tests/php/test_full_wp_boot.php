<?php
// Mock complete WordPress runtime to test loading budly-sales-agent.php
define('ABSPATH', __DIR__ . '/');
define('WP_DEBUG', true);

// Global mocks
$options = array();
function get_option($k, $d = false) { global $options; return isset($options[$k]) ? $options[$k] : $d; }
function update_option($k, $v) { global $options; $options[$k] = $v; return true; }
function plugin_dir_path($f) { return dirname($f) . '/'; }
function plugin_dir_url($f) { return 'https://example.com/wp-content/plugins/budly-sales-agent/'; }
function sanitize_title($t) { return strtolower(str_replace(' ', '-', $t)); }
function sanitize_text_field($t) { return trim($t); }
function sanitize_email($e) { return filter_var($e, FILTER_VALIDATE_EMAIL); }
function sanitize_textarea_field($t) { return trim($t); }
function is_email($e) { return filter_var($e, FILTER_VALIDATE_EMAIL) !== false; }
function esc_html($s) { return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); }
function esc_html__($s, $d = '') { return $s; }
function esc_url($u) { return $u; }
function esc_url_raw($u) { return $u; }
function is_admin() { return false; }
function is_page($p) { return false; }
function is_user_logged_in() { return false; }
function current_user_can($cap) { return false; }
function rest_url($r) { return 'https://example.com/wp-json/' . ltrim($r, '/'); }
function home_url($p = '') { return 'https://example.com' . $p; }
function admin_url($p = '') { return 'https://example.com/wp-admin/' . $p; }
function wp_create_nonce($a) { return 'nonce_' . $a; }
function register_activation_hook($f, $cb) {}
function register_deactivation_hook($f, $cb) {}
function add_action($tag, $cb, $p = 10, $a = 1) {
    global $actions;
    $actions[$tag][] = $cb;
}
function add_filter($tag, $cb, $p = 10, $a = 1) {
    global $filters;
    $filters[$tag][] = $cb;
}
function add_shortcode($tag, $cb) {
    global $shortcodes;
    $shortcodes[$tag] = $cb;
}
function add_submenu_page($p, $pt, $mt, $c, $ms, $cb) {}
function wp_schedule_event($t, $r, $h) {}
function wp_next_scheduled($h) { return false; }
function wp_unschedule_event($t, $h) {}
function flush_rewrite_rules() {}
function get_post($id) { return null; }
function get_page_by_path($p) { return null; }
function wp_insert_post($a) { return 1; }
function is_wp_error($e) { return false; }
function update_post_meta($id, $k, $v) {}
function wp_enqueue_style($h, $s, $d, $v) {}
function wp_enqueue_script($h, $s, $d, $v, $f) {}
function wp_localize_script($h, $o, $d) {}
function get_permalink($id) { return 'https://example.com/p/' . $id; }

// Database mock
class WPDB_Mock {
    public $prefix = 'wp_';
    public $last_error = '';
    public function get_var($query = null) { return null; }
    public function get_results($query = null) { return array(); }
    public function get_row($query = null) { return null; }
    public function insert($table, $data, $format = null) { return 1; }
    public function update($table, $data, $where, $format = null, $where_format = null) { return 1; }
    public function query($query) { return 1; }
    public function prepare($query, ...$args) { return $query; }
}
global $wpdb;
$wpdb = new WPDB_Mock();

try {
    echo "Loading budly-sales-agent.php...\n";
    require_once dirname(dirname(__DIR__)) . '/deploy/wordpress/budly-sales-agent/budly-sales-agent.php';
    echo "Plugin loaded successfully without errors!\n";
    
    // Test activation hook
    echo "Testing activation hook...\n";
    budly_sales_activate();
    echo "Activation hook executed successfully!\n";
    
    // Test shortcode render
    echo "Testing budly_sales_shortcode...\n";
    $out = budly_sales_shortcode();
    echo "Shortcode rendered " . strlen($out) . " bytes\n";
    
    echo "ALL TESTS PASSED CLEANLY!\n";
} catch (Throwable $t) {
    echo "FATAL ERROR: " . $t->getMessage() . "\n";
    echo "File: " . $t->getFile() . ":" . $t->getLine() . "\n";
    echo "Trace:\n" . $t->getTraceAsString() . "\n";
}
