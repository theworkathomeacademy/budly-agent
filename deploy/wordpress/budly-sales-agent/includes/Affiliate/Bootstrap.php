<?php
namespace Budly\Affiliate;

if (!defined('ABSPATH')) { exit; }

final class Bootstrap {
    public static function register() {
        require_once __DIR__ . '/FeatureFlags.php';
        require_once __DIR__ . '/SyntheticScope.php';
        require_once __DIR__ . '/InvitationService.php';
        require_once __DIR__ . '/ApplicationService.php';
        require_once __DIR__ . '/PublicPage.php';
        require_once __DIR__ . '/ApplicationShortcode.php';
        require_once __DIR__ . '/PortalShortcode.php';
        require_once __DIR__ . '/AdminPage.php';

        PublicPage::register();
        ApplicationShortcode::register();
        PortalShortcode::register();
        AdminPage::register();
    }
}
