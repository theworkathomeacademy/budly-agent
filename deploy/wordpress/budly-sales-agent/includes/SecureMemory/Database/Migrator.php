<?php
namespace Budly\SecureMemory\Database;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class Migrator {
    public static function migrate() {
        global $wpdb;
        require_once ABSPATH . 'wp-admin/includes/upgrade.php';
        $charset = $wpdb->get_charset_collate();
        $tables = array();

        $tables[] = "CREATE TABLE " . Config::table('customers') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, public_id varchar(40) NOT NULL,
            email varchar(190) NOT NULL, email_hash char(64) NOT NULL, preferred_name varchar(120) NOT NULL DEFAULT '',
            identity_version int unsigned NOT NULL DEFAULT 1, status varchar(20) NOT NULL DEFAULT 'active', email_verified tinyint(1) NOT NULL DEFAULT 0,
            created_at datetime NOT NULL, updated_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY public_id (public_id), UNIQUE KEY email_hash (email_hash), KEY status (status)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('preferences') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, customer_id bigint(20) unsigned NOT NULL, preference_key varchar(80) NOT NULL,
            preference_json longtext NOT NULL, classification varchar(30) NOT NULL DEFAULT 'customer_visible', schema_version int unsigned NOT NULL DEFAULT 1,
            created_at datetime NOT NULL, updated_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY customer_preference (customer_id,preference_key), KEY customer_id (customer_id)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('conversation_memory') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, memory_id varchar(40) NOT NULL, customer_id bigint(20) unsigned NOT NULL,
            conversation_id varchar(64) NOT NULL, namespace varchar(40) NOT NULL, memory_type varchar(40) NOT NULL, classification varchar(30) NOT NULL,
            schema_version int unsigned NOT NULL DEFAULT 1, source_agent_id varchar(60) NOT NULL, summary_json longtext NOT NULL, consent_reference varchar(40) NOT NULL,
            created_at datetime NOT NULL, updated_at datetime NOT NULL, expires_at datetime NULL, deleted_at datetime NULL,
            provenance_json longtext NULL, content_hash char(64) NULL, retention_policy varchar(40) NOT NULL DEFAULT 'customer_memory_default', corrected_at datetime NULL,
            PRIMARY KEY (id), UNIQUE KEY memory_id (memory_id), UNIQUE KEY customer_content (customer_id,content_hash), KEY customer_namespace (customer_id,namespace), KEY conversation_id (conversation_id), KEY expires_at (expires_at)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('consent') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, consent_id varchar(40) NOT NULL, customer_id bigint(20) unsigned NOT NULL,
            consent_type varchar(30) NOT NULL, status varchar(20) NOT NULL, consent_version varchar(20) NOT NULL, source varchar(60) NOT NULL,
            updated_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY consent_id (consent_id), UNIQUE KEY customer_type (customer_id,consent_type), KEY status (status)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('consent_history') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, history_id varchar(40) NOT NULL, customer_id bigint(20) unsigned NOT NULL,
            consent_type varchar(30) NOT NULL, status varchar(20) NOT NULL, consent_version varchar(20) NOT NULL, source varchar(60) NOT NULL,
            actor_type varchar(30) NOT NULL, created_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY history_id (history_id), KEY customer_type_time (customer_id,consent_type,created_at)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('verification_requests') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, request_id varchar(40) NOT NULL, customer_id bigint(20) unsigned NULL,
            email varchar(190) NOT NULL, email_hash char(64) NOT NULL, code_hash varchar(255) NOT NULL, ip_hash char(64) NOT NULL,
            attempts int unsigned NOT NULL DEFAULT 0, locked_at datetime NULL, consumed_at datetime NULL, expires_at datetime NOT NULL,
            delivery_status varchar(20) NOT NULL DEFAULT 'pending', created_at datetime NOT NULL,
            PRIMARY KEY (id), UNIQUE KEY request_id (request_id), KEY email_created (email_hash,created_at), KEY ip_created (ip_hash,created_at), KEY expires_at (expires_at)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('sessions') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, session_id varchar(40) NOT NULL, customer_id bigint(20) unsigned NOT NULL,
            token_hash char(64) NOT NULL, agent_id varchar(60) NOT NULL, status varchar(20) NOT NULL DEFAULT 'active',
            created_at datetime NOT NULL, last_seen_at datetime NOT NULL, idle_expires_at datetime NOT NULL, absolute_expires_at datetime NOT NULL,
            revoked_at datetime NULL, revoke_reason varchar(80) NOT NULL DEFAULT '', PRIMARY KEY (id), UNIQUE KEY session_id (session_id), UNIQUE KEY token_hash (token_hash),
            KEY customer_status (customer_id,status), KEY idle_expires_at (idle_expires_at), KEY absolute_expires_at (absolute_expires_at)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('audit') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, audit_id varchar(40) NOT NULL, event_type varchar(80) NOT NULL,
            actor_type varchar(30) NOT NULL, actor_id varchar(80) NOT NULL DEFAULT '', customer_reference varchar(80) NOT NULL DEFAULT '',
            conversation_id varchar(64) NOT NULL DEFAULT '', result varchar(20) NOT NULL, severity varchar(20) NOT NULL,
            metadata_json longtext NULL, created_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY audit_id (audit_id),
            KEY event_time (event_type,created_at), KEY actor_time (actor_type,actor_id,created_at), KEY severity_time (severity,created_at)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('schema_migrations') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, version varchar(30) NOT NULL, checksum char(64) NOT NULL,
            status varchar(20) NOT NULL, applied_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY version (version)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('agents') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, agent_id varchar(60) NOT NULL, display_name varchar(120) NOT NULL,
            status varchar(20) NOT NULL DEFAULT 'active', scopes_json longtext NOT NULL, namespaces_json longtext NOT NULL,
            created_at datetime NOT NULL, updated_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY agent_id (agent_id), KEY status (status)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('memory_contexts') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, context_id varchar(40) NOT NULL, session_id varchar(40) NOT NULL,
            customer_id bigint(20) unsigned NOT NULL, conversation_id varchar(64) NOT NULL, agent_id varchar(60) NOT NULL,
            purpose varchar(80) NOT NULL, approved tinyint(1) NOT NULL DEFAULT 0, start_fresh tinyint(1) NOT NULL DEFAULT 0,
            approved_at datetime NULL, expires_at datetime NOT NULL, created_at datetime NOT NULL, updated_at datetime NOT NULL,
            PRIMARY KEY (id), UNIQUE KEY context_id (context_id), UNIQUE KEY session_conversation_agent (session_id,conversation_id,agent_id),
            KEY customer_context (customer_id,conversation_id), KEY expires_at (expires_at)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('idempotency') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, customer_id bigint(20) unsigned NOT NULL, session_id varchar(40) NOT NULL,
            endpoint varchar(100) NOT NULL, idempotency_key varchar(80) NOT NULL, request_hash char(64) NOT NULL,
            response_json longtext NOT NULL, created_at datetime NOT NULL, expires_at datetime NOT NULL,
            PRIMARY KEY (id), UNIQUE KEY request_identity (customer_id,endpoint,idempotency_key), KEY expires_at (expires_at)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('rule_configurations') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, configuration_id varchar(40) NOT NULL,
            configuration_type varchar(40) NOT NULL, version varchar(60) NOT NULL, status varchar(20) NOT NULL,
            configuration_json longtext NOT NULL, activated_by bigint(20) unsigned NULL,
            activated_at datetime NULL, created_at datetime NOT NULL, PRIMARY KEY (id),
            UNIQUE KEY configuration_id (configuration_id), UNIQUE KEY type_version (configuration_type,version),
            KEY active_configuration (configuration_type,status)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('decision_evidence') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, decision_id varchar(40) NOT NULL,
            decision_type varchar(30) NOT NULL, customer_reference varchar(80) NOT NULL DEFAULT '',
            session_id varchar(40) NOT NULL DEFAULT '', conversation_id varchar(64) NOT NULL DEFAULT '',
            journey varchar(80) NOT NULL DEFAULT '', objective text NULL, inputs_json longtext NOT NULL,
            rule_version varchar(60) NOT NULL, eligible_products_json longtext NOT NULL,
            excluded_products_json longtext NOT NULL, outcome varchar(30) NOT NULL,
            selected_product_id varchar(100) NULL, confidence varchar(30) NULL,
            escalation_reference varchar(80) NULL, resulting_action varchar(80) NOT NULL,
            created_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY decision_id (decision_id),
            KEY decision_time (decision_type,created_at), KEY outcome_time (outcome,created_at),
            KEY customer_time (customer_reference,created_at)
        ) $charset;";

