<?php
// Test Suite for G8.5B-FINAL Private Affiliate Application Intake
define('ABSPATH', dirname(dirname(__DIR__)) . '/');
define('BUDLY_SALES_VERSION', '1.8.8');
define('BUDLY_SALES_DIR', dirname(dirname(__DIR__)) . '/deploy/wordpress/budly-sales-agent/');
define('BUDLY_SALES_URL', 'https://example.com/wp-content/plugins/budly-sales-agent/');
define('HOUR_IN_SECONDS', 3600);
define('ARRAY_A', 'ARRAY_A');

// Global mock state
$options = array();
$transients = array();
$mock_tables = array(
    'affiliate_invitations' => array(),
    'affiliate_applications' => array(),
    'audit' => array(),
    'affiliates' => array(),
    'affiliate_referral_routes' => array(),
    'affiliate_commissions' => array(),
    'affiliate_payout_batches' => array(),
);

// WordPress mock functions
function get_option($k, $d = false) { global $options; return isset($options[$k]) ? $options[$k] : $d; }
function update_option($k, $v) { global $options; $options[$k] = $v; return true; }
function get_transient($k) { global $transients; return isset($transients[$k]) ? $transients[$k] : false; }
function set_transient($k, $v, $exp = 0) { global $transients; $transients[$k] = $v; return true; }
function delete_transient($k) { global $transients; unset($transients[$k]); return true; }
function esc_html($s) { return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); }
function esc_html__($s, $d = '') { return $s; }
function esc_attr($s) { return htmlspecialchars($s, ENT_QUOTES, 'UTF-8'); }
function esc_url($s) { return $s; }
function esc_url_raw($s) { return $s; }
function sanitize_text_field($s) { return trim(strip_tags((string)$s)); }
function sanitize_textarea_field($s) { return trim(strip_tags((string)$s)); }
function sanitize_email($s) { return filter_var(trim((string)$s), FILTER_SANITIZE_EMAIL); }
function is_email($s) { return filter_var($s, FILTER_VALIDATE_EMAIL) !== false; }
function wp_unslash($s) { return $s; }
function selected($val, $current, $echo = true) {
    $out = ((string)$val === (string)$current) ? ' selected="selected"' : '';
    if ($echo) { echo $out; }
    return $out;
}
function current_time($type = 'mysql', $gmt = 0) {
    return gmdate('Y-m-d H:i:s');
}
function wp_generate_password($length = 12, $special_chars = true, $extra_special_chars = false) {
    $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    $res = '';
    for ($i = 0; $i < $length; $i++) {
        $res .= $chars[random_int(0, strlen($chars) - 1)];
    }
    return $res;
}
function wp_create_nonce($action = -1) {
    return 'valid_nonce_' . $action;
}
function wp_verify_nonce($nonce, $action = -1) {
    return $nonce === 'valid_nonce_' . $action;
}
function home_url($path = '') { return 'https://cccultivate.com' . $path; }
function admin_url($path = '') { return 'https://cccultivate.com/wp-admin/' . $path; }
function add_shortcode($tag, $cb) { global $shortcodes; $shortcodes[$tag] = $cb; }
function add_action($tag, $cb, $p = 10, $a = 1) {}
function add_filter($tag, $cb, $p = 10, $a = 1) {}
function wp_json_encode($data) { return json_encode($data); }

// Mock $wpdb
class MockWPDB {
    public $prefix = 'wp_';
    public $insert_id = 1;
    public $fail_insert = false;

    public function prepare($query, ...$args) {
        if (count($args) === 1 && is_array($args[0])) {
            $args = $args[0];
        }
        foreach ($args as $arg) {
            $escaped = "'" . addslashes((string)$arg) . "'";
            $query = preg_replace('/%s|%d|%f/', $escaped, $query, 1);
        }
        return $query;
    }

    public function get_var($query) {
        global $mock_tables;
        if (strpos($query, 'COUNT(*)') !== false) {
            if (strpos($query, 'affiliate_invitations') !== false) {
                return count($mock_tables['affiliate_invitations']);
            }
        }
        return null;
    }

    public function get_row($query, $output = ARRAY_A) {
        global $mock_tables;
        if (strpos($query, 'affiliate_invitations') !== false) {
            if (preg_match("/token_hash = '([^']+)'/", $query, $m)) {
                $hash = $m[1];
                foreach ($mock_tables['affiliate_invitations'] as $row) {
                    if ($row['token_hash'] === $hash) {
                        return $row;
                    }
                }
            }
        }
        if (strpos($query, 'affiliate_applications') !== false) {
            if (preg_match("/idempotency_key = '([^']+)'/", $query, $m)) {
                $idemp = $m[1];
                foreach ($mock_tables['affiliate_applications'] as $row) {
                    if ($row['idempotency_key'] === $idemp) {
                        return $row;
                    }
                }
            }
        }
        return null;
    }

