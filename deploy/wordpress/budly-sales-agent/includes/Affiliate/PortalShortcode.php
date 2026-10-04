<?php
namespace Budly\Affiliate;

if (!defined('ABSPATH')) { exit; }

final class PortalShortcode {
    public static function register() { add_shortcode('budly_affiliate_portal', array(__CLASS__, 'render')); }

    public static function render() {
        require_once __DIR__ . '/SyntheticScope.php';
        $decision = SyntheticScope::authorize_portal(is_user_logged_in() ? get_current_user_id() : 0);
        if (!FeatureFlags::enabled('affiliate_portal_enabled')) { return ''; }
        if (!is_user_logged_in()) {
            return '<p>Sign in to access the affiliate portal.</p>';
        }
        if (empty($decision['allowed'])) {
            return '<p>The Affiliate portal is not available for this account.</p>';
        }
        $scope = $decision['scope'];
        return '<section class="budly-affiliate-portal" data-mode="read-only"><h2>Affiliate Portal</h2><p><strong>' . esc_html($scope['affiliate_code']) . '</strong></p><p>Your governed synthetic Affiliate summary is available through the authenticated BROS service.</p><p>Customer identities are never displayed.</p></section>';
    }
}
