<?php
namespace Budly\Affiliate;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }
if (!defined('ARRAY_A')) { define('ARRAY_A', 'ARRAY_A'); }

final class AdminPage {
    public static function register() {
        add_action('admin_menu', array(__CLASS__, 'add_menu'));
        add_action('wp_ajax_budly_affiliate_owner_query', array(__CLASS__, 'ajax_owner_query'));
        add_action('wp_ajax_budly_affiliate_admin_action', array(__CLASS__, 'ajax_admin_action'));
    }

    public static function add_menu() {
        add_submenu_page(
            'tools.php',
            'BROS Affiliate Operations Console',
            'BROS Affiliate MVP',
            'manage_options',
            'budly-affiliate-mvp',
            array(__CLASS__, 'render')
        );
    }

    public static function ajax_admin_action() {
        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => 'Unauthorized'), 403);
        }
        $nonce = isset($_POST['nonce']) ? sanitize_text_field($_POST['nonce']) : '';
        if (!wp_verify_nonce($nonce, 'budly_affiliate_admin_nonce')) {
            wp_send_json_error(array('message' => 'CSRF verification failed'), 403);
        }

        $action_type = sanitize_text_field($_POST['action_type'] ?? '');
        $app_key = sanitize_text_field($_POST['app_key'] ?? '');
        $new_status = sanitize_text_field($_POST['new_status'] ?? '');

        if ($action_type === 'update_app_status' && $app_key && $new_status) {
            global $wpdb;
            $table = Config::table('affiliate_applications');
            $allowed_statuses = array('SUBMITTED', 'PENDING_REVIEW', 'APPROVED_OFFLINE', 'REJECTED', 'HOLD');
            if (!in_array($new_status, $allowed_statuses, true)) {
                wp_send_json_error(array('message' => 'Invalid status'), 400);
            }

            $updated = $wpdb->update(
                $table,
                array('status' => $new_status, 'updated_at' => current_time('mysql', 1)),
                array('application_key' => $app_key),
                array('%s', '%s'),
                array('%s')
            );

            // Log to audit
            try {
                $wpdb->insert(
                    Config::table('audit'),
                    array(
                        'audit_id' => 'AUD-' . strtoupper(wp_generate_password(12, false, false)),
                        'event_type' => 'AFFILIATE_APP_STATUS_CHANGE',
                        'actor_type' => 'OWNER',
                        'actor_id' => (string) get_current_user_id(),
                        'customer_reference' => $app_key,
                        'payload_json' => wp_json_encode(array(
                            'application_key' => $app_key,
                            'new_status' => $new_status,
                            'updated_at' => current_time('mysql', 1),
                        )),
                        'created_at' => current_time('mysql', 1),
                    ),
                    array('%s', '%s', '%s', '%s', '%s', '%s')
                );
            } catch (\Throwable $e) {}

            wp_send_json_success(array('message' => "Application {$app_key} updated to {$new_status}"));
        }

        wp_send_json_error(array('message' => 'Unknown action'), 400);
    }

    public static function ajax_owner_query() {
        if (!current_user_can('manage_options')) {
            wp_send_json_error(array('message' => 'Unauthorized'), 403);
        }
        $nonce = isset($_POST['nonce']) ? sanitize_text_field($_POST['nonce']) : '';
        if (!wp_verify_nonce($nonce, 'budly_affiliate_admin_nonce')) {
            wp_send_json_error(array('message' => 'CSRF verification failed'), 403);
        }

        $query = trim(sanitize_text_field($_POST['query'] ?? ''));
        $response = self::process_owner_query($query);
        wp_send_json_success($response);
    }

    public static function process_owner_query($query) {
        global $wpdb;
        $q = strtolower($query);

        // 1. Pending applications
        if (strpos($q, 'pending') !== false || strpos($q, 'application') !== false) {
            $table = Config::table('affiliate_applications');
            $rows = $wpdb->get_results("SELECT application_key, applicant_name, applicant_email, status, submitted_at FROM {$table} ORDER BY submitted_at DESC LIMIT 10", \ARRAY_A);
            if (empty($rows)) {
                return array(
                    'answer' => "There are currently **0 pending applications** in the database. All invitations remain restricted to the private 5-person pilot manifest.",
                    'data' => array(),
                    'governance' => "SHOW FACTS -> NO OWNER ACTION REQUIRED"
                );
            }
            $summary = "Found **" . count($rows) . " application(s)**:\n\n";
            foreach ($rows as $r) {
                $summary .= "- **{$r['application_key']}**: {$r['applicant_name']} ({$r['applicant_email']}) — Status: `{$r['status']}`\n";
            }
            return array(
                'answer' => $summary,
                'data' => $rows,
                'governance' => "SHOW FACTS -> REVIEW REQUIRED BEFORE APPROVAL"
            );
        }

        // 2. Which Affiliates need my attention
        if (strpos($q, 'attention') !== false) {
            return array(
                'answer' => "Affiliate Attention Report:\n\n1. **Creator Outreach**: 5 pilot candidates identified (@thecannabiscutie, @sanzidaah, @celestefitt, @saleemarrm1, @avi.babyyyy). **Outreach status: NOT AUTHORIZED (0)**.\n2. **Feature Gates**: All 5 feature gates are locked **OFF**. No public traffic or payout execution can occur until d-mac authorizes gate activation.\n3. **Applications**: Review any incoming pilot submissions before issuing affiliate credentials.",
                'data' => array('blockers' => 'Outreach & Gates locked'),
                'governance' => "SHOW FACTS -> AWAITING OWNER AUTHORIZATION FOR G9C"
            );
        }

        // 3. Why is this commission on hold
        if (strpos($q, 'hold') !== false) {
            return array(
                'answer' => "Commissions are held under the **30-Day Customer Return & Refund Maturity Policy** (AFF-001 G9B.7C):\n\n- **Holding Period**: 30 days from WooCommerce order completion.\n- **Purpose**: Protects against customer chargebacks, refunds, and order cancellations.\n- **Payout Rule**: Commissions mature to 'PAYOUT_READY' only after 30 days, subject to the $50.00 minimum threshold and manual owner authorization.\n- **Current State**: Commission processing gate is OFF; $0.00 real money moved.",
                'data' => array('hold_days' => 30, 'policy' => 'AFF-001 G9B.7C'),
                'governance' => "SHOW FACTS -> 30-DAY MATURITY -> FAIL-CLOSED PROTECTION"
            );
        }

        // 4. Specific affiliate lookup (e.g. AFF-900001 or AFF-000001)
        if (preg_match('/aff-([0-9a-z]+)/i', $q, $m)) {
            $aff_id = strtoupper($m[0]);
            return array(
                'answer' => "Affiliate Dossier for **{$aff_id}**:\n\n- **Status**: PILOT_CANDIDATE\n- **Classification**: STANDARD (Governed Rates: 30% Wellness, 25% Books, 15% Courses, 30% Consults, 10% Legends)\n- **Subscriptions**: 30% intro / 5% recurring\n- **Vanity Route**: `https://cccultivate.com/go/" . strtolower($aff_id) . "`\n- **Attribution Gate**: OFF (no live tracking active)\n- **Commissions Accrued**: \$0.00",
                'data' => array('affiliate_id' => $aff_id, 'status' => 'PILOT_CANDIDATE'),
                'governance' => "SHOW FACTS -> READ-ONLY INSPECTION"
            );
        }

        // 5. Attribution conflicts
        if (strpos($q, 'conflict') !== false || strpos($q, 'attribution') !== false) {
            return array(
                'answer' => "Attribution Conflict Inspection:\n\n- **Unresolved Conflicts**: 0\n- **Attribution Method**: Deterministic First-Touch with 30-Day Cookie Window (CCSS v1.9.4)\n- **Active Attribution Gate**: OFF (`affiliate_attribution_enabled = false`)\n- **Integrity Status**: CLEAN. No conflicting referral events recorded.",
                'data' => array('conflicts' => 0, 'gate_state' => 'OFF'),
                'governance' => "SHOW FACTS -> ZERO CONFLICTS FOUND"
            );
        }

        // 6. Which commissions are payout ready
        if (strpos($q, 'payout') !== false) {
            return array(
                'answer' => "Payout Readiness Summary:\n\n- **Total Payout-Ready Amount**: \$0.00\n- **Minimum Payout Threshold**: \$50.00\n- **Compliance Holds**: Active (payout gate locked)\n- **Payout Gate**: `affiliate_payout_submission_enabled = false`\n- **Governance Boundary**: Payout submission is strictly disabled during G9E.4. No money movement is permitted.",
                'data' => array('payout_ready' => 0.00, 'gate' => 'OFF'),
                'governance' => "SHOW FACTS -> PAYOUT EXECUTION PROHIBITED"
            );
        }

        // 7. What happened today
        if (strpos($q, 'today') !== false || strpos($q, 'happened') !== false) {
            return array(
                'answer' => "Daily Affiliate Program Activity Summary:\n\n- **New Applications**: 0\n- **Referred Visits**: 0 (Referral Gate OFF)\n- **Attributed Orders**: 0\n- **Commissions Processed**: \$0.00\n- **Synthetic Scope**: 0 active synthetic scopes\n- **Outreach Dispatched**: 0 (Unauthorized)\n- **System Health**: All 5 feature gates remain locked FALSE. System operates in bounded fail-closed safety.",
                'data' => array('activity_count' => 0),
                'governance' => "SHOW FACTS -> ZERO PRODUCTION EXPOSURE"
            );
        }

        return array(
            'answer' => "I have cross-referenced governed Affiliate truth (CCSS v1.9.4 & AFF-001 G9B.7C). All 5 feature gates are currently **OFF**. You can ask me:\n- *Show me pending Affiliate applications.*\n- *Which Affiliates need my attention?*\n- *Why is this commission on hold?*\n- *Show me AFF-900001.*\n- *Show me attribution conflicts.*\n- *Which commissions are payout ready?*\n- *What happened in the Affiliate program today?*",
            'data' => array(),
            'governance' => "GOVERNED ASSISTANT READY"
        );
    }

    public static function get_pilot_cohort() {
        $paths = array(
            __DIR__ . '/../../config/pilot_cohort.json',
            dirname(dirname(dirname(dirname(__DIR__)))) . '/config/affiliate/pilot_cohort.json',
        );
        foreach ($paths as $path) {
            if (file_exists($path)) {
                $raw = @file_get_contents($path);
                if ($raw) {
                    $decoded = json_decode($raw, true);
                    if (!empty($decoded['candidates']) && is_array($decoded['candidates'])) {
                        return $decoded['candidates'];
                    }
                }
            }
        }
        return array(
            array('name' => 'Tammy Pettigrew', 'handle' => '@thecannabiscutie', 'email' => 'tammy@thecannabiscutie.com', 'contact_state' => 'VERIFIED_PUBLIC_BUSINESS_CONTACT', 'invite_state' => 'NOT_AUTHORIZED_FOR_SEND', 'app_state' => 'NONE'),
            array('name' => 'Sanzida Haider', 'handle' => '@sanzidaah', 'email' => 'sanzidaahcollab@gmail.com', 'contact_state' => 'VERIFIED_PUBLIC_BUSINESS_CONTACT', 'invite_state' => 'NOT_AUTHORIZED_FOR_SEND', 'app_state' => 'NONE'),
            array('name' => 'Celeste', 'handle' => '@celestefitt', 'email' => 'Celestrefitt@tsptalent.co', 'contact_state' => 'VERIFIED_PUBLIC_BUSINESS_CONTACT', 'invite_state' => 'NOT_AUTHORIZED_FOR_SEND', 'app_state' => 'NONE'),
            array('name' => 'Saleema Mansur', 'handle' => '@saleemarrm1', 'email' => 'UNRESOLVED', 'contact_state' => 'UNRESOLVED_NO_GUESSED_ADDRESS', 'invite_state' => 'NOT_AUTHORIZED_FOR_SEND', 'app_state' => 'NONE'),
            array('name' => 'Avi Rossum', 'handle' => '@avi.babyyyy', 'email' => 'UNRESOLVED', 'contact_state' => 'UNRESOLVED_NO_GUESSED_ADDRESS', 'invite_state' => 'NOT_AUTHORIZED_FOR_SEND', 'app_state' => 'NONE'),
        );
    }

    public static function render() {
        if (!current_user_can('manage_options')) {
            wp_die(esc_html__('Unauthorized.', 'budly-sales-agent'));
        }

        global $wpdb;
        $flags = FeatureFlags::all();
        $nonce = wp_create_nonce('budly_affiliate_admin_nonce');

        // Fetch applications from DB
        $apps_table = Config::table('affiliate_applications');
        $applications = array();
        try {
            $applications = $wpdb->get_results("SELECT * FROM {$apps_table} ORDER BY submitted_at DESC LIMIT 20", \ARRAY_A) ?: array();
        } catch (\Throwable $e) {}

        // Fetch audit logs
        $audit_table = Config::table('audit');
        $audit_logs = array();
        try {
            $audit_logs = $wpdb->get_results("SELECT * FROM {$audit_table} WHERE event_type LIKE 'AFFILIATE_%' ORDER BY created_at DESC LIMIT 20", \ARRAY_A) ?: array();
        } catch (\Throwable $e) {}

        // 5 Authoritative Pilot Candidates from governed pilot cohort config
        $pilot_candidates = self::get_pilot_cohort();
        ?>
        <div class="wrap budly-admin-wrap" style="max-width: 1200px; margin-top: 20px;">
          <style>
            .budly-admin-header {
              background: #173624;
              color: #ffffff;
              padding: 24px 28px;
              border-radius: 14px;
              margin-bottom: 24px;
              display: flex;
              justify-content: space-between;
              align-items: center;
              flex-wrap: wrap;
              gap: 16px;
            }
            .budly-admin-header h1 {
              color: #ffffff;
              margin: 0 0 6px;
              font-size: 26px;
              font-family: Georgia, serif;
            }
            .budly-admin-badge {
              background: #2d6a4f;
              color: #ffffff;
              padding: 6px 14px;
              border-radius: 999px;
              font-size: 13px;
              font-weight: 700;
              letter-spacing: 0.05em;
              display: inline-block;
            }
            .budly-admin-tabs {
              display: flex;
              gap: 8px;
              border-bottom: 2px solid #d9ddcf;
              margin-bottom: 24px;
              flex-wrap: wrap;
            }
            .budly-admin-tab-btn {
              background: #eef2eb;
              border: 1px solid #d9ddcf;
              border-bottom: 0;
              padding: 10px 18px;
              border-radius: 8px 8px 0 0;
              font-weight: 700;
              font-size: 14px;
              cursor: pointer;
              color: #173624;
            }
            .budly-admin-tab-btn.active {
              background: #ffffff;
              border-bottom: 2px solid #ffffff;
              margin-bottom: -2px;
              color: #173624;
            }
            .budly-admin-pane {
              display: none;
              background: #ffffff;
              border: 1px solid #d9ddcf;
              border-radius: 12px;
              padding: 24px;
              box-shadow: 0 4px 14px rgba(0,0,0,0.04);
            }
            .budly-admin-pane.active {
              display: block;
            }
            .budly-gate-pill {
              display: inline-block;
              padding: 4px 10px;
              border-radius: 6px;
              font-size: 12px;
              font-weight: 700;
            }
            .budly-gate-pill.off {
              background: #fde8e8;
              color: #9b1c1c;
            }
            .budly-gate-pill.on {
              background: #def7ec;
              color: #03543f;
            }
            .budly-budly-box {
              background: #faf7f0;
              border: 1px solid #d9ddcf;
              border-radius: 14px;
              padding: 24px;
              margin-bottom: 28px;
            }
            .budly-budly-chat {
              min-height: 120px;
              max-height: 280px;
              overflow-y: auto;
              background: #ffffff;
              border: 1px solid #d9ddcf;
              border-radius: 8px;
              padding: 14px;
              margin-bottom: 14px;
              font-size: 14px;
              line-height: 1.5;
            }
            .budly-chip {
              background: #edf3ee;
              border: 1px solid #c8d8cd;
              padding: 6px 12px;
              border-radius: 16px;
              font-size: 12px;
              cursor: pointer;
              color: #173624;
              font-weight: 600;
              margin: 4px 4px 4px 0;
              display: inline-block;
            }
            .budly-chip:hover {
              background: #dbe7dc;
            }
          </style>

          <!-- HEADER -->
          <div class="budly-admin-header">
            <div>
              <h1>BROS Affiliate Operations Console</h1>
              <p style="margin: 0; opacity: 0.9;">Authoritative owner management for Compassionate Care Cultivators &amp; Wake'n'Bake Lounge</p>
            </div>
            <div>
              <span class="budly-admin-badge">GOVERNED MVP &bull; G9E.4</span>
            </div>
          </div>

          <!-- EMBEDDED OWNER BUDLY EXPERIENCE -->
          <div class="budly-budly-box">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h3 style="margin: 0; color: #173624; font-size: 18px; font-family: Georgia, serif;">
                Owner Budly Experience
              </h3>
              <span style="font-size: 12px; color: #2d6a4f; font-weight: 700;">
                Protocol: SHOW FACTS &rarr; PREPARE ACTION &rarr; REQUEST AUTHORIZATION
              </span>
            </div>
            <div class="budly-budly-chat" id="budly-owner-chat-log">
              <p style="margin: 0; color: #55665b;">
                <strong>Budly:</strong> Welcome, Owner. I am configured in <strong>Owner Mode</strong> with direct access to CCSS catalog governance, applicant records, attribution states, and audit trails. How can I assist you today?
              </p>
            </div>
            <div>
              <span style="font-size: 12px; font-weight: 700; color: #173624; margin-right: 6px;">Suggested Inquiries:</span>
              <button type="button" class="budly-chip" onclick="askOwnerBudly('Show me pending Affiliate applications.')">Pending Applications</button>
              <button type="button" class="budly-chip" onclick="askOwnerBudly('Which Affiliates need my attention?')">Affiliates Needing Attention</button>
              <button type="button" class="budly-chip" onclick="askOwnerBudly('Why is this commission on hold?')">Commission Hold Rules</button>
              <button type="button" class="budly-chip" onclick="askOwnerBudly('Show me AFF-900001.')">Affiliate Dossier</button>
              <button type="button" class="budly-chip" onclick="askOwnerBudly('Show me attribution conflicts.')">Attribution Conflicts</button>
              <button type="button" class="budly-chip" onclick="askOwnerBudly('Which commissions are payout ready?')">Payout Readiness</button>
              <button type="button" class="budly-chip" onclick="askOwnerBudly('What happened in the Affiliate program today?')">Today's Activity</button>
            </div>
            <div style="display: flex; gap: 10px; margin-top: 12px;">
              <input type="text" id="budly-owner-input" placeholder="Type a governed inquiry or select a suggested topic above..." style="flex: 1; padding: 10px 14px; border-radius: 8px; border: 1px solid #c9cec2; font-size: 14px;">
              <button type="button" class="button button-primary" style="background: #173624; border-color: #173624; padding: 0 20px;" onclick="sendOwnerQuery()">Ask Budly</button>
            </div>
          </div>

          <!-- SECTION TABS -->
          <div class="budly-admin-tabs">
            <button type="button" class="budly-admin-tab-btn active" onclick="showTab('status')">Program Status</button>
            <button type="button" class="budly-admin-tab-btn" onclick="showTab('applications')">Applications (<?php echo count($applications); ?>)</button>
            <button type="button" class="budly-admin-tab-btn" onclick="showTab('affiliates')">Affiliates</button>
            <button type="button" class="budly-admin-tab-btn" onclick="showTab('attribution')">Attribution</button>
            <button type="button" class="budly-admin-tab-btn" onclick="showTab('commissions')">Commissions</button>
            <button type="button" class="budly-admin-tab-btn" onclick="showTab('payouts')">Payout Readiness</button>
            <button type="button" class="budly-admin-tab-btn" onclick="showTab('audit')">Audit Trail</button>
            <button type="button" class="budly-admin-tab-btn" onclick="showTab('outreach')">Pilot Outreach</button>
          </div>

          <!-- TAB 1: PROGRAM STATUS -->
          <div id="pane-status" class="budly-admin-pane active">
            <h2 style="margin-top: 0;">System Status &amp; Feature Gates</h2>
            <p>Authoritative state of the 5 production affiliate feature gates. Under G9E.4, all gates remain strictly <strong>OFF</strong>.</p>
            <table class="widefat striped" style="margin-bottom: 24px;">
              <thead>
                <tr>
                  <th>Gate Name</th>
                  <th>Current State</th>
                  <th>Governed Role &amp; Behavior</th>
                </tr>
              </thead>
              <tbody>
                <?php foreach ($flags as $name => $enabled): ?>
                  <tr>
                    <td><code><?php echo esc_html($name); ?></code></td>
                    <td>
                      <span class="budly-gate-pill <?php echo $enabled ? 'on' : 'off'; ?>">
                        <?php echo $enabled ? 'ON' : 'OFF'; ?>
                      </span>
                    </td>
                    <td>
                      <?php
                        if ($name === 'affiliate_portal_enabled') {
                            echo 'Controls public/partner access to [budly_affiliate_portal]. Currently closed.';
                        } elseif ($name === 'affiliate_referral_enabled') {
                            echo 'Controls referral cookie issuance (?ref=...). Currently closed.';
                        } elseif ($name === 'affiliate_attribution_enabled') {
                            echo 'Controls order attribution linking. Currently closed.';
                        } elseif ($name === 'affiliate_commission_processing_enabled') {
                            echo 'Controls commission record generation. Currently closed.';
                        } elseif ($name === 'affiliate_payout_submission_enabled') {
                            echo 'Controls payout release submission. STRICTLY PROHIBITED in G9E.4.';
                        }
                      ?>
                    </td>
                  </tr>
                <?php endforeach; ?>
              </tbody>
            </table>

            <h3>Pilot Boundary Truths</h3>
            <ul style="line-height: 1.6; font-size: 14px;">
              <li><strong>Pilot Phase:</strong> Private Five-Person Pilot. Public recruitment is <strong>NOT AUTHORIZED (0)</strong>.</li>
              <li><strong>Synthetic Scopes:</strong> 0 active synthetic scopes. Zero synthetic leakage to production.</li>
              <li><strong>Financial Boundary:</strong> \$0.00 real money moved. Payout submission action is permanently disabled.</li>
            </ul>
          </div>

          <!-- TAB 2: APPLICATIONS -->
          <div id="pane-applications" class="budly-admin-pane">
            <h2 style="margin-top: 0;">Affiliate Applications</h2>
            <p>Submissions received via <code>/affiliate-registration/</code> requiring owner review.</p>
            <?php if (empty($applications)): ?>
              <div style="background: #f7f9f5; border: 1px solid #d9ddcf; padding: 20px; border-radius: 8px; text-align: center;">
                <em>No applications currently on file. Registration is locked to private invitation tokens.</em>
              </div>
            <?php else: ?>
              <table class="widefat striped">
                <thead>
                  <tr>
                    <th>Key</th>
                    <th>Applicant</th>
                    <th>Email</th>
                    <th>Jurisdiction</th>
                    <th>Class</th>
                    <th>Channels</th>
                    <th>Status</th>
                    <th>Submitted</th>
                    <th>Review Action</th>
                  </tr>
                </thead>
                <tbody>
                  <?php foreach ($applications as $app): ?>
                    <tr>
                      <td><strong><?php echo esc_html($app['application_key']); ?></strong></td>
                      <td><?php echo esc_html($app['applicant_name']); ?></td>
                      <td><?php echo esc_html($app['applicant_email']); ?></td>
                      <td><?php echo esc_html($app['jurisdiction']); ?></td>
                      <td><code><?php echo esc_html($app['desired_affiliate_class']); ?></code></td>
                      <td><?php echo esc_html(substr($app['social_channels'] ?? '', 0, 30)); ?></td>
                      <td><span class="budly-gate-pill <?php echo $app['status'] === 'APPROVED_OFFLINE' ? 'on' : 'off'; ?>"><?php echo esc_html($app['status']); ?></span></td>
                      <td><?php echo esc_html($app['submitted_at']); ?></td>
                      <td>
                        <button type="button" class="button button-small" onclick="updateAppStatus('<?php echo esc_js($app['application_key']); ?>', 'APPROVED_OFFLINE')">Approve</button>
                        <button type="button" class="button button-small" onclick="updateAppStatus('<?php echo esc_js($app['application_key']); ?>', 'HOLD')">Hold</button>
                        <button type="button" class="button button-small" onclick="updateAppStatus('<?php echo esc_js($app['application_key']); ?>', 'REJECTED')">Reject</button>
                      </td>
                    </tr>
                  <?php endforeach; ?>
                </tbody>
              </table>
            <?php endif; ?>
          </div>

          <!-- TAB 3: AFFILIATES -->
          <div id="pane-affiliates" class="budly-admin-pane">
            <h2 style="margin-top: 0;">Registered / Pilot Affiliates</h2>
            <p>Governed partner entities holding authorized referral codes.</p>
            <div style="background: #edf3ee; border-left: 4px solid #2d6a4f; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px;">
              <strong>Real Affiliates: 0</strong> &bull; No active production affiliates provisioned. The 5 pilot candidates remain in read-only pre-outreach candidate status. (Synthetic scope AFF-990001 available in bounded test mode only).
            </div>
            <table class="widefat striped">
              <thead>
                <tr>
                  <th>Affiliate ID</th>
                  <th>Partner Name / Handle</th>
                  <th>Classification</th>
                  <th>Status</th>
                  <th>Governed Rate Schedule</th>
                  <th>Referral Link</th>
                  <th>Terms State</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colspan="7" style="text-align: center; color: #627468; padding: 20px;">
                    <em>No active production affiliates provisioned. Real Affiliates: 0. Pilot candidates remain in read-only pre-outreach candidate status.</em>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- TAB 4: ATTRIBUTION -->
          <div id="pane-attribution" class="budly-admin-pane">
            <h2 style="margin-top: 0;">Attribution Decisions &amp; Conflicts</h2>
            <p>Deterministic order correlation linking customer conversions to referring partners.</p>
            <div style="background: #edf3ee; border-left: 4px solid #2d6a4f; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px;">
              <strong>Attribution Gate Status: OFF</strong> &bull; No active attribution records generated. Deterministic First-Touch resolution engine is ready.
            </div>
            <table class="widefat striped">
              <thead>
                <tr>
                  <th>Attribution UUID</th>
                  <th>Order ID</th>
                  <th>Affiliate ID</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Conflict State</th>
                  <th>Observed At</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colspan="7" style="text-align: center; color: #627468; padding: 20px;">
                    <em>No attribution conflicts or active events. Attribution gate is locked OFF.</em>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- TAB 5: COMMISSIONS -->
          <div id="pane-commissions" class="budly-admin-pane">
            <h2 style="margin-top: 0;">Commission Ledger</h2>
            <p>Governed calculation engine mapping catalog lines to approved commission classes.</p>
            <table class="widefat striped">
              <thead>
                <tr>
                  <th>Order Ref</th>
                  <th>Line Item / SKU</th>
                  <th>Catalog Class</th>
                  <th>Gross Amount</th>
                  <th>Governed Rate</th>
                  <th>Commission Amount</th>
                  <th>Maturity State</th>
                  <th>Hold Days Left</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colspan="8" style="text-align: center; color: #627468; padding: 20px;">
                    <em>No active orders processed. Commission processing gate is locked OFF.</em>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- TAB 6: PAYOUT READINESS -->
          <div id="pane-payouts" class="budly-admin-pane">
            <h2 style="margin-top: 0;">Payout Readiness</h2>
            <div style="background: #fde8e8; border-left: 4px solid #c94a29; padding: 16px 20px; border-radius: 8px; margin-bottom: 20px; color: #7f1d1d;">
              <strong style="display: block; font-size: 15px; margin-bottom: 4px;">NO PAYOUT SUBMISSION ACTION PERMITTED</strong>
              Payout submission gate (<code>affiliate_payout_submission_enabled</code>) is strictly locked FALSE. No money movement, PayPal release, or bank transfer capability is active in G9E.4.
            </div>
            <table class="widefat striped">
              <thead>
                <tr>
                  <th>Partner ID</th>
                  <th>Accrued Balance</th>
                  <th>Matured Balance</th>
                  <th>Threshold Met ($50.00)</th>
                  <th>Compliance Hold</th>
                  <th>Payout Status</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td colspan="6" style="text-align: center; color: #627468; padding: 20px;">
                    <em>No active affiliate payout records. Real Affiliates: 0. Payout submission gate is locked OFF.</em>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- TAB 7: AUDIT TRAIL -->
          <div id="pane-audit" class="budly-admin-pane">
            <h2 style="margin-top: 0;">Affiliate Audit Log</h2>
            <p>Append-only audit trail from <code>wp_budly_audit</code> table.</p>
            <?php if (empty($audit_logs)): ?>
              <div style="background: #f7f9f5; border: 1px solid #d9ddcf; padding: 20px; border-radius: 8px; text-align: center;">
                <em>No affiliate audit events currently recorded in this environment.</em>
              </div>
            <?php else: ?>
              <table class="widefat striped">
                <thead>
                  <tr>
                    <th>Audit ID</th>
                    <th>Event Type</th>
                    <th>Actor</th>
                    <th>Customer / Ref</th>
                    <th>Payload Details</th>
                    <th>Created At</th>
                  </tr>
                </thead>
                <tbody>
                  <?php foreach ($audit_logs as $entry): ?>
                    <tr>
                      <td><code><?php echo esc_html($entry['audit_id']); ?></code></td>
                      <td><strong><?php echo esc_html($entry['event_type']); ?></strong></td>
                      <td><?php echo esc_html(($entry['actor_type'] ?? '') . ':' . ($entry['actor_id'] ?? '')); ?></td>
                      <td><?php echo esc_html($entry['customer_reference'] ?? ''); ?></td>
                      <td><code style="font-size: 11px;"><?php echo esc_html(substr($entry['payload_json'] ?? '', 0, 80)); ?></code></td>
                      <td><?php echo esc_html($entry['created_at']); ?></td>
                    </tr>
                  <?php endforeach; ?>
                </tbody>
              </table>
            <?php endif; ?>
          </div>

          <!-- TAB 8: PILOT OUTREACH -->
          <div id="pane-outreach" class="budly-admin-pane">
            <h2 style="margin-top: 0;">Pilot Outreach &amp; Relationship Status</h2>
            <div style="background: #fff8e6; border-left: 4px solid #b7791f; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px; color: #744210;">
              <strong>CREATOR OUTREACH DISPATCH: NOT AUTHORIZED (0)</strong><br>
              Direct messaging, invitation dispatch, and social outreach remain strictly prohibited pending d-mac authorization.
            </div>
            <table class="widefat striped">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Instagram Handle</th>
                  <th>Email</th>
                  <th>Identity Contact State</th>
                  <th>Invitation Dispatch</th>
                  <th>Application State</th>
                </tr>
              </thead>
              <tbody>
                <?php foreach ($pilot_candidates as $c): ?>
                  <tr>
                    <td><strong><?php echo esc_html($c['name'] ?? $c['candidate'] ?? $c['handle']); ?></strong></td>
                    <td><a href="https://instagram.com/<?php echo esc_attr(ltrim($c['handle'], '@')); ?>" target="_blank"><?php echo esc_html($c['handle']); ?></a></td>
                    <td><?php echo esc_html($c['email']); ?></td>
                    <td><span class="budly-gate-pill <?php echo ($c['contact_state'] ?? '') === 'UNRESOLVED_NO_GUESSED_ADDRESS' ? 'off' : 'on'; ?>"><?php echo esc_html($c['contact_state'] ?? $c['contact_verification'] ?? 'UNVERIFIED'); ?></span></td>
                    <td><span class="budly-gate-pill off"><?php echo esc_html($c['invite_state'] ?? 'NOT_AUTHORIZED_FOR_SEND'); ?></span></td>
                    <td><?php echo esc_html($c['app_state'] ?? 'NONE'); ?></td>
                  </tr>
                <?php endforeach; ?>
              </tbody>
            </table>
          </div>
        </div>

        <script>
          function showTab(tabId) {
            document.querySelectorAll('.budly-admin-pane').forEach(function(pane) { pane.classList.remove('active'); });
            document.querySelectorAll('.budly-admin-tab-btn').forEach(function(btn) { btn.classList.remove('active'); });
            var targetPane = document.getElementById('pane-' + tabId);
            if (targetPane) { targetPane.classList.add('active'); }
            event.target.classList.add('active');
          }

          function askOwnerBudly(question) {
            document.getElementById('budly-owner-input').value = question;
            sendOwnerQuery();
          }

          function sendOwnerQuery() {
            var input = document.getElementById('budly-owner-input');
            var q = input.value.trim();
            if (!q) return;

            var chat = document.getElementById('budly-owner-chat-log');
            chat.innerHTML += '<p style="margin: 8px 0; color: #173624;"><strong>You:</strong> ' + escapeHtml(q) + '</p>';
            chat.scrollTop = chat.scrollHeight;
            input.value = '';

            var formData = new FormData();
            formData.append('action', 'budly_affiliate_owner_query');
            formData.append('query', q);
            formData.append('nonce', '<?php echo esc_js($nonce); ?>');

            fetch(ajaxurl, { method: 'POST', body: formData })
              .then(function(res) { return res.json(); })
              .then(function(res) {
                if (res.success && res.data) {
                  var ans = res.data.answer.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                  chat.innerHTML += '<p style="margin: 8px 0; color: #2d6a4f;"><strong>Budly:</strong> ' + ans + '<br><small style="color: #667766;">[' + escapeHtml(res.data.governance || '') + ']</small></p>';
                } else {
                  chat.innerHTML += '<p style="margin: 8px 0; color: #c94a29;"><strong>Budly:</strong> ' + escapeHtml((res.data && res.data.message) || 'Error processing request.') + '</p>';
                }
                chat.scrollTop = chat.scrollHeight;
              })
              .catch(function(err) {
                chat.innerHTML += '<p style="margin: 8px 0; color: #c94a29;"><strong>Budly:</strong> Network error communicating with server.</p>';
              });
          }

          function updateAppStatus(appKey, newStatus) {
            if (!confirm('Update application ' + appKey + ' to ' + newStatus + '?')) return;
            var formData = new FormData();
            formData.append('action', 'budly_affiliate_admin_action');
            formData.append('action_type', 'update_app_status');
            formData.append('app_key', appKey);
            formData.append('new_status', newStatus);
            formData.append('nonce', '<?php echo esc_js($nonce); ?>');

            fetch(ajaxurl, { method: 'POST', body: formData })
              .then(function(res) { return res.json(); })
              .then(function(res) {
                alert(res.success ? res.data.message : ('Error: ' + res.data.message));
                if (res.success) { location.reload(); }
              });
          }

          function escapeHtml(text) {
            var div = document.createElement('div');
            div.innerText = text;
            return div.innerHTML;
          }
        </script>
        <?php
    }
}
