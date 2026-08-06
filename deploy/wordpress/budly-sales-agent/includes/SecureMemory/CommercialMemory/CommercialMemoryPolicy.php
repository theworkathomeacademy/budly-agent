<?php
namespace Budly\SecureMemory\CommercialMemory;

use Budly\SecureMemory\Config;
use Budly\SecureMemory\Memory\MemoryPolicy;

if (!defined('ABSPATH')) { exit; }

final class CommercialMemoryPolicy {
    const TYPES = array(
        'customer_interest', 'product_interest', 'preferred_format', 'purchase_intent',
        'customer_goal', 'customer_objection', 'preferred_communication_style',
        'education_progress', 'affiliate_interest', 'membership_interest',
    );
    const SOURCES = array(
        'customer_statement', 'customer_correction', 'conversation_summary',
        'verified_profile', 'governed_decision', 'administrator_correction',
    );
    const CONFIDENCE_BASES = array(
        'customer_explicit', 'customer_confirmed', 'verified_profile',
        'governed_rule_evidence', 'administrator_verified',
    );
    const EXPIRATION_POLICIES = array('customer_memory_default', 'until_withdrawn', 'date_bounded');
    const NAMESPACES = array('commercial', 'shared');

    public static function validate(array $input, $now = null) {
        $type = sanitize_key(isset($input['type']) ? $input['type'] : '');
        $namespace = sanitize_key(isset($input['namespace']) ? $input['namespace'] : 'commercial');
        $source = sanitize_key(isset($input['source']) ? $input['source'] : '');
        $basis = sanitize_key(isset($input['confidence_basis']) ? $input['confidence_basis'] : '');
        $policy = sanitize_key(isset($input['expiration_policy']) ? $input['expiration_policy'] : 'customer_memory_default');
        if (!in_array($type, self::TYPES, true) || !in_array($namespace, self::NAMESPACES, true)) { return null; }
        if (!in_array($source, self::SOURCES, true) || !in_array($basis, self::CONFIDENCE_BASES, true)) { return null; }
        if (!in_array($policy, self::EXPIRATION_POLICIES, true)) { return null; }
        if (!isset($input['confidence']) || !is_numeric($input['confidence'])) { return null; }
        $confidence = (float) $input['confidence'];
        if ($confidence < 0 || $confidence > 1) { return null; }
        $value = self::value(isset($input['value']) ? $input['value'] : null);
        if ($value === null) { return null; }
        $reference = sanitize_text_field(isset($input['source_reference']) ? $input['source_reference'] : '');
        if (!preg_match('/^[A-Za-z0-9._:-]{3,80}$/', $reference)) { return null; }
        $observed = self::date(isset($input['timestamp']) ? $input['timestamp'] : null, $now ?: time(), false);
        if ($observed === null) { return null; }
        $expires = null;
        if ($policy === 'customer_memory_default') {
            $expires = gmdate('Y-m-d H:i:s', ($now ?: time()) + Config::COMMERCIAL_MEMORY_DEFAULT_RETENTION_DAYS * DAY_IN_SECONDS);
        } elseif ($policy === 'date_bounded') {
            $expires = self::date(isset($input['expires_at']) ? $input['expires_at'] : null, $now ?: time(), true);
            if ($expires === null || strtotime($expires . ' UTC') > ($now ?: time()) + 730 * DAY_IN_SECONDS) { return null; }
        }
        return array(
            'namespace'=>$namespace, 'memory_type'=>$type, 'value'=>$value,
            'confidence'=>round($confidence, 4), 'confidence_basis'=>$basis,
            'source_type'=>$source, 'source_reference'=>$reference,
            'observed_at'=>$observed, 'expiration_policy'=>$policy, 'expires_at'=>$expires,
        );
    }

    public static function age_state(array $row, $now = null) {
        $time = $now ?: time();
        if (!empty($row['expires_at']) && strtotime($row['expires_at'] . ' UTC') <= $time) { return 'expired'; }
        $observed = strtotime($row['observed_at'] . ' UTC');
        return $observed <= $time - Config::COMMERCIAL_MEMORY_STALE_AFTER_DAYS * DAY_IN_SECONDS ? 'stale' : 'current';
    }

    public static function conversation_summary($value) {
        if (!is_array($value)) { return null; }
        $allowed = array(
            'topics_discussed', 'products_discussed', 'questions_asked', 'recommendations_made',
            'customer_decisions', 'human_escalations', 'conversation_outcome', 'next_recommended_action',
        );
        if (array_diff(array_keys($value), $allowed)) { return null; }
        $clean = array();
        foreach ($allowed as $key) {
            if (!array_key_exists($key, $value)) { $clean[$key] = in_array($key, array('conversation_outcome','next_recommended_action'), true) ? '' : array(); continue; }
            if (in_array($key, array('conversation_outcome','next_recommended_action'), true)) {
                if (!is_string($value[$key]) || mb_strlen($value[$key]) > 500 || MemoryPolicy::contains_sensitive($value[$key])) { return null; }
                $clean[$key] = sanitize_text_field($value[$key]);
            } else {
                if (!is_array($value[$key]) || count($value[$key]) > 20) { return null; }
                $clean[$key] = array();
                foreach ($value[$key] as $item) {
                    if (!is_string($item) || mb_strlen($item) > 300 || MemoryPolicy::contains_sensitive($item)) { return null; }
                    $clean[$key][] = sanitize_text_field($item);
                }
            }
        }
        return $clean;
    }

    private static function value($value) {
        if (is_bool($value) || is_int($value) || is_float($value)) { return $value; }
        if (!is_string($value) || trim($value) === '' || mb_strlen($value) > 500 || MemoryPolicy::contains_sensitive($value)) { return null; }
        return sanitize_text_field($value);
    }

    private static function date($value, $now, $future) {
        if ($value === null || $value === '') { return $future ? null : gmdate('Y-m-d H:i:s', $now); }
        $timestamp = strtotime((string) $value);
        if ($timestamp === false || (!$future && $timestamp > $now + 300) || ($future && $timestamp <= $now)) { return null; }
        return gmdate('Y-m-d H:i:s', $timestamp);
    }
}
