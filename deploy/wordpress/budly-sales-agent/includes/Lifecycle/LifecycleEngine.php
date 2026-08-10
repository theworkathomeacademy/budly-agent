<?php
namespace Budly\Lifecycle;

use Budly\SecureMemory\Config;
use Budly\SecureMemory\Validation;

if (!defined('ABSPATH')) { exit; }

final class LifecycleEngine {
    const STAGE_VISITOR = 'Visitor';
    const STAGE_EXPLORER = 'Explorer';
    const STAGE_MEMBER = 'Member';
    const STAGE_RETURNING_MEMBER = 'Returning Member';
    const STAGE_COMMUNITY_MEMBER = 'Community Member';
    const STAGE_ADVOCATE = 'Advocate';
    const STAGE_LEADER = 'Leader';

    public static function canonical_stages() {
        return array(
            self::STAGE_VISITOR,
            self::STAGE_EXPLORER,
            self::STAGE_MEMBER,
            self::STAGE_RETURNING_MEMBER,
            self::STAGE_COMMUNITY_MEMBER,
            self::STAGE_ADVOCATE,
            self::STAGE_LEADER,
        );
    }

    public static function get_relationship_health($customer_id) {
        global $wpdb;
        $table = Config::table('relationship_health');
        $row = $wpdb->get_row($wpdb->prepare(
            "SELECT * FROM {$table} WHERE customer_id = %d LIMIT 1",
            $customer_id
        ), ARRAY_A);

        if (!$row) {
            return array(
                'lifecycle_stage' => self::STAGE_VISITOR,
                'trust_score' => 0.5,
                'engagement_score' => 0.5,
                'knowledge_score' => 0.0,
                'milestones' => array(),
                'last_interaction_at' => null,
            );
        }

        return array(
            'lifecycle_stage' => $row['lifecycle_stage'],
            'trust_score' => (float) $row['trust_score'],
            'engagement_score' => (float) $row['engagement_score'],
            'knowledge_score' => (float) $row['knowledge_score'],
            'milestones' => !empty($row['milestones_json']) ? json_decode($row['milestones_json'], true) : array(),
            'last_interaction_at' => $row['last_interaction_at'],
        );
    }

    public static function transition_stage($customer_id, $new_stage, $evidence = array(), $audit_reference = '') {
        $allowed = self::canonical_stages();
        if (!in_array($new_stage, $allowed, true)) {
            throw new \InvalidArgumentException('Invalid canonical lifecycle stage: ' . $new_stage);
        }

        global $wpdb;
        $health_table = Config::table('relationship_health');
        $journey_table = Config::table('member_journey');
        $now = current_time('mysql', true);
        $audit_ref = !empty($audit_reference) ? $audit_reference : Validation::opaque_id('audit');

        $existing = $wpdb->get_row($wpdb->prepare(
            "SELECT id, milestones_json FROM {$health_table} WHERE customer_id = %d LIMIT 1",
            $customer_id
        ));

        $milestones = array();
        if ($existing && !empty($existing->milestones_json)) {
            $milestones = json_decode($existing->milestones_json, true);
        }
        $milestones[] = array(
            'stage' => $new_stage,
            'achieved_at' => $now,
            'evidence' => $evidence,
        );

        if ($existing) {
            $wpdb->update($health_table, array(
                'lifecycle_stage' => $new_stage,
                'trust_score' => min(1.0, 0.5 + (count($milestones) * 0.1)),
                'engagement_score' => min(1.0, 0.5 + (count($milestones) * 0.05)),
                'milestones_json' => wp_json_encode($milestones),
                'last_interaction_at' => $now,
                'updated_at' => $now,
            ), array('id' => $existing->id));
        } else {
            $wpdb->insert($health_table, array(
                'health_uuid' => Validation::uuid(),
                'customer_id' => $customer_id,
                'lifecycle_stage' => $new_stage,
                'trust_score' => 0.5,
                'engagement_score' => 0.5,
                'knowledge_score' => 0.1,
                'milestones_json' => wp_json_encode($milestones),
                'last_interaction_at' => $now,
                'updated_at' => $now,
            ));
        }

        $wpdb->insert($journey_table, array(
            'journey_uuid' => Validation::uuid(),
            'customer_id' => $customer_id,
            'milestone_name' => 'transition_to_' . strtolower(str_replace(' ', '_', $new_stage)),
            'lifecycle_stage' => $new_stage,
            'evidence_json' => wp_json_encode($evidence),
            'audit_reference' => $audit_ref,
            'achieved_at' => $now,
        ));

        return self::get_relationship_health($customer_id);
    }

    public static function process_commerce_event_signal($customer_id, $order_id, $gross_amount) {
        if (!$customer_id) { return null; }
        $health = self::get_relationship_health($customer_id);
        $current = $health['lifecycle_stage'];

        $next_stage = $current;
        if ($current === self::STAGE_VISITOR || $current === self::STAGE_EXPLORER) {
            $next_stage = self::STAGE_MEMBER;
        } elseif ($current === self::STAGE_MEMBER) {
            $next_stage = self::STAGE_RETURNING_MEMBER;
        }

        if ($next_stage !== $current) {
            return self::transition_stage($customer_id, $next_stage, array(
                'source' => 'commerce_event',
                'order_id' => $order_id,
                'gross_amount' => $gross_amount,
            ));
        }

        return $health;
    }
}
