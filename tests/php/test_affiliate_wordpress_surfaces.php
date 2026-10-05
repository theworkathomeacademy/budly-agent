<?php
// Define WordPress stubs for isolated testing
define('ABSPATH', dirname(dirname(__DIR__)) . '/');
define('BUDLY_SALES_VERSION', '1.8.10-rc-g9e4');
define('BUDLY_RELEASE_CANDIDATE', 'budly-v1.8.10-rc-g9e4');
define('BUDLY_SALES_DIR', dirname(dirname(__DIR__)) . '/deploy/wordpress/budly-sales-agent/');
define('BUDLY_SALES_URL', 'https://example.com/wp-content/plugins/budly-sales-agent/');
if (!defined('ARRAY_A')) { define('ARRAY_A', 'ARRAY_A'); }

$options = array();
function get_option($k, $d = false) { global $options; return isset($options[$k]) ? $options[$k] : $d; }
function update_option($k, $v) { global $options; $options[$k] = $v; return true; }
function esc_html($s) { return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); }
function esc_html__($s, $d = '') { return $s; }
function esc_attr($s) { return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); }
function esc_js($s) { return addslashes((string)$s); }
function esc_url($s) { return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); }
function esc_url_raw($s) { return $s; }
function is_user_logged_in() { global $logged_in; return !empty($logged_in); }
function get_current_user_id() { global $current_user_id; return (int) $current_user_id; }
function current_user_can($cap) { global $user_caps; return !empty($user_caps[$cap]); }
function current_time($type, $gmt = false) { return '2026-10-04 12:00:00'; }
function sanitize_text_field($s) { return trim((string) $s); }
function sanitize_title($s) { return preg_replace('/[^a-z0-9_-]/', '-', strtolower(trim((string)$s))); }
function wp_generate_password($length, $special = true, $extra = false) { return str_repeat('A', $length); }
function wp_json_encode($value) { return json_encode($value); }
function wp_create_nonce($action = -1) { return 'nonce_' . $action; }
function wp_verify_nonce($nonce, $action = -1) { return $nonce === 'nonce_' . $action; }
function wp_die($msg) { throw new Exception('WP_DIE: ' . $msg); }
function home_url($path = '') { return 'https://cccultivate.com' . $path; }
function admin_url($path = '') { return 'https://cccultivate.com/wp-admin/' . $path; }
function wp_login_url($redirect = '') { return 'https://cccultivate.com/wp-login.php?redirect_to=' . urlencode($redirect); }
function get_permalink($id = 0) { return 'https://cccultivate.com/affiliate-account/'; }
function wp_unslash($v) { return $v; }

global $shortcodes;
$shortcodes = array();
function add_shortcode($tag, $cb) { global $shortcodes; $shortcodes[$tag] = $cb; }
function add_submenu_page($parent, $page_title, $menu_title, $capability, $menu_slug, $callback) {
    global $admin_pages;
    $admin_pages[$menu_slug] = array('parent' => $parent, 'cap' => $capability, 'cb' => $callback);
}
function add_action($tag, $cb, $p = 10, $a = 1) {}
function add_filter($tag, $cb, $p = 10, $a = 1) {}
function wp_schedule_event($time, $recurrence, $hook) {}
function wp_next_scheduled($hook) { return false; }
function wp_unschedule_event($timestamp, $hook) {}

class FakeWpdb {
    public $prefix = 'wp_';
    public $rows = array();
    public function insert($table, $data, $formats = null) { $this->rows[] = array('table' => $table, 'data' => $data); return 1; }
    public function update($table, $data, $where, $formats = null, $where_formats = null) { return 1; }
    public function get_results($query, $output = 'OBJECT') { return array(); }
    public function get_row($query, $output = 'OBJECT') { return null; }
    public function get_var($query) { return 0; }
    public function prepare($query, ...$args) { return $query; }
}
$wpdb = new FakeWpdb();

require_once BUDLY_SALES_DIR . 'includes/SecureMemory/Config.php';
require_once BUDLY_SALES_DIR . 'includes/Affiliate/Bootstrap.php';

// Register all affiliate classes and hooks
\Budly\Affiliate\Bootstrap::register();

echo "=== TEST 1: FeatureFlags default state ===" . PHP_EOL;
$flags = \Budly\Affiliate\FeatureFlags::all();
echo 'FLAGS TEST: ' . json_encode($flags) . PHP_EOL;
foreach ($flags as $name => $val) {
    if ($val !== false) { throw new Exception('Flag not false: ' . $name); }
}
if (\Budly\Affiliate\FeatureFlags::enabled('non_existent') !== false) {
    throw new Exception('Unknown flag should be false');
}
echo "PASS: All 5 feature flags default strictly to FALSE." . PHP_EOL;