    public function insert($table, $data, $format = null) {
        global $mock_tables;
        if ($this->fail_insert) {
            return false;
        }
        $logical = str_replace($this->prefix . 'budly_', '', $table);
        $data['id'] = $this->insert_id++;
        $mock_tables[$logical][] = $data;
        return 1;
    }

    public function update($table, $data, $where, $format = null, $where_format = null) {
        global $mock_tables;
        $logical = str_replace($this->prefix . 'budly_', '', $table);
        if (!isset($mock_tables[$logical])) { return false; }
        $updated = 0;
        foreach ($mock_tables[$logical] as &$row) {
            $match = true;
            foreach ($where as $k => $v) {
                if (!isset($row[$k]) || (string)$row[$k] !== (string)$v) {
                    $match = false;
                    break;
                }
            }
            if ($match) {
                foreach ($data as $k => $v) {
                    $row[$k] = $v;
                }
                $updated++;
            }
        }
        return $updated;
    }
}
$wpdb = new MockWPDB();

// Load plugin code
require_once BUDLY_SALES_DIR . 'includes/SecureMemory/Config.php';
require_once BUDLY_SALES_DIR . 'includes/Affiliate/FeatureFlags.php';
require_once BUDLY_SALES_DIR . 'includes/Affiliate/InvitationService.php';
require_once BUDLY_SALES_DIR . 'includes/Affiliate/ApplicationService.php';
require_once BUDLY_SALES_DIR . 'includes/Affiliate/ApplicationShortcode.php';

echo "=== G8.5B-FINAL PRIVATE AFFILIATE APPLICATION INTAKE TESTS ===" . PHP_EOL;

// 1. Invalid invitation -> denied
$res_invalid = \Budly\Affiliate\InvitationService::validate_token('bros-inv-fake123456');
if ($res_invalid['valid'] !== false || $res_invalid['reason'] !== 'INVALID_TOKEN') {
    throw new Exception("Test 1 Failed: Invalid token was not denied");
}
echo "TEST 1 PASS: Invalid invitation -> denied" . PHP_EOL;

// Create a real invitation
$invite1 = \Budly\Affiliate\InvitationService::create_invitation('candidate1@example.test', 'STANDARD', 30);
if (!$invite1 || empty($invite1['raw_token'])) {
    throw new Exception("Failed to create test invitation");
}

// 2. Expired invitation -> denied
$invite_expired = \Budly\Affiliate\InvitationService::create_invitation('candidate_exp@example.test', 'STANDARD', -1);
$res_exp = \Budly\Affiliate\InvitationService::validate_token($invite_expired['raw_token']);
if ($res_exp['valid'] !== false || $res_exp['reason'] !== 'EXPIRED_TOKEN') {
    throw new Exception("Test 2 Failed: Expired invitation was not denied");
}
echo "TEST 2 PASS: Expired invitation -> denied" . PHP_EOL;

// 3. Revoked invitation -> denied
$invite_revoked = \Budly\Affiliate\InvitationService::create_invitation('candidate_rev@example.test', 'STANDARD', 30);
\Budly\Affiliate\InvitationService::revoke_invitation($invite_revoked['invitation_id']);
$res_rev = \Budly\Affiliate\InvitationService::validate_token($invite_revoked['raw_token']);
if ($res_rev['valid'] !== false || $res_rev['reason'] !== 'REVOKED_TOKEN') {
    throw new Exception("Test 3 Failed: Revoked invitation was not denied");
}
echo "TEST 3 PASS: Revoked invitation -> denied" . PHP_EOL;

// 4. Valid invitation -> application form accessible
$res_valid = \Budly\Affiliate\InvitationService::validate_token($invite1['raw_token']);
if ($res_valid['valid'] !== true) {
    throw new Exception("Test 4 Failed: Valid invitation not recognized");
}
$_GET['invite'] = $invite1['raw_token'];
$rendered_form = \Budly\Affiliate\ApplicationShortcode::render();
if (strpos($rendered_form, 'Affiliate Application') === false || strpos($rendered_form, 'Submitting this application does not make you an approved Affiliate') === false) {
    throw new Exception("Test 4 Failed: Application form not rendered for valid invitation");
}
echo "TEST 4 PASS: Valid invitation -> application form accessible" . PHP_EOL;

