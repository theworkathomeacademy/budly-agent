<?php
namespace Budly\SecureMemory;

if (!defined('ABSPATH')) { exit; }

final class Config {
    const API_NAMESPACE = 'budly-identity/v1';
    const API_VERSION = '1.1';
    const SCHEMA_VERSION = '1.4.0';
    const BROS_RULE_VERSION = 'bros-rules-1.5.0.0';
    const COMMERCE_CONFIG_VERSION = 'commerce-attribution-1.6.0.0';
    const CONSENT_VERSION = '1.0';
    const SESSION_COOKIE = 'budly_memory_session';
    const SESSION_IDLE_SECONDS = 1800;
    const SESSION_ABSOLUTE_SECONDS = 7200;
    const VERIFICATION_TTL_SECONDS = 600;
    const VERIFICATION_MAX_ATTEMPTS = 5;
    const VERIFICATION_EMAIL_LIMIT = 3;
    const VERIFICATION_IP_LIMIT = 10;
    const VERIFICATION_RATE_WINDOW = 3600;
    const VERIFICATION_RESEND_COOLDOWN_SECONDS = 60;
    const MAX_JSON_BYTES = 32768;
    const DEFAULT_AGENT_ID = 'sales-agent';
    const SUMMARY_MAX_BYTES = 8192;
    const SUMMARY_MAX_LIST_ITEMS = 20;
    const SUMMARY_MAX_ITEM_CHARS = 500;
    const MEMORY_MAX_ACTIVE_PER_CUSTOMER = 100;
    const MEMORY_DEFAULT_RETENTION_DAYS = 365;
    const VERIFICATION_ARTIFACT_RETENTION_DAYS = 7;
    const SESSION_RECORD_RETENTION_DAYS = 30;
    const CLEANUP_BATCH_SIZE = 500;
    const COMMERCIAL_MEMORY_MAX_ACTIVE = 200;
    const COMMERCIAL_MEMORY_DEFAULT_RETENTION_DAYS = 365;
    const COMMERCIAL_MEMORY_STALE_AFTER_DAYS = 180;

    public static function table($logical_name) {
        global $wpdb;
        $allowed = array(
            'customers', 'preferences', 'conversation_memory', 'consent',
            'consent_history', 'verification_requests', 'sessions', 'audit',
            'schema_migrations', 'agents', 'memory_contexts', 'idempotency',
            'decision_evidence', 'rule_configurations', 'commercial_memory',
            'conversation_contexts', 'commerce_events', 'order_links',
            'affiliate_attribution', 'revenue_daily',
        );
        if (!in_array($logical_name, $allowed, true)) {
            throw new \InvalidArgumentException('Unknown secure-memory table.');
        }
        return $wpdb->prefix . 'budly_' . $logical_name;
    }

    public static function rate_limit($name) {
        $defaults = array(
            'verification_email' => self::VERIFICATION_EMAIL_LIMIT,
            'verification_ip' => self::VERIFICATION_IP_LIMIT,
            'verification_attempts' => self::VERIFICATION_MAX_ATTEMPTS,
            'commercial_memory_read' => 120,
            'commercial_memory_write' => 60,
            'commercial_memory_export' => 10,
            'commerce_admin_read' => 120,
            'commerce_admin_export' => 10,
        );
        if (!isset($defaults[$name])) { return 0; }
        return max(1, (int) get_option('budly_memory_' . $name . '_limit', $defaults[$name]));
    }

    public static function verification_resend_cooldown_seconds() {
        return max(1, (int) get_option(
            'budly_memory_verification_resend_cooldown_seconds',
            self::VERIFICATION_RESEND_COOLDOWN_SECONDS
        ));
    }
    public static function retention_days($name){$defaults=array('verification'=>self::VERIFICATION_ARTIFACT_RETENTION_DAYS,'session'=>self::SESSION_RECORD_RETENTION_DAYS,'memory'=>self::MEMORY_DEFAULT_RETENTION_DAYS);return isset($defaults[$name])?max(1,(int)get_option('budly_memory_'.$name.'_retention_days',$defaults[$name])):0;}
}
