<?php
namespace Budly\SecureMemory;

use Budly\SecureMemory\Database\Migrator;

if (!defined('ABSPATH')) { exit; }

final class Bootstrap {
    public static function load() {
        $base = __DIR__ . DIRECTORY_SEPARATOR;
        foreach (array(
            'Config.php','Errors.php','Validation.php','Response.php',
            'Database/Repository.php','Database/Migrator.php','Audit/AuditService.php',
            'Email/EmailTransport.php','Email/WordPressMailTransport.php',
            'Verification/VerificationRepository.php','Verification/VerificationService.php',
            'Sessions/SessionRepository.php','Sessions/SessionService.php','Sessions/SessionGuard.php',
            'Consent/ConsentRepository.php','Consent/ConsentService.php',
            'Authorization/AgentRegistry.php','Idempotency/IdempotencyService.php',
            'Profile/ProfileRepository.php','Profile/ProfileService.php','Profile/PreferenceService.php',
            'Memory/MemoryPolicy.php','Memory/MemoryRepository.php','Memory/MemoryService.php',
            'CommercialMemory/CommercialMemoryPolicy.php','CommercialMemory/CommercialMemoryRepository.php',
            'CommercialMemory/ConversationContextService.php','CommercialMemory/CommercialMemoryService.php',
            'CommercialMemory/CommercialContextBuilder.php',
            'Decision/DecisionRepository.php','Decision/DecisionService.php',
            'Admin/AdminRepository.php','Admin/AdminService.php','Admin/AdminPage.php',
            'Cleanup/CleanupService.php',
            'Security/RequestSecurity.php',
            '../Commerce/CommerceRepository.php','../Commerce/AttributionService.php',
            '../Commerce/RevenueService.php','../Commerce/WooCommerceAdapter.php',
            '../Conversation/ConversationManager.php','../Lifecycle/LifecycleEngine.php',
            'Api/Routes.php',
        ) as $relative) { require_once $base . $relative; }
    }

    public static function register() {
        self::load();
        add_action('plugins_loaded', array(__CLASS__, 'maybe_migrate'), 5);
        add_action('rest_api_init', array('Budly\\SecureMemory\\Api\\Routes', 'register'));
        add_action('admin_menu', array('Budly\\SecureMemory\\Admin\\AdminPage', 'register'));
        add_action('admin_enqueue_scripts', array('Budly\\SecureMemory\\Admin\\AdminPage', 'enqueue'));
        add_action('budly_secure_memory_cleanup', array('Budly\\SecureMemory\\Cleanup\\CleanupService', 'scheduled_run'));
        add_filter('rest_pre_dispatch', array('Budly\\SecureMemory\\Security\\RequestSecurity', 'before'), 10, 3);
        add_filter('rest_post_dispatch', array('Budly\\SecureMemory\\Security\\RequestSecurity', 'after'), 10, 3);
        \Budly\Commerce\WooCommerceAdapter::register();
        if (!wp_next_scheduled('budly_secure_memory_cleanup')) { wp_schedule_event(time()+300, 'daily', 'budly_secure_memory_cleanup'); }
    }

    public static function activate() {
        self::load();
        Migrator::migrate();
        if (!wp_next_scheduled('budly_secure_memory_cleanup')) { wp_schedule_event(time()+300, 'daily', 'budly_secure_memory_cleanup'); }
    }

    public static function deactivate(){$timestamp=wp_next_scheduled('budly_secure_memory_cleanup');if($timestamp)wp_unschedule_event($timestamp,'budly_secure_memory_cleanup');}

    public static function maybe_migrate() {
        if (get_option('budly_secure_memory_schema_version') !== Config::SCHEMA_VERSION) {
            Migrator::migrate();
        }
    }
}