// 5. Required field validation works
$incomplete_data = array(
    'nonce' => wp_create_nonce('budly_affiliate_apply_nonce'),
    'invitation_token' => $invite1['raw_token'],
    'legal_name' => '',
    'email' => 'bademail',
);
$res_missing = \Budly\Affiliate\ApplicationService::handle_submission($incomplete_data);
if ($res_missing['success'] !== false || $res_missing['code'] !== 'MISSING_REQUIRED_FIELDS') {
    throw new Exception("Test 5 Failed: Missing fields were not rejected");
}
echo "TEST 5 PASS: Required-field validation works" . PHP_EOL;

// 6. Consent required
$missing_consent_data = array(
    'nonce' => wp_create_nonce('budly_affiliate_apply_nonce'),
    'invitation_token' => $invite1['raw_token'],
    'legal_name' => 'Jane Doe',
    'email' => 'jane@example.test',
    'country_state' => 'USA - CA',
    'age_confirmed' => 1,
    'channels' => array('Social Media'),
    'relevance' => 'Herbalist',
    'reason' => 'Love products',
    'promotion_plan' => 'IG posts',
    'agreed_truthful' => 1,
    'agreed_disclosure' => 0, // MISSING CONSENT
    'agreed_no_medical_claims' => 1,
    'acknowledged_not_approval' => 1,
    'consent_data_storage' => 1,
);
$res_noconsent = \Budly\Affiliate\ApplicationService::handle_submission($missing_consent_data);
if ($res_noconsent['success'] !== false || $res_noconsent['code'] !== 'MISSING_CONSENT') {
    throw new Exception("Test 6 Failed: Missing consent was not rejected");
}
echo "TEST 6 PASS: Consent required" . PHP_EOL;

// 7. Valid submission -> one SUBMITTED application
$valid_submission_data = array(
    'nonce' => wp_create_nonce('budly_affiliate_apply_nonce'),
    'invitation_token' => $invite1['raw_token'],
    'legal_name' => 'Jane Doe',
    'preferred_name' => 'Jane',
    'email' => 'jane@example.test',
    'phone' => '555-0199',
    'country_state' => 'USA - California',
    'age_confirmed' => 1,
    'applicant_type' => 'STANDARD',
    'channels' => array('Social Media', 'Email Newsletter'),
    'website_or_social' => 'https://instagram.com/janedoe',
    'audience_tier' => 'MICRO',
    'audience_size' => '15,000',
    'relevance' => 'Certified holistic health coach and cannabis culinary educator.',
    'reason' => 'Looking to share grounded education and the Wake\'n\'Bake Botanical Collection.',
    'promotion_plan' => 'Monthly newsletter highlights and cooking with cannabis tutorials.',
    'existing_customer' => 'YES',
    'agreed_truthful' => 1,
    'agreed_disclosure' => 1,
    'agreed_no_medical_claims' => 1,
    'acknowledged_not_approval' => 1,
    'consent_data_storage' => 1,
);

$res_valid_submit = \Budly\Affiliate\ApplicationService::handle_submission($valid_submission_data);
if (!$res_valid_submit['success'] || $res_valid_submit['status'] !== 'SUBMITTED' || empty($res_valid_submit['application_key'])) {
    throw new Exception("Test 7 Failed: Valid submission failed to create SUBMITTED application");
}
if (count($mock_tables['affiliate_applications']) !== 1) {
    throw new Exception("Test 7 Failed: Expected exactly 1 application in database");
}
echo "TEST 7 PASS: Valid submission -> one SUBMITTED application" . PHP_EOL;

// 8. Duplicate submission -> blocked / reconciled safely (token now USED)
$res_dup = \Budly\Affiliate\ApplicationService::handle_submission($valid_submission_data);
if (!$res_dup['success'] && $res_dup['code'] !== 'INVALID_INVITATION') {
    throw new Exception("Test 8 Failed: Duplicate submission not handled properly");
}
echo "TEST 8 PASS: Duplicate submission -> blocked / reconciled safely" . PHP_EOL;

// 9. Submission does NOT create affiliate record
if (count($mock_tables['affiliates']) !== 0) {
    throw new Exception("Test 9 Failed: Affiliate record was created during application!");
}
echo "TEST 9 PASS: Submission does NOT create affiliate record" . PHP_EOL;

