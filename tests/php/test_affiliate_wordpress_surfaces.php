<?php
// Define WordPress stubs for isolated testing
define('ABSPATH', dirname(dirname(__DIR__)) . '/');
define('BUDLY_SALES_VERSION', '1.8.8');
define('BUDLY_SALES_DIR', dirname(dirname(__DIR__)) . '/deploy/wordpress/budly-sales-agent/');
define('BUDLY_SALES_URL', 'https://example.com/wp-content/plugins/budly-sales-agent/');

$options = array();
function get_option($k, $d = false) { global $options; return isset($options[$k]) ? $options[$k] : $d; }
function update_option($k, $v) { global $options; $options[$k] = $v; return true; }
function esc_html($s) { return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); }
function esc_html__($s, $d = '') { return $s; }
function is_user_logged_in() { global $logged_in; return !empty($logged_in); }
function get_current_user_id() { global $current_user_id; return (int) $current_user_id; }
function current_user_can($cap) { global $user_caps; return !empty($user_caps[$cap]); }
function current_time($type, $gmt = false) { return '2026-10-04 12:00:00'; }
function sanitize_text_field($s) { return trim((string) $s); }
function wp_generate_password($length, $special = true, $extra = false) { return str_repeat('A', $length); }
function wp_json_encode($value) { return json_encode($value); }
function wp_die($msg) { throw new Exception('WP_DIE: ' . $msg); }
function add_submenu_page($parent, $page_title, $menu_title, $capability, $menu_slug, $callback) {
    global $admin_pages;
    $admin_pages[$menu_slug] = array('parent' => $parent, 'cap' => $capability, 'cb' => $callback);
}
function add_shortcode($tag, $cb) { global $shortcodes; $shortcodes[$tag] = $cb; }
function add_action($tag, $cb, $p = 10, $a = 1) {}
function add_filter($tag, $cb, $p = 10, $a = 1) {}
function wp_schedule_event($time, $recurrence, $hook) {}
function wp_next_scheduled($hook) { return false; }
function wp_unschedule_event($timestamp, $hook) {}

class FakeWpdb {
    public $prefix = 'wp_';
    public $rows = array();
    public function insert($table, $data, $formats = null) { $this->rows[] = array('table' => $table, 'data' => $data); return 1; }
}
$wpdb = new FakeWpdb();

require_once BUDLY_SALES_DIR . 'includes/SecureMemory/Config.php';
require_once BUDLY_SALES_DIR . 'includes/Affiliate/FeatureFlags.php';
require_once BUDLY_SALES_DIR . 'includes/Affiliate/AdminPage.php';
require_once BUDLY_SALES_DIR . 'includes/Affiliate/PortalShortcode.php';

// TEST 1: FeatureFlags default state
$flags = \Budly\Affiliate\FeatureFlags::all();
echo 'FLAGS TEST: ' . json_encode($flags) . PHP_EOL;
foreach ($flags as $name => $val) {
    if ($val !== false) { throw new Exception('Flag not false: ' . $name); }
}
if (\Budly\Affiliate\FeatureFlags::enabled('non_existent') !== false) {
    throw new Exception('Unknown flag should be false');
}

// TEST 2: Portal shortcode when flag is OFF
\Budly\Affiliate\PortalShortcode::register();
$logged_in = false;
$portal_out = \Budly\Affiliate\PortalShortcode::render();
echo 'PORTAL SHORTCODE (GATE OFF): "' . $portal_out . '"' . PHP_EOL;
if ($portal_out !== '') { throw new Exception('Portal rendered while flag is OFF'); }

// TEST 3: Portal shortcode when flag is ON (unauthenticated vs authenticated)
$options['budly_affiliate_portal_enabled'] = true;
$portal_guest = \Budly\Affiliate\PortalShortcode::render();
echo 'PORTAL GUEST (GATE ON): ' . $portal_guest . PHP_EOL;
if (strpos($portal_guest, 'Sign in') === false) { throw new Exception('Guest did not get sign-in message'); }

$logged_in = true;
$current_user_id = 990001;
$portal_denied = \Budly\Affiliate\PortalShortcode::render();
if (strpos($portal_denied, 'not available') === false) { throw new Exception('Unmapped auth user was not denied'); }
$options['budly_g9e_authoritative_synthetic_scope'] = array(
    'active' => true,
    'classification' => 'TEST_SYNTHETIC_NON_PRODUCTION_PERSON',
    'wordpress_user_id' => 990001,
    'affiliate_id' => 'synthetic-affiliate-a-uuid',
    'affiliate_code' => 'AFF-990001',
    'expires_at' => '2099-10-04 12:30:00 UTC',
);
$portal_user = \Budly\Affiliate\PortalShortcode::render();
echo 'PORTAL AUTH (GATE ON): ' . $portal_user . PHP_EOL;
if (strpos($portal_user, 'Affiliate Portal') === false) { throw new Exception('Auth user did not get portal'); }

$current_user_id = 990002;
$portal_wrong_user = \Budly\Affiliate\PortalShortcode::render();
if (strpos($portal_wrong_user, 'not available') === false) { throw new Exception('Synthetic Affiliate B was not denied'); }

$current_user_id = 990001;
$user_caps = array('manage_options' => true);
$portal_owner = \Budly\Affiliate\PortalShortcode::render();
if (strpos($portal_owner, 'not available') === false) { throw new Exception('Owner was allowed to impersonate Affiliate portal'); }
$user_caps = array();

// Reset option back to false
$options['budly_affiliate_portal_enabled'] = false;
if (\Budly\Affiliate\PortalShortcode::render() !== '') { throw new Exception('Portal must be empty when gate reset'); }

// TEST 4: Admin Page authorization boundary
\Budly\Affiliate\AdminPage::register();
$user_caps = array();
try {
    \Budly\Affiliate\AdminPage::render();
    throw new Exception('Unauthorized user should have been blocked');
} catch (Exception $e) {
    if (strpos($e->getMessage(), 'WP_DIE: Unauthorized.') === false) { throw $e; }
    echo 'ADMIN UNAUTHORIZED CHECK: BLOCKED AS EXPECTED' . PHP_EOL;
}

$user_caps['manage_options'] = true;
ob_start();
\Budly\Affiliate\AdminPage::render();
$admin_html = ob_get_clean();
echo 'ADMIN AUTHORIZED RENDER: SUCCESS' . PHP_EOL;
if (strpos($admin_html, 'BROS Affiliate MVP') === false || strpos($admin_html, 'OFF') === false) {
    throw new Exception('Admin page failed to render gate states');
}

echo 'ALL WORDPRESS SURFACES VERIFIED PASS!' . PHP_EOL;
