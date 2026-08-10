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
        $tables[] = "CREATE TABLE " . Config::table('commercial_memory') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, memory_uuid char(36) NOT NULL,
            customer_id bigint(20) unsigned NOT NULL, namespace varchar(40) NOT NULL DEFAULT 'commercial',
            memory_type varchar(50) NOT NULL, value_json longtext NOT NULL, confidence decimal(5,4) NOT NULL,
            confidence_basis varchar(80) NOT NULL, source_type varchar(50) NOT NULL, source_reference varchar(80) NOT NULL,
            observed_at datetime NOT NULL, consent_state varchar(20) NOT NULL, consent_reference varchar(40) NOT NULL,
            expiration_policy varchar(50) NOT NULL, expires_at datetime NULL, version int unsigned NOT NULL DEFAULT 1,
            supersedes_uuid char(36) NULL, status varchar(20) NOT NULL DEFAULT 'active', invalidated_reason varchar(160) NULL,
            audit_reference varchar(40) NOT NULL, created_at datetime NOT NULL, updated_at datetime NOT NULL, deleted_at datetime NULL,
            PRIMARY KEY (id), UNIQUE KEY memory_uuid (memory_uuid), KEY customer_status (customer_id,status),
            KEY customer_type (customer_id,memory_type), KEY namespace_type (namespace,memory_type),
            KEY expiration_review (status,expires_at), KEY supersedes_uuid (supersedes_uuid)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('conversation_contexts') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, context_uuid char(36) NOT NULL,
            customer_id bigint(20) unsigned NOT NULL, conversation_id varchar(64) NOT NULL,
            summary_json longtext NOT NULL, source_type varchar(50) NOT NULL, consent_reference varchar(40) NOT NULL,
            audit_reference varchar(40) NOT NULL, version int unsigned NOT NULL DEFAULT 1,
            observed_at datetime NOT NULL, expires_at datetime NULL, status varchar(20) NOT NULL DEFAULT 'active',
            created_at datetime NOT NULL, updated_at datetime NOT NULL, deleted_at datetime NULL,
            PRIMARY KEY (id), UNIQUE KEY context_uuid (context_uuid), UNIQUE KEY customer_conversation_version (customer_id,conversation_id,version),
            KEY customer_status (customer_id,status), KEY conversation_id (conversation_id), KEY expiration_review (status,expires_at)
        ) $charset;";
        $pre_commerce_table_count = count($tables);
        $tables[] = "CREATE TABLE " . Config::table('commerce_events') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, event_uuid char(36) NOT NULL,
            external_event_key varchar(191) NOT NULL, order_id bigint(20) unsigned NULL, event_type varchar(40) NOT NULL,
            source varchar(40) NOT NULL DEFAULT 'woocommerce', verification_status varchar(20) NOT NULL,
            customer_id bigint(20) unsigned NULL, session_id varchar(40) NULL, conversation_id varchar(64) NULL,
            decision_id varchar(40) NULL, product_id bigint(20) unsigned NULL, affiliate_id varchar(100) NULL,
            currency char(3) NULL, gross_amount decimal(20,6) NOT NULL DEFAULT 0, discount_amount decimal(20,6) NOT NULL DEFAULT 0,
            shipping_amount decimal(20,6) NOT NULL DEFAULT 0, tax_amount decimal(20,6) NOT NULL DEFAULT 0,
            refund_amount decimal(20,6) NOT NULL DEFAULT 0, net_amount decimal(20,6) NOT NULL DEFAULT 0,
            attribution_status varchar(30) NOT NULL DEFAULT 'unattributed', reconciliation_status varchar(30) NOT NULL DEFAULT 'pending',
            evidence_json longtext NULL, audit_reference varchar(40) NOT NULL, source_occurred_at datetime NOT NULL,
            processed_at datetime NOT NULL, created_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY event_uuid (event_uuid),
            UNIQUE KEY external_event_key (external_event_key), KEY order_event (order_id,event_type),
            KEY customer_time (customer_id,source_occurred_at), KEY attribution_time (attribution_status,source_occurred_at),
            KEY currency_time (currency,source_occurred_at), KEY reconciliation_status (reconciliation_status)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('order_links') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, link_uuid char(36) NOT NULL, order_id bigint(20) unsigned NOT NULL,
            customer_id bigint(20) unsigned NULL, session_id varchar(40) NULL, conversation_id varchar(64) NULL,
            decision_id varchar(40) NULL, attribution_status varchar(30) NOT NULL, attribution_method varchar(40) NOT NULL,
            confidence varchar(20) NOT NULL DEFAULT 'deterministic', evidence_json longtext NOT NULL,
            evidence_observed_at datetime NOT NULL, rule_version varchar(60) NOT NULL, conflict_state varchar(30) NOT NULL DEFAULT 'none',
            resolution_state varchar(30) NOT NULL DEFAULT 'resolved', audit_reference varchar(40) NOT NULL,
            created_at datetime NOT NULL, updated_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY link_uuid (link_uuid),
            UNIQUE KEY order_id (order_id), KEY customer_status (customer_id,attribution_status),
            KEY conversation_id (conversation_id), KEY decision_id (decision_id), KEY resolution_state (resolution_state)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('affiliate_attribution') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, attribution_uuid char(36) NOT NULL, order_id bigint(20) unsigned NOT NULL,
            affiliate_id varchar(100) NOT NULL, referral_id varchar(100) NULL, source varchar(40) NOT NULL,
            verification_status varchar(20) NOT NULL, evidence_json longtext NOT NULL, audit_reference varchar(40) NOT NULL,
            created_at datetime NOT NULL, updated_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY attribution_uuid (attribution_uuid),
            UNIQUE KEY order_affiliate (order_id,affiliate_id), KEY affiliate_time (affiliate_id,created_at)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('revenue_daily') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, revenue_date date NOT NULL, currency char(3) NOT NULL,
            product_id bigint(20) unsigned NOT NULL DEFAULT 0, affiliate_id varchar(100) NOT NULL DEFAULT '',
            orders_count bigint(20) unsigned NOT NULL DEFAULT 0, gross_amount decimal(20,6) NOT NULL DEFAULT 0,
            discount_amount decimal(20,6) NOT NULL DEFAULT 0, shipping_amount decimal(20,6) NOT NULL DEFAULT 0,
            tax_amount decimal(20,6) NOT NULL DEFAULT 0, refund_amount decimal(20,6) NOT NULL DEFAULT 0,
            net_amount decimal(20,6) NOT NULL DEFAULT 0, attributed_amount decimal(20,6) NOT NULL DEFAULT 0,
            unattributed_amount decimal(20,6) NOT NULL DEFAULT 0, source_event_count bigint(20) unsigned NOT NULL DEFAULT 0,
            calculated_at datetime NOT NULL, config_version varchar(60) NOT NULL, PRIMARY KEY (id),
            UNIQUE KEY daily_dimension (revenue_date,currency,product_id,affiliate_id), KEY currency_date (currency,revenue_date)
        ) $charset;";
        $pre_v17_table_count = count($tables);
        $tables[] = "CREATE TABLE " . Config::table('conversation_state') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, state_uuid char(36) NOT NULL,
            customer_id bigint(20) unsigned NOT NULL, conversation_id varchar(64) NOT NULL,
            current_state varchar(40) NOT NULL DEFAULT 'visitor', previous_state varchar(40) NULL,
            transition_reason varchar(120) NOT NULL DEFAULT 'initial', confidence_score decimal(5,4) NOT NULL DEFAULT 1.0000,
            active_journey varchar(80) NULL, context_json longtext NULL, updated_at datetime NOT NULL,
            created_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY state_uuid (state_uuid),
            UNIQUE KEY customer_conversation (customer_id,conversation_id), KEY state_time (current_state,updated_at)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('conversation_pattern_history') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, pattern_uuid char(36) NOT NULL,
            pattern_name varchar(60) NOT NULL, customer_id bigint(20) unsigned NOT NULL,
            conversation_id varchar(64) NOT NULL, match_score decimal(5,4) NOT NULL DEFAULT 1.0000,
            selected_action varchar(80) NOT NULL, execution_json longtext NULL, executed_at datetime NOT NULL,
            PRIMARY KEY (id), UNIQUE KEY pattern_uuid (pattern_uuid), KEY pattern_name_time (pattern_name,executed_at),
            KEY customer_pattern (customer_id,pattern_name)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('relationship_health') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, health_uuid char(36) NOT NULL,
            customer_id bigint(20) unsigned NOT NULL, lifecycle_stage varchar(40) NOT NULL DEFAULT 'Visitor',
            trust_score decimal(5,4) NOT NULL DEFAULT 0.5000, engagement_score decimal(5,4) NOT NULL DEFAULT 0.5000,
            knowledge_score decimal(5,4) NOT NULL DEFAULT 0.0000, milestones_json longtext NULL,
            last_interaction_at datetime NOT NULL, updated_at datetime NOT NULL, PRIMARY KEY (id),
            UNIQUE KEY health_uuid (health_uuid), UNIQUE KEY customer_id (customer_id), KEY stage_health (lifecycle_stage,updated_at)
        ) $charset;";
        $tables[] = "CREATE TABLE " . Config::table('member_journey') . " (
            id bigint(20) unsigned NOT NULL AUTO_INCREMENT, journey_uuid char(36) NOT NULL,
            customer_id bigint(20) unsigned NOT NULL, milestone_name varchar(80) NOT NULL,
            lifecycle_stage varchar(40) NOT NULL, evidence_json longtext NOT NULL, audit_reference varchar(40) NOT NULL,
            achieved_at datetime NOT NULL, PRIMARY KEY (id), UNIQUE KEY journey_uuid (journey_uuid),
            KEY customer_milestone (customer_id,milestone_name), KEY stage_time (lifecycle_stage,achieved_at)
        ) $charset;";

        $installed_version = (string) get_option('budly_secure_memory_schema_version', '0.0.0');
        if (version_compare($installed_version, Config::SCHEMA_VERSION, '<')) {
            $tables_to_apply = version_compare($installed_version, '1.4.0', '>=')
                ? array_slice($tables, $pre_v17_table_count)
                : (version_compare($installed_version, '1.3.0', '>=') ? array_slice($tables, $pre_commerce_table_count) : $tables);
            foreach ($tables_to_apply as $sql) { dbDelta($sql); }
        }
        foreach (array('commerce_events', 'order_links', 'affiliate_attribution', 'revenue_daily', 'conversation_state', 'conversation_pattern_history', 'relationship_health', 'member_journey') as $required_table) {
            $table_name = Config::table($required_table);
            if ($wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $table_name)) !== $table_name) {
                throw new \RuntimeException('Required table is missing after migration: ' . $required_table);
            }
        }
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
                'scopes_json'=>wp_json_encode(array('identity:read','profile:read','profile:update','preferences:read','preferences:update','consent:read','consent:update','memory:preview','memory:read:shared','memory:read:agent','memory:write:summary','memory:delete:self','memory:export:self','commercial-memory:read','commercial-memory:write','commercial-memory:delete','commercial-memory:export','conversation:read','conversation:write','lifecycle:read','lifecycle:update')),
                'namespaces_json'=>wp_json_encode(array('shared','sales','commercial','conversation','lifecycle')), 'created_at'=>$now, 'updated_at'=>$now,
            ));
        } else {
            $now=current_time('mysql',true);
            $wpdb->update($agent_table,array(
                'scopes_json'=>wp_json_encode(array('identity:read','profile:read','profile:update','preferences:read','preferences:update','consent:read','consent:update','memory:preview','memory:read:shared','memory:read:agent','memory:write:summary','memory:delete:self','memory:export:self','commercial-memory:read','commercial-memory:write','commercial-memory:delete','commercial-memory:export','conversation:read','conversation:write','lifecycle:read','lifecycle:update')),
                'namespaces_json'=>wp_json_encode(array('shared','sales','commercial','conversation','lifecycle')),'updated_at'=>$now,
            ),array('agent_id'=>Config::DEFAULT_AGENT_ID));
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
            'commercial_memory'=>'commercial-memory-1.5.0.0',
            'commerce_attribution'=>Config::COMMERCE_CONFIG_VERSION,
            'conversation_intelligence'=>'conversation-intelligence-1.7.0.0',
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
                    'configuration_json'=>wp_json_encode(array('version'=>$version,'release'=>$type==='commerce_attribution'?'1.6.0':($type==='commercial_memory'?'1.5.0':'1.3.4'))),
                    'activated_by'=>null, 'activated_at'=>$now, 'created_at'=>$now,
                ));
            }
        }
    }
}