echo "=== TEST 2: PublicPage Shortcode [budly_affiliate_public] ===" . PHP_EOL;
$public_html = \Budly\Affiliate\PublicPage::render();
if (strpos($public_html, "Wake'n'Bake") === false) { throw new Exception('Public page missing Wake\'n\'Bake branding'); }
if (strpos($public_html, '30%') === false || strpos($public_html, '25%') === false || strpos($public_html, '15%') === false || strpos($public_html, '10%') === false) {
    throw new Exception('Public page missing governed commission classes');
}
if (strpos($public_html, '5% ongoing') === false) { throw new Exception('Public page missing subscription recurring policy'); }
if (strpos($public_html, '$50.00') === false) { throw new Exception('Public page missing payout threshold'); }
if (strpos($public_html, 'FTC') === false) { throw new Exception('Public page missing FTC compliance note'); }
if (strpos($public_html, 'Private Pilot Phase') === false) { throw new Exception('Public page missing private pilot notice'); }
if (strpos($public_html, 'No Follower Minimum') === false) { throw new Exception('Public page missing no follower minimum notice'); }
echo "PASS: PublicPage renders complete creator-facing layout with governed rates and boundaries." . PHP_EOL;

echo "=== TEST 3: ApplicationShortcode Closed State [budly_affiliate_application] ===" . PHP_EOL;
$app_closed_html = \Budly\Affiliate\ApplicationShortcode::render();
if (strpos($app_closed_html, 'closed') === false && strpos($app_closed_html, 'Closed') === false) {
    throw new Exception('Application page missing closed-state notice without invitation');
}
if (strpos($app_closed_html, 'Private Pilot') === false && strpos($app_closed_html, 'private pilot') === false) {
    throw new Exception('Application page missing private pilot notice');
}
echo "PASS: ApplicationShortcode correctly presents closed-state when no valid invitation is supplied." . PHP_EOL;

echo "=== TEST 4: Portal Shortcode Gate OFF vs Gate ON [budly_affiliate_portal] ===" . PHP_EOL;
// Gate OFF: Must show closed/preparation state, no private data
$logged_in = false;
$portal_off = \Budly\Affiliate\PortalShortcode::render();
echo 'PORTAL SHORTCODE (GATE OFF): ' . substr(strip_tags($portal_off), 0, 100) . '...' . PHP_EOL;
if (strpos($portal_off, 'in Private Preparation') === false) {
    throw new Exception('Portal did not render preparation state when gate is OFF');
}
if (strpos($portal_off, 'AFF-') !== false) {
    throw new Exception('Portal leaked affiliate identity while gate is OFF');
}

// Gate ON: Unauthenticated guest
$options['budly_affiliate_portal_enabled'] = true;
$portal_guest = \Budly\Affiliate\PortalShortcode::render();
if (strpos($portal_guest, 'Sign in') === false) {
    throw new Exception('Guest did not get sign-in message when gate is ON');
}

// Gate ON: Authenticated unmapped user
$logged_in = true;
$current_user_id = 990001;
$portal_denied = \Budly\Affiliate\PortalShortcode::render();
if (strpos($portal_denied, 'not available') === false) {
    throw new Exception('Unmapped user was not denied access');
}

// Gate ON: Authenticated authorized synthetic affiliate
$options['budly_g9e_authoritative_synthetic_scope'] = array(
    'active' => true,
    'classification' => 'TEST_SYNTHETIC_NON_PRODUCTION_PERSON',
    'wordpress_user_id' => 990001,
    'affiliate_id' => 'synthetic-affiliate-a-uuid',
    'affiliate_code' => 'AFF-990001',
    'expires_at' => '2099-10-04 12:30:00 UTC',
);
$portal_auth = \Budly\Affiliate\PortalShortcode::render();
if (strpos($portal_auth, 'AFF-990001') === false) {
    throw new Exception('Authorized user did not get Affiliate Portal with AFF ID');
}
if (strpos($portal_auth, 'My Referral Assets') === false) {
    throw new Exception('Authorized portal missing Referral Assets');
}
if (strpos($portal_auth, 'What I Can Promote') === false) {
    throw new Exception('Authorized portal missing What I Can Promote');
}
if (strpos($portal_auth, 'My Performance') === false) {
    throw new Exception('Authorized portal missing Performance summary');
}
if (strpos($portal_auth, 'Budly for Affiliates') === false) {
    throw new Exception('Authorized portal missing Budly for Affiliates section');
}

// Gate ON: Owner attempt to access affiliate dashboard directly (forbidden impersonation)
$user_caps = array('manage_options' => true);
$portal_owner = \Budly\Affiliate\PortalShortcode::render();
if (strpos($portal_owner, 'not available') === false) {
    throw new Exception('Owner was allowed to impersonate Affiliate portal');
}
$user_caps = array();

