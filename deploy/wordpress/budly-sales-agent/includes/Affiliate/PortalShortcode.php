<?php
namespace Budly\Affiliate;

if (!defined('ABSPATH')) { exit; }

final class PortalShortcode {
    public static function register() { add_shortcode('budly_affiliate_portal', array(__CLASS__, 'render')); }

    public static function render() {
        if (!FeatureFlags::enabled('affiliate_portal_enabled')) { return ''; }
        if (!is_user_logged_in()) { return '<p>Sign in to access the affiliate portal.</p>'; }
        return '<section class="budly-affiliate-portal" data-mode="read-only"><h2>Affiliate Portal</h2><p>Your governed affiliate summary is available through the authenticated BROS service.</p><p>Customer identities are never displayed.</p></section>';
    }
}
