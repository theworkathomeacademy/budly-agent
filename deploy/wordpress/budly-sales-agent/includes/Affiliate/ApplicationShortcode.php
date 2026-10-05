<?php
namespace Budly\Affiliate;

if (!defined('ABSPATH')) { exit; }

final class ApplicationShortcode {
    public static function register() {
        add_shortcode('budly_affiliate_application', array(__CLASS__, 'render'));
        add_action('wp_ajax_budly_affiliate_apply', array(__CLASS__, 'ajax_submit'));
        add_action('wp_ajax_nopriv_budly_affiliate_apply', array(__CLASS__, 'ajax_submit'));
    }

    public static function ajax_submit() {
        $result = ApplicationService::handle_submission($_POST);
        if (!$result['success']) {
            $status_code = isset($result['code']) && $result['code'] === 'CSRF_FAILURE' ? 403 : 400;
            if (isset($result['code']) && $result['code'] === 'RATE_LIMIT_EXCEEDED') { $status_code = 429; }
            if (isset($result['code']) && $result['code'] === 'PERSISTENCE_FAILED') { $status_code = 500; }
            wp_send_json_error($result, $status_code);
        }
        wp_send_json_success($result);
    }

    public static function render() {
        $token = isset($_GET['invite']) ? sanitize_text_field(wp_unslash($_GET['invite'])) : '';
        if (!$token && isset($_POST['invitation_code'])) {
            $token = sanitize_text_field(wp_unslash($_POST['invitation_code']));
        }

        $invitation = InvitationService::validate_token($token);
        $nonce = wp_create_nonce('budly_affiliate_apply_nonce');
        $ajax_url = admin_url('admin-ajax.php');

        ob_start();
        ?>
        <div class="budly-affiliate-application-wrapper" data-budly-affiliate-app>
          <style>
            .budly-aff-card {
              max-width: 760px;
              margin: 30px auto;
              background: #faf7f0;
              border: 1px solid #d9ddcf;
              border-radius: 20px;
              padding: clamp(24px, 5vw, 48px);
              color: #17261d;
              font-family: Georgia, serif;
              box-shadow: 0 15px 45px rgba(23, 54, 36, 0.08);
            }
            .budly-aff-header {
              text-align: center;
              margin-bottom: 28px;
            }
            .budly-aff-eyebrow {
              text-transform: uppercase;
              letter-spacing: 0.15em;
              color: #2d6a4f;
              font: 700 12px Arial, sans-serif;
              margin-bottom: 6px;
            }
            .budly-aff-title {
              font-size: clamp(28px, 4vw, 38px);
              color: #173624;
              margin: 0 0 10px;
              line-height: 1.15;
            }
            .budly-aff-lead {
              font-size: 16px;
              color: #4a5d52;
              max-width: 580px;
              margin: 0 auto;
            }
            .budly-aff-notice {
              background: #edf3ee;
              border-left: 4px solid #2d6a4f;
              padding: 14px 18px;
              border-radius: 8px;
              margin: 22px 0;
              font-family: Arial, sans-serif;
              font-size: 14px;
              line-height: 1.45;
              color: #173624;
            }
            .budly-aff-notice strong {
              display: block;
              margin-bottom: 2px;
            }
            .budly-aff-section {
              margin: 28px 0 16px;
              padding-top: 20px;
              border-top: 1px solid #e2e6dc;
            }
            .budly-aff-section h3 {
              font-family: Arial, sans-serif;
              font-size: 18px;
              color: #173624;
              margin: 0 0 14px;
            }
            .budly-aff-field {
              margin-bottom: 16px;
            }
            .budly-aff-field label {
              display: block;
              font-family: Arial, sans-serif;
              font-weight: 700;
              font-size: 13px;
              margin-bottom: 6px;
              color: #1b4332;
            }
            .budly-aff-field input[type="text"],
            .budly-aff-field input[type="email"],
            .budly-aff-field select,
            .budly-aff-field textarea {
              width: 100%;
              padding: 12px 14px;
              border: 1px solid #c8cdbf;
              border-radius: 10px;
              background: #fff;
              font-size: 15px;
              font-family: Arial, sans-serif;
              color: #17261d;
              box-sizing: border-box;
            }
            .budly-aff-field textarea {
              min-height: 90px;
              resize: vertical;
            }
            .budly-aff-grid-2 {
              display: grid;
              grid-template-columns: 1fr 1fr;
              gap: 16px;
            }
            .budly-aff-checkbox-group {
              display: grid;
              grid-template-columns: 1fr 1fr;
              gap: 10px;
              font-family: Arial, sans-serif;
              font-size: 14px;
            }
            .budly-aff-checkbox-label {
              display: flex;
              align-items: flex-start;
              gap: 8px;
              font-family: Arial, sans-serif;
              font-size: 13px;
              line-height: 1.4;
              margin-bottom: 10px;
              cursor: pointer;
            }
            .budly-aff-checkbox-label input[type="checkbox"] {
              margin-top: 3px;
            }
            .budly-aff-btn {
              display: block;
              width: 100%;
              padding: 15px;
              background: #173624;
              color: #fff;
              border: 0;
              border-radius: 12px;
              font-family: Arial, sans-serif;
              font-weight: 700;
              font-size: 16px;
              cursor: pointer;
              transition: background 0.2s ease;
              margin-top: 24px;
            }
            .budly-aff-btn:hover {
              background: #234b32;
            }
            .budly-aff-btn:disabled {
              opacity: 0.6;
              cursor: wait;
            }
            .budly-aff-success-card {
              text-align: center;
              padding: 20px 0;
            }
            .budly-aff-success-icon {
              display: inline-grid;
              place-items: center;
              width: 56px;
              height: 56px;
              border-radius: 50%;
              background: #2d6a4f;
              color: #fff;
              font-size: 26px;
              margin-bottom: 16px;
            }
            .budly-aff-success-card ul {
              text-align: left;
              max-width: 500px;
              margin: 20px auto;
              padding-left: 20px;
              font-family: Arial, sans-serif;
              font-size: 14px;
              color: #33443a;
              line-height: 1.6;
            }
            @media (max-width: 600px) {
              .budly-aff-grid-2,
              .budly-aff-checkbox-group {
                grid-template-columns: 1fr;
              }
            }
          </style>

          <?php if (!$invitation['valid']): ?>
            <!-- CLOSED / INVITATION GATE -->
            <div class="budly-aff-card">
              <div class="budly-aff-header">
                <div class="budly-aff-eyebrow">Wake'n'Bake &amp; CCC Pilot</div>
                <h2 class="budly-aff-title">Private Affiliate Intake</h2>
                <p class="budly-aff-lead">
                  Public Affiliate registration is currently <strong>closed</strong>. Enrollment is limited to invited private pilot candidates.
                </p>
              </div>

              <?php if ($token && !$invitation['valid']): ?>
                <div class="budly-aff-notice" style="border-left-color: #c94a29; background: #faedea;">
                  <strong>Invitation Not Valid</strong>
                  <?php
                    $reason = $invitation['reason'] ?? '';
                    if ($reason === 'EXPIRED_TOKEN') {
                        echo 'This invitation token has expired.';
                    } elseif ($reason === 'ALREADY_USED') {
                        echo 'This invitation token has already been used to submit an application.';
                    } elseif ($reason === 'REVOKED_TOKEN') {
                        echo 'This invitation token has been revoked.';
                    } else {
                        echo 'The invitation code entered was not recognized. Please check your invitation link or code.';
                    }
                  ?>
                </div>
              <?php endif; ?>

              <form method="GET" class="budly-aff-form" style="margin-top: 24px;">
                <div class="budly-aff-field">
                  <label for="invite-input">Have a Private Pilot Invitation Code?</label>
                  <input type="text" id="invite-input" name="invite" placeholder="Enter your invitation token (e.g., bros-inv-...)" required>
                </div>
                <button type="submit" class="budly-aff-btn">Access Private Application</button>
              </form>

              <div class="budly-aff-notice" style="margin-top: 30px;">
                <strong>Looking for general shopping help?</strong>
                Visit <a href="<?php echo esc_url(home_url('/ask-budly/')); ?>" style="color: #173624; font-weight: bold;">Ask Budly</a> or browse our store catalog.
              </div>
            </div>

          <?php else: ?>
            <!-- PRIVATE APPLICATION FORM -->
            <div class="budly-aff-card">
              <div id="budly-aff-form-container">
                <div class="budly-aff-header">
                  <div class="budly-aff-eyebrow">Authorized Private Pilot</div>
                  <h2 class="budly-aff-title">Affiliate Application</h2>
                  <p class="budly-aff-lead">
                    Thank you for joining our private pilot intake. Please complete your application details below for owner review.
                  </p>
                </div>

                <div class="budly-aff-notice">
                  <strong>Important Notice</strong>
                  Submitting this application does not make you an approved Affiliate. All submissions require human review and agreement to formal terms before any referral link or account is activated.
                </div>

                <div id="budly-aff-error" class="budly-aff-notice" style="border-left-color: #c94a29; background: #faedea; display: none;"></div>

                <form id="budly-aff-apply-form">
                  <input type="hidden" name="action" value="budly_affiliate_apply">
                  <input type="hidden" name="nonce" value="<?php echo esc_attr($nonce); ?>">
                  <input type="hidden" name="invitation_token" value="<?php echo esc_attr($token); ?>">

                  <!-- 1. Identity -->
                  <div class="budly-aff-section">
                    <h3>1. Applicant Identity</h3>
                    <div class="budly-aff-grid-2">
                      <div class="budly-aff-field">
                        <label for="legal_name">Legal / Full Name *</label>
                        <input type="text" id="legal_name" name="legal_name" required>
                      </div>
                      <div class="budly-aff-field">
                        <label for="preferred_name">Preferred / Display Name</label>
                        <input type="text" id="preferred_name" name="preferred_name" placeholder="Leave blank if same as legal name">
                      </div>
                    </div>
                    <div class="budly-aff-grid-2">
                      <div class="budly-aff-field">
                        <label for="email">Email Address *</label>
                        <input type="email" id="email" name="email" value="<?php echo esc_attr($invitation['recipient_email'] ?? ''); ?>" required>
                      </div>
                      <div class="budly-aff-field">
                        <label for="phone">Phone Number (Optional)</label>
                        <input type="text" id="phone" name="phone">
                      </div>
                    </div>
                    <div class="budly-aff-grid-2">
                      <div class="budly-aff-field">
                        <label for="country_state">Country &amp; State / Jurisdiction *</label>
                        <input type="text" id="country_state" name="country_state" placeholder="e.g. USA - California" required>
                      </div>
                      <div class="budly-aff-field">
                        <label for="applicant_type">Applicant Type *</label>
                        <select id="applicant_type" name="applicant_type">
                          <option value="STANDARD" <?php selected($invitation['intended_class'], 'STANDARD'); ?>>Standard Affiliate</option>
                          <option value="STRATEGIC_PARTNER" <?php selected($invitation['intended_class'], 'STRATEGIC_PARTNER'); ?>>Strategic Partner</option>
                        </select>
                      </div>
                    </div>
                    <div class="budly-aff-field">
                      <label class="budly-aff-checkbox-label">
                        <input type="checkbox" name="age_confirmed" value="1" required>
                        <span>I confirm that I am at least 18 years of age (or legal age of majority in my jurisdiction). *</span>
                      </label>
                    </div>
                  </div>

                  <!-- 2. Promotional Channels & Audience -->
                  <div class="budly-aff-section">
                    <h3>2. Promotional Channels &amp; Audience</h3>
                    <div class="budly-aff-field">
                      <label>Primary Promotional Channels (Select all that apply) *</label>
                      <div class="budly-aff-checkbox-group">
                        <label class="budly-aff-checkbox-label"><input type="checkbox" name="channels[]" value="Social Media"> Social Media (IG/TikTok/X/YouTube)</label>
                        <label class="budly-aff-checkbox-label"><input type="checkbox" name="channels[]" value="Blog / Website"> Blog / Content Website</label>
                        <label class="budly-aff-checkbox-label"><input type="checkbox" name="channels[]" value="Email Newsletter"> Email Newsletter / Community</label>
                        <label class="budly-aff-checkbox-label"><input type="checkbox" name="channels[]" value="Events / In-Person"> Events / In-Person / Lounge</label>
                        <label class="budly-aff-checkbox-label"><input type="checkbox" name="channels[]" value="Culinary / Education"> Culinary / Educational Workshops</label>
                        <label class="budly-aff-checkbox-label"><input type="checkbox" name="channels[]" value="Other"> Other</label>
                      </div>
                    </div>
                    <div class="budly-aff-field">
                      <label for="website_or_social">Website or Primary Social Profile URL</label>
                      <input type="text" id="website_or_social" name="website_or_social" placeholder="https://instagram.com/... or https://yoursite.com">
                    </div>
                    <div class="budly-aff-grid-2">
                      <div class="budly-aff-field">
                        <label for="audience_tier">Audience Classification *</label>
                        <select id="audience_tier" name="audience_tier">
                          <option value="NANO">Nano (&lt; 5,000)</option>
                          <option value="MICRO">Micro (5,000 – 25,000)</option>
                          <option value="MID_TIER">Mid-Tier (25,000 – 100,000)</option>
                          <option value="MACRO">Macro (100,000 – 500,000)</option>
                          <option value="MEGA">Mega (500,000+)</option>
                        </select>
                      </div>
                      <div class="budly-aff-field">
                        <label for="audience_size">Estimated Audience / Follower Count</label>
                        <input type="text" id="audience_size" name="audience_size" placeholder="e.g. 12,500 newsletter subscribers">
                      </div>
                    </div>
                  </div>

                  <!-- 3. Relevance & Promotion Plan -->
                  <div class="budly-aff-section">
                    <h3>3. Program Relevance &amp; Plans</h3>
                    <div class="budly-aff-field">
                      <label for="relevance">Relevance to Cannabis, Wellness &amp; Culinary Education *</label>
                      <textarea id="relevance" name="relevance" placeholder="Briefly describe your connection or background in cannabis, botanical wellness, culinary arts, or community education..." required></textarea>
                    </div>
                    <div class="budly-aff-field">
                      <label for="reason">Why do you want to join the Wake'n'Bake &amp; CCC Affiliate Program? *</label>
                      <textarea id="reason" name="reason" placeholder="What excites you about sharing our books, memberships, and wellness offerings?" required></textarea>
                    </div>
                    <div class="budly-aff-field">
                      <label for="promotion_plan">How do you plan to promote the pilot products? *</label>
                      <textarea id="promotion_plan" name="promotion_plan" placeholder="Explain your promotional approach (e.g., product reviews, recipe demonstrations, newsletter features, community events)..." required></textarea>
                    </div>
                    <div class="budly-aff-field">
                      <label for="existing_customer">Are you an existing customer or community member? *</label>
                      <select id="existing_customer" name="existing_customer">
                        <option value="NO">No</option>
                        <option value="YES">Yes</option>
                      </select>
                    </div>
                  </div>

                  <!-- 4. Required Commitments & Disclosures -->
                  <div class="budly-aff-section">
                    <h3>4. Commitments, Disclosures &amp; Consent</h3>
                    <div class="budly-aff-field">
                      <label class="budly-aff-checkbox-label">
                        <input type="checkbox" name="agreed_truthful" value="1" required>
                        <span><strong>Truthful Promotion:</strong> I agree to promote products honestly and accurately, reflecting genuine experience and official product descriptions. *</span>
                      </label>
                      <label class="budly-aff-checkbox-label">
                        <input type="checkbox" name="agreed_disclosure" value="1" required>
                        <span><strong>Affiliate Disclosures:</strong> I agree to include clear, prominent affiliate relationship disclosures on all promotional materials in compliance with applicable advertising standards. *</span>
                      </label>
                      <label class="budly-aff-checkbox-label">
                        <input type="checkbox" name="agreed_no_medical_claims" value="1" required>
                        <span><strong>No Medical Claims:</strong> I agree never to make prohibited medical, therapeutic, or health claims regarding cannabis or botanical wellness products. *</span>
                      </label>
                      <label class="budly-aff-checkbox-label">
                        <input type="checkbox" name="acknowledged_not_approval" value="1" required>
                        <span><strong>Application Status:</strong> I acknowledge that submitting this application does not equal approval or create an affiliate entitlement. *</span>
                      </label>
                      <label class="budly-aff-checkbox-label">
                        <input type="checkbox" name="consent_data_storage" value="1" required>
                        <span><strong>Data Consent:</strong> I consent to the secure storage and processing of my application details solely for Affiliate-program review and administration. *</span>
                      </label>
                    </div>
                  </div>

                  <button type="submit" id="budly-aff-submit-btn" class="budly-aff-btn">Submit Pilot Application</button>
                </form>
              </div>

              <!-- SUCCESS CONTAINER -->
              <div id="budly-aff-success-container" style="display: none;">
                <div class="budly-aff-success-card">
                  <div class="budly-aff-success-icon">✓</div>
                  <div class="budly-aff-eyebrow">Status: Pending Review</div>
                  <h2 class="budly-aff-title">APPLICATION RECEIVED</h2>
                  <p class="budly-aff-lead">
                    Thank you for submitting your application to the Wake'n'Bake &amp; CCC Affiliate Pilot.
                  </p>
                  <div class="budly-aff-notice" style="text-align: left; max-width: 540px; margin: 24px auto;">
                    <strong>Application Reference: <span id="budly-aff-app-ref"></span></strong>
                    Please note the following next steps:
                    <ul>
                      <li>Your application has been received into <strong>SUBMITTED</strong> status and is pending human review.</li>
                      <li>No referral link or tracking route exists yet.</li>
                      <li>No Affiliate account or commission rights have been created.</li>
                      <li>Our team will contact you at your provided email with next steps and terms acceptance upon review.</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            <script>
              document.addEventListener('DOMContentLoaded', function() {
                var form = document.getElementById('budly-aff-apply-form');
                if (!form) return;
                var submitBtn = document.getElementById('budly-aff-submit-btn');
                var errBox = document.getElementById('budly-aff-error');
                var formContainer = document.getElementById('budly-aff-form-container');
                var successContainer = document.getElementById('budly-aff-success-container');
                var appRefSpan = document.getElementById('budly-aff-app-ref');

                form.addEventListener('submit', function(e) {
                  e.preventDefault();
                  errBox.style.display = 'none';
                  errBox.textContent = '';
                  submitBtn.disabled = true;
                  submitBtn.textContent = 'Processing Application...';

                  var formData = new FormData(form);

                  fetch('<?php echo esc_url($ajax_url); ?>', {
                    method: 'POST',
                    body: formData
                  })
                  .then(function(res) { return res.json(); })
                  .then(function(data) {
                    if (data && data.success) {
                      formContainer.style.display = 'none';
                      successContainer.style.display = 'block';
                      if (appRefSpan) {
                        appRefSpan.textContent = data.data.application_key || 'CONFIRMED';
                      }
                    } else {
                      errBox.style.display = 'block';
                      errBox.textContent = (data && data.data && data.data.message) ? data.data.message : 'An error occurred. Please verify your inputs and try again.';
                      submitBtn.disabled = false;
                      submitBtn.textContent = 'Submit Pilot Application';
                    }
                  })
                  .catch(function(err) {
                    errBox.style.display = 'block';
                    errBox.textContent = 'Network or submission error. Please try again.';
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Submit Pilot Application';
                  });
                });
              });
            </script>
          <?php endif; ?>
        </div>
        <?php
        return ob_get_clean();
    }
}