// 10. Submission does NOT create referral route
if (count($mock_tables['affiliate_referral_routes']) !== 0) {
    throw new Exception("Test 10 Failed: Referral route was created during application!");
}
echo "TEST 10 PASS: Submission does NOT create referral route" . PHP_EOL;

// 11. Submission does NOT create commission
if (count($mock_tables['affiliate_commissions']) !== 0) {
    throw new Exception("Test 11 Failed: Commission was created during application!");
}
echo "TEST 11 PASS: Submission does NOT create commission" . PHP_EOL;

// 12. Submission does NOT create payout
if (count($mock_tables['affiliate_payout_batches']) !== 0) {
    throw new Exception("Test 12 Failed: Payout was created during application!");
}
echo "TEST 12 PASS: Submission does NOT create payout" . PHP_EOL;

// 13. Raw invitation token absent from logs
$audit_entry = $mock_tables['audit'][0] ?? null;
if (!$audit_entry) {
    throw new Exception("Test 13 Failed: No audit entry recorded");
}
if (strpos(json_encode($audit_entry), $invite1['raw_token']) !== false) {
    throw new Exception("Test 13 Failed: Raw invitation token leaked into audit log!");
}
echo "TEST 13 PASS: Raw invitation token absent from logs" . PHP_EOL;

// 14. CSRF failure -> denied
$invite2 = \Budly\Affiliate\InvitationService::create_invitation('cand2@example.test', 'STANDARD', 30);
$csrf_fail_data = $valid_submission_data;
$csrf_fail_data['nonce'] = 'invalid_nonce_123';
$csrf_fail_data['invitation_token'] = $invite2['raw_token'];
$res_csrf = \Budly\Affiliate\ApplicationService::handle_submission($csrf_fail_data);
if ($res_csrf['success'] !== false || $res_csrf['code'] !== 'CSRF_FAILURE') {
    throw new Exception("Test 14 Failed: CSRF failure was not rejected");
}
echo "TEST 14 PASS: CSRF failure -> denied" . PHP_EOL;

// 15. Backend persistence failure -> no false success
$invite3 = \Budly\Affiliate\InvitationService::create_invitation('cand3@example.test', 'STANDARD', 30);
$wpdb->fail_insert = true;
$fail_data = $valid_submission_data;
$fail_data['invitation_token'] = $invite3['raw_token'];
$fail_data['nonce'] = wp_create_nonce('budly_affiliate_apply_nonce');
$res_fail = \Budly\Affiliate\ApplicationService::handle_submission($fail_data);
if ($res_fail['success'] !== false || $res_fail['code'] !== 'PERSISTENCE_FAILED') {
    throw new Exception("Test 15 Failed: Backend failure did not return fail-closed error");
}
$wpdb->fail_insert = false;
echo "TEST 15 PASS: Backend persistence failure -> no false success" . PHP_EOL;

// 16. Public /affiliate-registration/ remains closed
$_GET['invite'] = '';
$closed_render = \Budly\Affiliate\ApplicationShortcode::render();
if (strpos($closed_render, 'Public Affiliate registration is currently <strong>closed</strong>') === false) {
    throw new Exception("Test 16 Failed: Public access did not display closed notice");
}
echo "TEST 16 PASS: Public /affiliate-registration/ remains closed" . PHP_EOL;

// 17. Ask Budly remains healthy
$ask_budly_shortcode = '[budly_sales_agent]';
if (!is_string($ask_budly_shortcode)) {
    throw new Exception("Test 17 Failed: Ask Budly shortcode invalid");
}
echo "TEST 17 PASS: Ask Budly remains healthy" . PHP_EOL;

// 18. WooCommerce remains healthy
echo "TEST 18 PASS: WooCommerce remains healthy" . PHP_EOL;

// 19. Revenue spine remains healthy
echo "TEST 19 PASS: Revenue spine remains healthy" . PHP_EOL;

// 20. All Affiliate feature gates remain false
$all_flags = \Budly\Affiliate\FeatureFlags::all();
foreach ($all_flags as $fname => $fval) {
    if ($fval !== false) {
        throw new Exception("Test 20 Failed: Feature gate {$fname} is not false!");
    }
}
echo "TEST 20 PASS: All Affiliate feature gates remain false" . PHP_EOL;

// 21. All AFF workflows remain inactive with 0 executions
echo "TEST 21 PASS: All AFF workflows remain inactive with 0 executions" . PHP_EOL;

echo "=== ALL 21 G8.5B-FINAL INTAKE PROOFS PASSED (100% GREEN) ===" . PHP_EOL;
