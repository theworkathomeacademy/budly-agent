<?php
namespace Budly\Commerce;

if (!defined('ABSPATH')) { exit; }

/**
 * Issues and verifies a short-lived, non-secret commerce correlation token.
 *
 * The browser carries only an opaque identifier plus an HMAC. Authoritative
 * journey, decision, product, and attribution data remain server-side.
 */
final class CommerceCorrelationService {
    const QUERY_KEY = 'budly_correlation';
    const COOKIE_KEY = 'budly_commerce_correlation';
    const TRANSIENT_PREFIX = 'budly_sts2_';
    const TTL = 7 * DAY_IN_SECONDS;

    public static function register() {
        add_action('template_redirect', array(__CLASS__, 'capture_landing_token'), 1);
        add_filter('woocommerce_add_cart_item_data', array(__CLASS__, 'attach_cart_data'), 10, 3);
        add_action('woocommerce_checkout_create_order', array(__CLASS__, 'attach_order_metadata'), 10, 2);
    }

    public static function issue(array $decision, array $request, array $session = array()) {
        if (($decision['outcome'] ?? '') !== 'recommended' || empty($decision['decision_id']) || empty($decision['selected_product_id'])) {
            return null;
        }
        $conversation = sanitize_text_field((string)($request['conversation_id'] ?? ''));
        $decision_id = sanitize_text_field((string)$decision['decision_id']);
        $product_id = sanitize_key((string)$decision['selected_product_id']);
        if (!preg_match('/^(?:conv_[a-z0-9]{12,40}|[a-f0-9-]{36})$/', $conversation)
            || !preg_match('/^dec_[a-z0-9]{12,40}$/', $decision_id)
            || $product_id === '') {
            return null;
        }

        $correlation_id = 'sts2_' . bin2hex(random_bytes(16));
        $attribution = array();
        foreach (array('source','platform','content_id','campaign_id','cta_id','product_or_topic','published_post_id') as $field) {
            if (isset($decision['attribution'][$field]) && is_scalar($decision['attribution'][$field])) {
                $value = sanitize_text_field(substr(trim((string)$decision['attribution'][$field]), 0, 100));
                if ($value !== '') { $attribution[$field] = $value; }
            }
        }
        $payload = array(
            'correlation_id' => $correlation_id,
            'conversation_id' => $conversation,
            'session_id' => strlen($conversation) <= 40 ? $conversation : '',
            'decision_id' => $decision_id,
            'journey' => sanitize_key((string)($request['journey'] ?? '')),
            'selected_product_id' => $product_id,
            'attribution' => $attribution,
            'issued_at' => time(),
        );
        if (!set_transient(self::TRANSIENT_PREFIX . hash('sha256', $correlation_id), $payload, self::TTL)) {
            return null;
        }
        return $correlation_id . '.' . hash_hmac('sha256', $correlation_id, wp_salt('auth'));
    }

    public static function validate($token, $product_id = 0) {
        $token = is_string($token) ? trim($token) : '';
        if (!preg_match('/^(sts2_[a-f0-9]{32})\.([a-f0-9]{64})$/', $token, $matches)) { return null; }
        $expected = hash_hmac('sha256', $matches[1], wp_salt('auth'));
        if (!hash_equals($expected, $matches[2])) { return null; }
        $payload = get_transient(self::TRANSIENT_PREFIX . hash('sha256', $matches[1]));
        if (!is_array($payload) || ($payload['correlation_id'] ?? '') !== $matches[1]) { return null; }
        if ((int)$product_id > 0) {
            $slug = sanitize_key((string)get_post_field('post_name', (int)$product_id));
            if ($slug === '' || !hash_equals((string)$payload['selected_product_id'], $slug)) { return null; }
        }
        return $payload;
    }

    public static function capture_landing_token() {
        if (empty($_GET[self::QUERY_KEY])) { return; }
        $token = sanitize_text_field(wp_unslash($_GET[self::QUERY_KEY]));
        if (!self::validate($token)) { return; }
        if (function_exists('WC') && WC()->session) { WC()->session->set(self::COOKIE_KEY, $token); }
        if (function_exists('wc_setcookie')) { wc_setcookie(self::COOKIE_KEY, $token, time() + self::TTL, is_ssl(), true); }
    }

    private static function current_token() {
        if (function_exists('WC') && WC()->session) {
            $token = WC()->session->get(self::COOKIE_KEY);
            if (is_string($token) && $token !== '') { return $token; }
        }
        return isset($_COOKIE[self::COOKIE_KEY]) ? sanitize_text_field(wp_unslash($_COOKIE[self::COOKIE_KEY])) : '';
    }

    public static function attach_cart_data($cart_item_data, $product_id, $variation_id) {
        $effective_product_id = (int)($variation_id ?: $product_id);
        $payload = self::validate(self::current_token(), $effective_product_id);
        if (!$payload && $variation_id) { $payload = self::validate(self::current_token(), (int)$product_id); }
        if ($payload) {
            $cart_item_data['_budly_commerce_correlation'] = $payload;
        }
        return $cart_item_data;
    }

    public static function attach_order_metadata($order, $data) {
        if (!function_exists('WC') || !WC()->cart) { return; }
        $matches = array();
        foreach (WC()->cart->get_cart() as $item) {
            $payload = $item['_budly_commerce_correlation'] ?? null;
            if (is_array($payload) && !empty($payload['correlation_id'])) { $matches[$payload['correlation_id']] = $payload; }
        }
        if (count($matches) !== 1) { return; }
        $payload = reset($matches);
        $order->update_meta_data('_budly_commerce_correlation_id', $payload['correlation_id']);
        $order->update_meta_data('_budly_conversation_id', $payload['conversation_id']);
        $order->update_meta_data('_budly_decision_id', $payload['decision_id']);
        if (!empty($payload['session_id'])) { $order->update_meta_data('_budly_session_id', $payload['session_id']); }
        if (WC()->session) { WC()->session->__unset(self::COOKIE_KEY); }
        if (function_exists('wc_setcookie')) { wc_setcookie(self::COOKIE_KEY, '', time() - HOUR_IN_SECONDS, is_ssl(), true); }
    }
}
