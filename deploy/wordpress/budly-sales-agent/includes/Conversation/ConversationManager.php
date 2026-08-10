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

    public static function canonical_patterns() {
        return array(
            'first_visit' => array('label' => 'First Visit', 'action' => 'welcome_and_explore'),
            'returning_member' => array('label' => 'Returning Member', 'action' => 'resume_context'),
            'educational_conversation' => array('label' => 'Educational Conversation', 'action' => 'explain_concepts'),
            'product_recommendation' => array('label' => 'Product Recommendation', 'action' => 'evaluate_catalog_match'),
            'comparison' => array('label' => 'Comparison', 'action' => 'compare_attributes'),
            'complaint' => array('label' => 'Complaint', 'action' => 'deescalate_and_route'),
            'affiliate_inquiry' => array('label' => 'Affiliate Inquiry', 'action' => 'provide_affiliate_info'),
            'wholesale_inquiry' => array('label' => 'Wholesale Inquiry', 'action' => 'route_to_wholesale_sales'),
            'human_handoff' => array('label' => 'Human Handoff', 'action' => 'save_context_for_human_review'),
            'conversation_recovery' => array('label' => 'Conversation Recovery', 'action' => 'restore_session_state'),
        );
    }

    public static function select_pattern($intent_or_message, $context = array()) {
        $patterns = self::canonical_patterns();
        $msg = strtolower((string) $intent_or_message);

        if (strpos($msg, 'wholesale') !== false || strpos($msg, 'bulk') !== false) {
            return array('name' => 'wholesale_inquiry', 'pattern' => $patterns['wholesale_inquiry'], 'match_score' => 0.95);
        }
        if (strpos($msg, 'affiliate') !== false || strpos($msg, 'referral') !== false) {
            return array('name' => 'affiliate_inquiry', 'pattern' => $patterns['affiliate_inquiry'], 'match_score' => 0.95);
        }
        if (strpos($msg, 'complaint') !== false || strpos($msg, 'bad reaction') !== false || strpos($msg, 'damaged') !== false) {
            return array('name' => 'complaint', 'pattern' => $patterns['complaint'], 'match_score' => 0.90);
        }
        if (strpos($msg, 'human') !== false || strpos($msg, 'support') !== false) {
            return array('name' => 'human_handoff', 'pattern' => $patterns['human_handoff'], 'match_score' => 0.85);
        }
        if (strpos($msg, 'compare') !== false) {
            return array('name' => 'comparison', 'pattern' => $patterns['comparison'], 'match_score' => 0.90);
        }
        if (strpos($msg, 'how to') !== false || strpos($msg, 'learn') !== false || strpos($msg, 'what is') !== false) {
            return array('name' => 'educational_conversation', 'pattern' => $patterns['educational_conversation'], 'match_score' => 0.85);
        }
        if (!empty($context['is_returning_member'])) {
            return array('name' => 'returning_member', 'pattern' => $patterns['returning_member'], 'match_score' => 0.90);
        }
        if (!empty($context['needs_recovery'])) {
            return array('name' => 'conversation_recovery', 'pattern' => $patterns['conversation_recovery'], 'match_score' => 0.90);
        }
        if (!empty($context['ready_for_recommendation'])) {
            return array('name' => 'product_recommendation', 'pattern' => $patterns['product_recommendation'], 'match_score' => 0.90);
        }

        return array('name' => 'first_visit', 'pattern' => $patterns['first_visit'], 'match_score' => 0.80);
    }
}