        foreach ($tables as $sql) { dbDelta($sql); }
        $migration_table = Config::table('schema_migrations');
        $checksum = hash('sha256', implode("\n", $tables));
        $existing = $wpdb->get_var($wpdb->prepare("SELECT version FROM {$migration_table} WHERE version = %s", Config::SCHEMA_VERSION));
        if (!$existing) {
            $result = $wpdb->insert($migration_table, array('version'=>Config::SCHEMA_VERSION,'checksum'=>$checksum,'status'=>'applied','applied_at'=>current_time('mysql', true)));
            if ($result === false) { throw new \RuntimeException('Secure-memory migration record could not be written.'); }
        }
        update_option('budly_secure_memory_schema_version', Config::SCHEMA_VERSION, false);
        $agent_table = Config::table('agents');
        $agent = $wpdb->get_var($wpdb->prepare("SELECT agent_id FROM {$agent_table} WHERE agent_id = %s", Config::DEFAULT_AGENT_ID));
        if (!$agent) {
            $now = current_time('mysql', true);
            $wpdb->insert($agent_table, array(
                'agent_id'=>Config::DEFAULT_AGENT_ID, 'display_name'=>'Budly Sales Agent', 'status'=>'active',
                'scopes_json'=>wp_json_encode(array('identity:read','profile:read','profile:update','preferences:read','preferences:update','consent:read','consent:update','memory:preview','memory:read:shared','memory:read:agent','memory:write:summary','memory:delete:self','memory:export:self')),
                'namespaces_json'=>wp_json_encode(array('shared','sales')), 'created_at'=>$now, 'updated_at'=>$now,
            ));
        }
        $configuration_table = Config::table('rule_configurations');
        $configuration_versions = array(
            'qualification'=>'qualification-1.3.4.1',
            'recommendation'=>'recommendation-1.3.4.1',
            'catalog'=>'catalog-allowlist-2026-07-16',
            'journeys'=>'journey-routing-1.3.4.1',
            'escalation'=>'escalation-1.3.4.1',
            'consent'=>'secure-memory-consent-1.0',
            'retention'=>'secure-memory-retention-1.1.0',
        );
        foreach ($configuration_versions as $type=>$version) {
            $existing_configuration = $wpdb->get_var($wpdb->prepare(
                "SELECT configuration_id FROM {$configuration_table} WHERE configuration_type=%s AND version=%s LIMIT 1",
                $type, $version
            ));
            if (!$existing_configuration) {
                $now = current_time('mysql', true);
                $wpdb->insert($configuration_table, array(
                    'configuration_id'=>\Budly\SecureMemory\Validation::opaque_id('cfg'),
                    'configuration_type'=>$type, 'version'=>$version, 'status'=>'active',
                    'configuration_json'=>wp_json_encode(array('version'=>$version,'release'=>'1.3.4')),
                    'activated_by'=>null, 'activated_at'=>$now, 'created_at'=>$now,
                ));
            }
        }
    }
}
