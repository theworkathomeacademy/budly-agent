<?php
namespace Budly\Conversation;

use Budly\SecureMemory\Config;
use Budly\SecureMemory\Validation;

if (!defined('ABSPATH')) { exit; }

final class ConversationManager {
    public static function get_state($customer_id, $conversation_id) {
        global $wpdb;
        $table = Config::table('conversation_state');
        $row = $wpdb->get_row($wpdb->prepare(
            "SELECT * FROM {$table} WHERE customer_id = %d AND conversation_id = %s LIMIT 1",
            $customer_id, $conversation_id
        ), ARRAY_A);

        if (!$row) {
            return array(
                'current_state' => 'visitor',
                'previous_state' => null,
                'transition_reason' => 'initial',
                'confidence_score' => 1.0,
                'active_journey' => null,
                'context' => array(),
            );
        }

        return array(
            'current_state' => $row['current_state'],
            'previous_state' => $row['previous_state'],
            'transition_reason' => $row['transition_reason'],
            'confidence_score' => (float) $row['confidence_score'],
            'active_journey' => $row['active_journey'],
            'context' => !empty($row['context_json']) ? json_decode($row['context_json'], true) : array(),
        );
    }

    public static function transition_state($customer_id, $conversation_id, $new_state, $reason = 'user_action', $active_journey = null, $confidence = 1.0, $context = array()) {
        global $wpdb;
        $valid_states = array('visitor', 'exploring', 'discovering', 'evaluating_recommendation', 'recovering', 'completed');
        if (!in_array($new_state, $valid_states, true)) {
            throw new \InvalidArgumentException('Invalid conversation state: ' . $new_state);
        }

        $current = self::get_state($customer_id, $conversation_id);
        $prev_state = $current['current_state'];

        $table = Config::table('conversation_state');
        $now = current_time('mysql', true);
        $existing_id = $wpdb->get_var($wpdb->prepare(
            "SELECT id FROM {$table} WHERE customer_id = %d AND conversation_id = %s LIMIT 1",
            $customer_id, $conversation_id
        ));

        $data = array(
            'current_state' => $new_state,
            'previous_state' => $prev_state,
            'transition_reason' => sanitize_text_field($reason),
            'confidence_score' => max(0.0, min(1.0, (float) $confidence)),
            'active_journey' => $active_journey ? sanitize_text_field($active_journey) : $current['active_journey'],
            'context_json' => wp_json_encode($context),
            'updated_at' => $now,
        );

        if ($existing_id) {
            $wpdb->update($table, $data, array('id' => $existing_id));
        } else {
            $data['state_uuid'] = Validation::uuid();
            $data['customer_id'] = $customer_id;
            $data['conversation_id'] = $conversation_id;
            $data['created_at'] = $now;
            $wpdb->insert($table, $data);
        }

        return self::get_state($customer_id, $conversation_id);
    }

    public static function record_pattern_execution($customer_id, $conversation_id, $pattern_name, $match_score, $action, $execution_data = array()) {
        global $wpdb;
        $table = Config::table('conversation_pattern_history');
        $now = current_time('mysql', true);

        $wpdb->insert($table, array(
            'pattern_uuid' => Validation::uuid(),
            'pattern_name' => sanitize_text_field($pattern_name),
            'customer_id' => $customer_id,
            'conversation_id' => $conversation_id,
            'match_score' => max(0.0, min(1.0, (float) $match_score)),
            'selected_action' => sanitize_text_field($action),
            'execution_json' => wp_json_encode($execution_data),
            'executed_at' => $now,
        ));
    }

    public static function select_next_adaptive_question($known_attributes, $journey = 'general') {
        $candidate_questions = array(
            'shopping_goal' => array('priority' => 10, 'text' => 'What are you shopping for today?'),
            'experience_level' => array('priority' => 8, 'text' => 'What is your experience level with these products?'),
            'preferred_format' => array('priority' => 7, 'text' => 'Do you prefer tinctures, edibles, gummies, or flower?'),
            'budget_range' => array('priority' => 5, 'text' => 'Do you have a target price range in mind?'),
            'purchase_timeline' => array('priority' => 4, 'text' => 'Are you looking to order today or researching for later?'),
        );

        $unasked = array();
        foreach ($candidate_questions as $key => $q) {
            if (empty($known_attributes[$key])) {
                $unasked[$key] = $q;
            }
        }

        if (empty($unasked)) {
            return null;
        }

        uasort($unasked, function($a, $b) {
            return $b['priority'] <=> $a['priority'];
        });

        $first_key = array_key_first($unasked);
        return array(
            'attribute' => $first_key,
            'question' => $unasked[$first_key]['text'],
            'info_value' => $unasked[$first_key]['priority'] / 10.0,
        );
    }
}
