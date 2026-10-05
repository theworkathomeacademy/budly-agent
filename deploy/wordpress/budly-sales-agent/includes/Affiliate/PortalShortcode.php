<?php
namespace Budly\Affiliate;

if (!defined('ABSPATH')) { exit; }

final class PortalShortcode {
    public static function register() {
        add_shortcode('budly_affiliate_portal', array(__CLASS__, 'render'));
    }

    public static function render() {
        require_once __DIR__ . '/SyntheticScope.php';
        $gate_enabled = FeatureFlags::enabled('affiliate_portal_enabled');
        $user_id = is_user_logged_in() ? get_current_user_id() : 0;
        $decision = SyntheticScope::authorize_portal($user_id);

        ob_start();
        ?>
        <div class="budly-affiliate-portal-wrapper" data-portal-gate="<?php echo $gate_enabled ? 'on' : 'off'; ?>">
          <style>
            .budly-portal-card {
              max-width: 960px;
              margin: 24px auto 40px;
              background: #faf7f0;
              border: 1px solid #d9ddcf;
              border-radius: 20px;
              padding: clamp(24px, 5vw, 44px);
              color: #17261d;
              font-family: Georgia, serif;
              box-shadow: 0 15px 45px rgba(23, 54, 36, 0.07);
              box-sizing: border-box;
            }
            .budly-portal-eyebrow {
              text-transform: uppercase;
              letter-spacing: 0.15em;
              color: #2d6a4f;
              font: 700 12px Arial, sans-serif;
              margin-bottom: 8px;
              display: inline-block;
            }
            .budly-portal-title {
              font-size: clamp(26px, 4vw, 36px);
              color: #173624;
              margin: 0 0 12px;
              line-height: 1.15;
            }
            .budly-portal-lead {
              font-size: 16px;
              color: #3f5146;
              max-width: 680px;
              line-height: 1.55;
              font-family: Arial, sans-serif;
              margin-bottom: 24px;
            }
            .budly-portal-notice {
              background: #edf3ee;
              border-left: 4px solid #2d6a4f;
              padding: 16px 20px;
              border-radius: 10px;
              margin: 20px 0;
              font-family: Arial, sans-serif;
              font-size: 14px;
              line-height: 1.5;
              color: #173624;
            }
            .budly-portal-btn {
              display: inline-flex;
              align-items: center;
              justify-content: center;
              min-height: 46px;
              padding: 12px 24px;
              background: #173624;
              color: #fff !important;
              border-radius: 10px;
              text-decoration: none;
              font-family: Arial, sans-serif;
              font-weight: 700;
              font-size: 14px;
              margin-top: 14px;
              transition: background 0.2s ease;
            }
            .budly-portal-btn:hover {
              background: #234b32;
            }
            /* Dashboard layout */
            .budly-dash-header {
              display: flex;
              flex-wrap: wrap;
              justify-content: space-between;
              align-items: center;
              gap: 16px;
              padding-bottom: 24px;
              border-bottom: 1px solid #dcdfd5;
              margin-bottom: 28px;
            }
            .budly-dash-id-badge {
              background: #173624;
              color: #fff;
              padding: 6px 14px;
              border-radius: 8px;
              font-family: Arial, sans-serif;
              font-weight: 700;
              font-size: 14px;
              display: inline-block;
            }
            .budly-dash-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
              gap: 20px;
              margin-bottom: 28px;
            }
            .budly-dash-card {
              background: #ffffff;
              border: 1px solid #e2e6db;
              border-radius: 14px;
              padding: 22px;
              box-sizing: border-box;
            }
            .budly-dash-card h4 {
              margin: 0 0 12px;
              font-size: 18px;
              color: #173624;
              font-family: Georgia, serif;
            }
            .budly-dash-copy-box {
              display: flex;
              align-items: center;
              background: #f4f6f1;
              border: 1px solid #c9cec2;
              border-radius: 8px;
              padding: 8px 12px;
              margin-bottom: 12px;
            }
            .budly-dash-copy-box input {
              flex: 1;
              border: 0;
              background: transparent;
              font-family: monospace;
              font-size: 13px;
              color: #17261d;
              outline: none;
            }
            .budly-dash-copy-btn {
              padding: 6px 12px;
              background: #2d6a4f;
              color: #fff;
              border: 0;
              border-radius: 6px;
              font-size: 12px;
              font-weight: 700;
              cursor: pointer;
            }
            .budly-stat-tiles {
              display: grid;
              grid-template-columns: 1fr 1fr;
              gap: 12px;
              margin: 14px 0;
            }
            .budly-stat-tile {
              background: #f7f9f5;
              border: 1px solid #e0e4da;
              border-radius: 10px;
              padding: 14px;
              text-align: center;
            }
            .budly-stat-num {
              font-size: 24px;
              font-weight: 700;
              color: #173624;
              font-family: Arial, sans-serif;
            }
            .budly-stat-lbl {
              font-size: 11px;
              color: #526357;
              text-transform: uppercase;
              font-weight: 600;
              margin-top: 4px;
              font-family: Arial, sans-serif;
            }
          </style>

