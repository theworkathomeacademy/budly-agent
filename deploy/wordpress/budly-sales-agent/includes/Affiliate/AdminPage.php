<?php
namespace Budly\Affiliate;

if (!defined('ABSPATH')) { exit; }

final class AdminPage {
    public static function register() {
        add_action('admin_menu', array(__CLASS__, 'add_menu'));
    }

    public static function add_menu() {
        add_submenu_page('tools.php', 'BROS Affiliate MVP', 'BROS Affiliate MVP', 'manage_options', 'budly-affiliate-mvp', array(__CLASS__, 'render'));
    }

    public static function render() {
        if (!current_user_can('manage_options')) { wp_die(esc_html__('Unauthorized.', 'budly-sales-agent')); }
        $flags = FeatureFlags::all();
        echo '<div class="wrap"><h1>BROS Affiliate MVP</h1><p><strong>Non-production control surface.</strong> No payout action is available here.</p><table class="widefat"><thead><tr><th>Feature gate</th><th>State</th></tr></thead><tbody>';
        foreach ($flags as $name => $enabled) {
            echo '<tr><td>' . esc_html($name) . '</td><td>' . esc_html($enabled ? 'ON' : 'OFF') . '</td></tr>';
        }
        echo '</tbody></table></div>';
    }
}
