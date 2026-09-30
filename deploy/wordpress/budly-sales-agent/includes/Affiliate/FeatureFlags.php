<?php
namespace Budly\Affiliate;

if (!defined('ABSPATH')) { exit; }

final class FeatureFlags {
    private const DEFAULTS = array(
        'affiliate_referral_enabled' => false,
        'affiliate_attribution_enabled' => false,
        'affiliate_commission_processing_enabled' => false,
        'affiliate_portal_enabled' => false,
        'affiliate_payout_submission_enabled' => false,
    );

    public static function enabled($name) {
        if (!array_key_exists($name, self::DEFAULTS)) { return false; }
        return get_option('budly_' . $name, self::DEFAULTS[$name]) === true;
    }

    public static function all() {
        $result = array();
        foreach (self::DEFAULTS as $name => $default) { $result[$name] = self::enabled($name); }
        return $result;
    }
}