          <?php if (!$gate_enabled): ?>
            <!-- CLOSED / PREPARATION STATE -->
            <div class="budly-portal-card" data-state="gate-closed">
              <span class="budly-portal-eyebrow">Wake'n'Bake Lounge™ Affiliate Portal</span>
              <h2 class="budly-portal-title">Affiliate Portal in Private Preparation</h2>
              <p class="budly-portal-lead">
                The creator portal is currently in final verification within our private five-creator pilot. During this preparation phase, public portal access remains closed.
              </p>
              <div class="budly-portal-notice">
                <strong style="display: block; margin-bottom: 4px;">Pilot Partner Status</strong>
                If you are an approved pilot partner, our team will coordinate access directly with you once portal authorization is released. No private creator metrics or customer details are exposed while the portal gate is closed.
              </div>
              <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                <a href="<?php echo esc_url(home_url('/affiliate/')); ?>" class="budly-portal-btn">
                  View Program Overview &amp; Rates
                </a>
                <a href="<?php echo esc_url(home_url('/ask-budly/')); ?>" class="budly-portal-btn" style="background: #ffffff; color: #173624 !important; border: 1px solid #c8cdbf;">
                  Ask Budly a Question
                </a>
              </div>
            </div>

          <?php elseif (!is_user_logged_in()): ?>
            <!-- GATE ON — GUEST MUST SIGN IN -->
            <div class="budly-portal-card" data-state="login-required">
              <span class="budly-portal-eyebrow">Partner Access</span>
              <h2 class="budly-portal-title">Sign in to Access Your Affiliate Portal</h2>
              <p class="budly-portal-lead">
                Please log in to your account to view your affiliate links, performance metrics, and commission reports.
              </p>
              <a href="<?php echo esc_url(wp_login_url(get_permalink())); ?>" class="budly-portal-btn">
                Log In to Your Account
              </a>
            </div>

          <?php elseif (empty($decision['allowed'])): ?>
            <!-- GATE ON — LOGGED IN BUT NOT AUTHORIZED AFFILIATE -->
            <div class="budly-portal-card" data-state="access-denied">
              <span class="budly-portal-eyebrow">Access Verification</span>
              <h2 class="budly-portal-title">Portal Access Not Available</h2>
              <p class="budly-portal-lead">
                The Affiliate portal is not available for this account. If you are an invited pilot partner, please ensure you are signed in with the correct account or contact program support.
              </p>
              <div class="budly-portal-notice">
                Interested in partnering with us? Learn more about the program at our <a href="<?php echo esc_url(home_url('/affiliate/')); ?>" style="color: #173624; font-weight: bold;">Affiliate Program Overview</a>.
              </div>
            </div>

          <?php else: ?>
            <!-- GATE ON + AUTHORIZED AFFILIATE DASHBOARD -->
            <?php
              $scope = $decision['scope'];
              $affiliate_code = esc_html($scope['affiliate_code'] ?? '');
              $aff_slug = strtolower(str_replace('AFF-', 'pilot-', $affiliate_code));
              $ref_canonical = home_url('/?ref=' . $affiliate_code);
              $ref_vanity = home_url('/go/' . $aff_slug);
            ?>
            <div class="budly-portal-card" data-state="dashboard" data-mode="read-only">
              <!-- WELCOME / IDENTITY -->
              <div class="budly-dash-header">
                <div>
                  <span class="budly-portal-eyebrow">Welcome Partner</span>
                  <h2 class="budly-portal-title" style="margin-bottom: 4px;">Affiliate Portal</h2>
                  <p style="margin: 0; font-family: Arial, sans-serif; font-size: 14px; color: #4b5d52;">
                    Status: <strong style="color: #2d6a4f;">Active Pilot Partner</strong> &bull; Classification: <strong>Standard</strong>
                  </p>
                </div>
                <div>
                  <span class="budly-dash-id-badge"><?php echo $affiliate_code; ?></span>
                </div>
              </div>

              <!-- MY REFERRAL ASSETS -->
              <div class="budly-dash-card" style="margin-bottom: 24px;">
                <h4>My Referral Assets</h4>
                <p style="font-family: Arial, sans-serif; font-size: 14px; color: #3e4f44; margin-bottom: 16px;">
                  Use these links in your social bios, newsletters, and educational content. Attributed sales are tracked automatically.
                </p>

                <label style="display: block; font-family: Arial, sans-serif; font-size: 12px; font-weight: 700; color: #2d6a4f; margin-bottom: 4px;">
                  CANONICAL REFERRAL LINK
                </label>
                <div class="budly-dash-copy-box">
                  <input type="text" value="<?php echo esc_attr($ref_canonical); ?>" readonly id="budly-ref-canon">
                  <button type="button" class="budly-dash-copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('budly-ref-canon').value); alert('Copied!');">Copy</button>
                </div>

