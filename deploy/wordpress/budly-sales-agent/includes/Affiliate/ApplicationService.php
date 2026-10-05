<?php
namespace Budly\Affiliate;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class ApplicationService {
    public static function handle_submission($data) {
        // 1. Nonce check
        $nonce = isset($data['nonce']) ? sanitize_text_field($data['nonce']) : '';
        if (!wp_verify_nonce($nonce, 'budly_affiliate_apply_nonce')) {
            return array('success' => false, 'code' => 'CSRF_FAILURE', 'message' => 'Security token invalid or expired. Please refresh the page.');
        }

        // 2. Rate limiting check (max 5 submissions per hour per IP)
        $ip = isset($_SERVER['REMOTE_ADDR']) ? sanitize_text_field(wp_unslash($_SERVER['REMOTE_ADDR'])) : '127.0.0.1';
        $ip_hash = hash('sha256', $ip);
        $rate_key = 'budly_aff_rate_' . substr($ip_hash, 0, 16);
        $attempts = (int) get_transient($rate_key);
        if ($attempts >= 5) {
            return array('success' => false, 'code' => 'RATE_LIMIT_EXCEEDED', 'message' => 'Too many application attempts. Please try again later.');
        }
        set_transient($rate_key, $attempts + 1, HOUR_IN_SECONDS);

        // 3. Invitation validation
        $raw_token = isset($data['invitation_token']) ? sanitize_text_field($data['invitation_token']) : '';
        $invitation = InvitationService::validate_token($raw_token);
        if (!$invitation['valid']) {
            return array('success' => false, 'code' => 'INVALID_INVITATION', 'message' => 'Invitation token is invalid, expired, or already used.');
        }

        // 4. Required Field Validation
        $legal_name = sanitize_text_field(isset($data['legal_name']) ? wp_unslash($data['legal_name']) : '');
        $preferred_name = sanitize_text_field(isset($data['preferred_name']) ? wp_unslash($data['preferred_name']) : '');
        $email = sanitize_email(isset($data['email']) ? wp_unslash($data['email']) : '');
        $phone = sanitize_text_field(isset($data['phone']) ? wp_unslash($data['phone']) : '');
        $country_state = sanitize_text_field(isset($data['country_state']) ? wp_unslash($data['country_state']) : '');
        $age_confirmed = !empty($data['age_confirmed']);
        $applicant_type = isset($data['applicant_type']) && $data['applicant_type'] === 'STRATEGIC_PARTNER' ? 'STRATEGIC_PARTNER' : 'STANDARD';
        
        $channels = isset($data['channels']) && is_array($data['channels']) ? array_map('sanitize_text_field', $data['channels']) : array();
        $website_or_social = esc_url_raw(isset($data['website_or_social']) ? wp_unslash($data['website_or_social']) : '');
        $audience_size = sanitize_text_field(isset($data['audience_size']) ? wp_unslash($data['audience_size']) : '');
        $audience_tier = sanitize_text_field(isset($data['audience_tier']) ? wp_unslash($data['audience_tier']) : 'NANO');
        $relevance = sanitize_textarea_field(isset($data['relevance']) ? wp_unslash($data['relevance']) : '');
        $reason = sanitize_textarea_field(isset($data['reason']) ? wp_unslash($data['reason']) : '');
        $promotion_plan = sanitize_textarea_field(isset($data['promotion_plan']) ? wp_unslash($data['promotion_plan']) : '');
        $existing_customer = isset($data['existing_customer']) && strtoupper((string)$data['existing_customer']) === 'YES' ? 'YES' : 'NO';

        // 5. Consent & Disclosure Validation
        $agreed_truthful = !empty($data['agreed_truthful']);
        $agreed_disclosure = !empty($data['agreed_disclosure']);
        $agreed_no_medical_claims = !empty($data['agreed_no_medical_claims']);
        $acknowledged_not_approval = !empty($data['acknowledged_not_approval']);
        $consent_data_storage = !empty($data['consent_data_storage']);

        if (!$legal_name || !$email || !is_email($email) || !$country_state || !$age_confirmed) {
            return array('success' => false, 'code' => 'MISSING_REQUIRED_FIELDS', 'message' => 'Please provide your full name, valid email, jurisdiction, and confirm you are 18+.');
        }

        if (empty($channels) || !$relevance || !$reason || !$promotion_plan) {
            return array('success' => false, 'code' => 'MISSING_PROMOTIONAL_DETAILS', 'message' => 'Please complete all promotional and relevance questions.');
        }

        if (!$agreed_truthful || !$agreed_disclosure || !$agreed_no_medical_claims || !$acknowledged_not_approval || !$consent_data_storage) {
            return array('success' => false, 'code' => 'MISSING_CONSENT', 'message' => 'All program agreements, disclosures, and privacy consents are required.');
        }

        // 6. Idempotency & Duplicate Protection
        global $wpdb;
        $idempotency_key = hash('sha256', strtolower($email) . ':' . $invitation['token_hash']);
        $apps_table = Config::table('affiliate_applications');

        $existing_app = $wpdb->get_row(
            $wpdb->prepare("SELECT application_key, status FROM {$apps_table} WHERE idempotency_key = %s LIMIT 1", $idempotency_key),
            \ARRAY_A
        );
        if ($existing_app) {
            return array(
                'success' => true,
                'application_key' => $existing_app['application_key'],
                'status' => $existing_app['status'],
                'duplicate' => true,
                'message' => 'Your application has already been received and is pending review.',
            );
        }

        // 7. Atomic Persistence
        $application_key = 'APP-' . strtoupper(wp_generate_password(8, false, false));
        $now = current_time('mysql', 1);

        $answers_payload = array(
            'legal_name' => $legal_name,
            'preferred_name' => $preferred_name ?: $legal_name,
            'phone' => $phone,
            'country_state' => $country_state,
            'age_confirmed' => true,
            'applicant_type' => $applicant_type,
            'channels' => $channels,
            'website_or_social' => $website_or_social,
            'audience_size' => $audience_size,
            'audience_tier' => $audience_tier,
            'relevance' => $relevance,
            'reason' => $reason,
            'promotion_plan' => $promotion_plan,
            'existing_customer' => $existing_customer,
            'consents' => array(
                'agreed_truthful' => true,
                'agreed_disclosure' => true,
                'agreed_no_medical_claims' => true,
                'acknowledged_not_approval' => true,
                'consent_data_storage' => true,
                'consent_version' => '1.0',
                'captured_at' => $now,
            ),
            'invitation_id' => $invitation['invitation_id'],
        );

        $inserted = $wpdb->insert(
            $apps_table,
            array(
                'application_key' => $application_key,
                'applicant_email' => $email,
                'applicant_name' => $legal_name,
                'display_name' => $preferred_name ?: $legal_name,
                'phone' => $phone,
                'jurisdiction' => $country_state,
                'desired_affiliate_class' => $applicant_type,
                'audience_category' => $audience_tier,
                'estimated_audience_size' => $audience_size,
                'social_channels' => wp_json_encode(array($website_or_social)),
                'promotion_methods' => wp_json_encode($channels),
                'application_answers' => wp_json_encode($answers_payload),
                'status' => 'SUBMITTED',
                'invitation_reference' => $invitation['invitation_id'],
                'idempotency_key' => $idempotency_key,
                'submitted_at' => $now,
                'created_at' => $now,
                'updated_at' => $now,
            ),
            array('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')
        );

        if ($inserted === false) {
            return array('success' => false, 'code' => 'PERSISTENCE_FAILED', 'message' => 'Unable to record your application. Please try again.');
        }

        // 8. Consume invitation
        InvitationService::consume_token($invitation['token_hash'], $application_key);

        // 9. Audit event (no raw token secrets)
        $audit_table = Config::table('audit');
        $wpdb->insert(
            $audit_table,
            array(
                'audit_id' => 'AUD-' . strtoupper(wp_generate_password(12, false, false)),
                'event_type' => 'AFFILIATE_APPLICATION_SUBMITTED',
                'actor_type' => 'APPLICANT',
                'actor_id' => $email,
                'customer_reference' => $application_key,
                'payload_json' => wp_json_encode(array(
                    'application_key' => $application_key,
                    'invitation_id' => $invitation['invitation_id'],
                    'desired_class' => $applicant_type,
                    'status' => 'SUBMITTED',
                    'submitted_at' => $now,
                )),
                'ip_hash' => $ip_hash,
                'user_agent' => isset($_SERVER['HTTP_USER_AGENT']) ? substr(sanitize_text_field(wp_unslash($_SERVER['HTTP_USER_AGENT'])), 0, 255) : '',
                'created_at' => $now,
            ),
            array('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')
        );

        return array(
            'success' => true,
            'application_key' => $application_key,
            'status' => 'SUBMITTED',
            'duplicate' => false,
            'message' => 'Application received. Your application is pending review.',
        );
    }
}