// Reset gate back to OFF
$options['budly_affiliate_portal_enabled'] = false;
$portal_reset = \Budly\Affiliate\PortalShortcode::render();
if (strpos($portal_reset, 'in Private Preparation') === false) {
    throw new Exception('Portal must return to preparation state when gate is reset to OFF');
}
echo "PASS: Portal shortcode enforces strict authorization and boundary controls across all states." . PHP_EOL;

echo "=== TEST 5: Owner Console Authorization & Operations UX ===" . PHP_EOL;
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

if (strpos($admin_html, 'BROS Affiliate Operations Console') === false) {
    throw new Exception('Admin page failed to render header');
}
if (strpos($admin_html, 'OFF') === false) {
    throw new Exception('Admin page failed to render gate OFF states');
}
if (strpos($admin_html, 'Owner Budly Experience') === false) {
    throw new Exception('Admin page missing Owner Budly Experience');
}
if (strpos($admin_html, 'Applications') === false || strpos($admin_html, 'Affiliates') === false || strpos($admin_html, 'Payout Readiness') === false) {
    throw new Exception('Admin page missing required operations sections');
}
if (strpos($admin_html, 'NO PAYOUT SUBMISSION ACTION PERMITTED') === false) {
    throw new Exception('Admin page missing explicit payout submission prohibition notice');
}
if (strpos($admin_html, 'CREATOR OUTREACH DISPATCH: NOT AUTHORIZED (0)') === false) {
    throw new Exception('Admin page missing creator outreach prohibition notice');
}

// Deterministic assertion: Authoritative G9 five-person pilot cohort
$authoritative_handles = array('@thecannabiscutie', '@sanzidaah', '@celestefitt', '@saleemarrm1', '@avi.babyyyy');
foreach ($authoritative_handles as $h) {
    if (strpos($admin_html, $h) === false) {
        throw new Exception("Admin page missing authoritative pilot candidate handle: {$h}");
    }
}
$authoritative_emails = array('tammy@thecannabiscutie.com', 'sanzidaahcollab@gmail.com', 'Celestrefitt@tsptalent.co');
foreach ($authoritative_emails as $em) {
    if (strpos($admin_html, $em) === false) {
        throw new Exception("Admin page missing verified candidate email: {$em}");
    }
}
if (strpos($admin_html, 'UNRESOLVED') === false) {
    throw new Exception("Admin page missing UNRESOLVED indicator for candidates without verified emails");
}

// Deterministic assertion: Stale cohort completely excluded
$stale_handles = array('@thestonedhousewife', '@cannabissomatics', '@chefcheri', '@loudgirlgoodies', '@iamcarlag');
foreach ($stale_handles as $sh) {
    if (strpos($admin_html, $sh) !== false) {
        throw new Exception("Admin page contains unauthorized stale candidate handle: {$sh}");
    }
}

// Deterministic assertion: Real Affiliates = 0
if (strpos($admin_html, 'Real Affiliates: 0') === false) {
    throw new Exception("Admin page missing explicit Real Affiliates: 0 notice");
}
echo "PASS: Owner Console renders all operational tabs, verifies authoritative 5 candidates, and excludes stale handles." . PHP_EOL;

echo "=== TEST 6: Owner Budly Experience Governance Queries ===" . PHP_EOL;
$queries = array(
    'Show me pending Affiliate applications.' => array('pending', 'SHOW FACTS'),
    'Which Affiliates need my attention?' => array('Outreach', 'AWAITING OWNER AUTHORIZATION'),
    'Why is this commission on hold?' => array('30-Day', 'FAIL-CLOSED PROTECTION'),
    'Show me AFF-900001.' => array('AFF-900001', 'READ-ONLY INSPECTION'),
    'Show me attribution conflicts.' => array('0', 'ZERO CONFLICTS'),
    'Which commissions are payout ready?' => array('0.00', 'PAYOUT EXECUTION PROHIBITED'),
    'What happened in the Affiliate program today?' => array('ZERO PRODUCTION EXPOSURE', 'Activity'),
);

foreach ($queries as $q => $expectations) {
    $res = \Budly\Affiliate\AdminPage::process_owner_query($q);
    if (empty($res['answer'])) {
        throw new Exception("Owner Budly query '{$q}' returned empty answer");
    }
    foreach ($expectations as $exp) {
        if (stripos($res['answer'], $exp) === false && stripos($res['governance'] ?? '', $exp) === false) {
            throw new Exception("Owner Budly query '{$q}' missing expected token '{$exp}'");
        }
    }
    echo "  [PASS] Owner Budly query: '{$q}' -> answered with governed protocol: {$res['governance']}" . PHP_EOL;
}

echo "=== ALL WORDPRESS AFFILIATE SURFACES AND GOVERNANCE TESTS PASSED! ===" . PHP_EOL;