                <label style="display: block; font-family: Arial, sans-serif; font-size: 12px; font-weight: 700; color: #2d6a4f; margin-bottom: 4px;">
                  VANITY REFERRAL LINK
                </label>
                <div class="budly-dash-copy-box">
                  <input type="text" value="<?php echo esc_attr($ref_vanity); ?>" readonly id="budly-ref-vanity">
                  <button type="button" class="budly-dash-copy-btn" onclick="navigator.clipboard.writeText(document.getElementById('budly-ref-vanity').value); alert('Copied!');">Copy</button>
                </div>

                <div style="margin-top: 14px; padding-top: 14px; border-top: 1px solid #e7ebe0; display: flex; gap: 16px; align-items: center; flex-wrap: wrap;">
                  <span style="font-family: Arial, sans-serif; font-size: 13px; color: #3e4f44;">
                    QR Code Asset: <strong>Generated for <?php echo $affiliate_code; ?></strong>
                  </span>
                  <a href="<?php echo esc_url($ref_canonical); ?>" target="_blank" style="font-family: Arial, sans-serif; font-size: 13px; color: #2d6a4f; font-weight: 700;">
                    Test Referral Link &rarr;
                  </a>
                </div>
              </div>

              <!-- WHAT I CAN PROMOTE & MY PERFORMANCE GRID -->
              <div class="budly-dash-grid">
                <!-- WHAT I CAN PROMOTE -->
                <div class="budly-dash-card">
                  <h4>What I Can Promote</h4>
                  <ul style="font-family: Arial, sans-serif; font-size: 13px; color: #3e4f44; padding-left: 18px; margin: 0 0 14px; line-height: 1.6;">
                    <li><strong>30% Wellness &amp; Cultivator:</strong> Tinctures, body care &amp; teas</li>
                    <li><strong>25% Books &amp; Guides:</strong> Physical &amp; digital literature</li>
                    <li><strong>15% Courses:</strong> Educational video masterclasses</li>
                    <li><strong>30% Consultations:</strong> 1-on-1 holistic coaching</li>
                    <li><strong>10% Legends Collection:</strong> Premium lounge goods</li>
                    <li><strong>Subscriptions:</strong> 30% first order / 5% recurring renewals</li>
                  </ul>
                  <p style="font-family: Arial, sans-serif; font-size: 12px; color: #627468; margin: 0;">
                    *Exclusions apply to shipping fees, sales taxes, and wholesale products.
                  </p>
                </div>

                <!-- MY PERFORMANCE -->
                <div class="budly-dash-card">
                  <h4>My Performance Summary</h4>
                  <div class="budly-stat-tiles">
                    <div class="budly-stat-tile">
                      <div class="budly-stat-num">0</div>
                      <div class="budly-stat-lbl">Referral Clicks</div>
                    </div>
                    <div class="budly-stat-tile">
                      <div class="budly-stat-num">0</div>
                      <div class="budly-stat-lbl">Attributed Orders</div>
                    </div>
                    <div class="budly-stat-tile">
                      <div class="budly-stat-num">$0.00</div>
                      <div class="budly-stat-lbl">Accrued Commissions</div>
                    </div>
                    <div class="budly-stat-tile">
                      <div class="budly-stat-num">$0.00</div>
                      <div class="budly-stat-lbl">Payout Ready</div>
                    </div>
                  </div>
                  <p style="font-family: Arial, sans-serif; font-size: 12px; color: #627468; margin: 6px 0 0; line-height: 1.4;">
                    *Commissions mature after 30-day refund hold. Minimum payout threshold is $50.00.
                  </p>
                </div>
              </div>

              <!-- PRIVACY & BOUNDARIES NOTICE -->
              <div class="budly-portal-notice">
                <strong style="display: block; margin-bottom: 2px;">Privacy Protection Notice</strong>
                Customer identities, shipping addresses, and personal contact details are strictly protected under Phase 3 privacy governance and are never displayed in creator dashboards.
              </div>

              <!-- BUDLY FOR AFFILIATES -->
              <div class="budly-dash-card">
                <h4>Budly for Affiliates</h4>
                <p style="font-family: Arial, sans-serif; font-size: 14px; color: #3e4f44; margin-bottom: 12px;">
                  Need inspiration for your next post or recipe feature? Budly can help you find products, understand active ingredients, and craft compliant disclosures.
                </p>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                  <a href="<?php echo esc_url(home_url('/ask-budly/?q=' . urlencode('What wellness products can I recommend to my audience?'))); ?>" class="budly-portal-btn" style="padding: 8px 16px; font-size: 13px;">
                    Ask Budly: Product Repertoire
                  </a>
                  <a href="<?php echo esc_url(home_url('/ask-budly/?q=' . urlencode('What are the required FTC disclosures for affiliates?'))); ?>" class="budly-portal-btn" style="padding: 8px 16px; font-size: 13px; background: #2d6a4f;">
                    Ask Budly: FTC Disclosure Help
                  </a>
                </div>
              </div>
            </div>
          <?php endif; ?>
        </div>
        <?php
        return ob_get_clean();
    }
}
