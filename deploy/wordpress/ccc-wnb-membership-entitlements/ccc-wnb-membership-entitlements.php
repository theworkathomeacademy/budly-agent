<?php
/**
 * Plugin Name: CCC Wake'n'Bake Membership Entitlements
 * Description: Derives Lounge membership access from authoritative WooCommerce acquisition and Flexible Subscriptions state.
 * Version: 0.3.1
 * Requires Plugins: woocommerce, flexible-subscriptions
 * License: GPL-2.0-or-later
 */
namespace CCC\WNB;

defined( 'ABSPATH' ) || exit;
require_once __DIR__ . '/includes/class-entitlement-rules.php';

final class Membership_Entitlements {
    private const PRODUCTS = array( 1048 => array( 'sku' => 'WNB-MBR-MEMBER', 'level' => 'member' ), 1049 => array( 'sku' => 'WNB-MBR-ELITE', 'level' => 'elite' ) );
    private const PASS_PRODUCT = array( 'product_id' => 1047, 'sku' => 'WNB-MBR-PASS', 'level' => 'pass' );
    private const PAYMENT_PLAN_PRODUCTS = array( 455, 457, 460 );
    private const META_PREFIX = '_ccc_wnb_membership_';
    private static $adjusted_prices = array();

    public static function bootstrap(): void {
        add_action( 'fsub/subscription/status/updated', array( __CLASS__, 'on_status_updated' ), 20, 3 );
        add_action( 'fsub/subscription/new', array( __CLASS__, 'on_new_subscription' ), 20, 1 );
        add_action( 'woocommerce_order_status_changed', array( __CLASS__, 'on_order_status_changed' ), 20, 4 );
        add_action( 'woocommerce_before_calculate_totals', array( __CLASS__, 'apply_cart_discount' ), 30, 1 );
        add_filter( 'user_has_cap', array( __CLASS__, 'capabilities' ), 20, 4 );
        add_filter( 'rest_pre_dispatch', array( __CLASS__, 'answer_budly_membership_question' ), 20, 3 );
        add_shortcode( 'ccc_wnb_protected', array( __CLASS__, 'protected_content' ) );
        add_shortcode( 'ccc_wnb_community', array( __CLASS__, 'render_community_hub' ) );
    }

    public static function on_status_updated( $subscription, $new_status, $previous_status ): void {
        self::sync_subscription_owner( $subscription );
    }

    public static function on_new_subscription( $subscription ): void {
        self::sync_subscription_owner( $subscription );
    }

    public static function on_order_status_changed( $order_id, $from, $to, $order ): void {
        if ( ! in_array( $to, array( 'processing', 'completed' ), true ) || ! is_object( $order ) ) {
            return;
        }
        $user_id = (int) $order->get_customer_id();
        if ( $user_id > 0 && self::order_contains_pass( $order ) ) {
            self::state( $user_id );
        }
    }

    private static function sync_subscription_owner( $subscription ): void {
        if ( ! is_object( $subscription ) || ! method_exists( $subscription, 'get_customer_id' ) ) {
            return;
        }
        $user_id = (int) $subscription->get_customer_id();
        if ( $user_id > 0 && self::is_membership_subscription( $subscription ) ) {
            self::state( $user_id );
        }
    }

    private static function is_membership_subscription( $subscription ): bool {
        if ( ! is_object( $subscription ) || ! method_exists( $subscription, 'get_type' ) || 'fsb_subscription' !== $subscription->get_type() ) {
            return false;
        }
        foreach ( $subscription->get_items( 'line_item' ) as $item ) {
            if ( self::matched_product( $item ) ) {
                return true;
            }
        }
        return false;
    }

    private static function matched_product( $item ): ?array {
        if ( ! is_object( $item ) || ! method_exists( $item, 'get_product_id' ) ) {
            return null;
        }
        $id = (int) $item->get_product_id();
        if ( ! isset( self::PRODUCTS[ $id ] ) ) {
            return null;
        }
        $product = wc_get_product( $id );
        return $product && $product->get_sku() === self::PRODUCTS[ $id ]['sku'] ? array_merge( self::PRODUCTS[ $id ], array( 'product_id' => $id ) ) : null;
    }

    /** Always recompute from the authoritative order store; metadata is a cache for downstream integrations. */
    public static function state( int $user_id ): array {
        if ( $user_id <= 0 || ! function_exists( 'wc_get_orders' ) ) {
            return Entitlement_Rules::evaluate( array(), time() );
        }
        $candidates = array();
        $orders = wc_get_orders( array( 'type' => 'fsb_subscription', 'customer_id' => $user_id, 'status' => 'any', 'limit' => -1 ) );
        foreach ( $orders as $order ) {
            if ( ! self::is_membership_subscription( $order ) || (int) $order->get_customer_id() !== $user_id ) {
                continue;
            }
            foreach ( $order->get_items( 'line_item' ) as $item ) {
                $product = self::matched_product( $item );
                if ( ! $product ) {
                    continue;
                }
                $end = method_exists( $order, 'get_current_period_end' ) ? $order->get_current_period_end() : null;
                $candidates[] = array_merge( $product, array(
                    'status' => $order->get_status(),
                    'paid_until' => $end instanceof \DateTimeInterface ? $end->getTimestamp() : 0,
                    'subscription_id' => (int) $order->get_id(),
                ) );
            }
        }
        $state = Entitlement_Rules::evaluate( $candidates, time(), self::pass_acquisition( $user_id ) );
        self::cache_state( $user_id, $state );
        return $state;
    }

    private static function pass_acquisition( int $user_id ): ?array {
        $orders = wc_get_orders( array( 'type' => 'shop_order', 'customer_id' => $user_id, 'status' => array( 'processing', 'completed' ), 'limit' => -1 ) );
        foreach ( $orders as $order ) {
            if ( self::order_contains_pass( $order ) ) {
                return array_merge( self::PASS_PRODUCT, array( 'acquired' => true, 'order_id' => (int) $order->get_id() ) );
            }
        }
        return null;
    }

    private static function order_contains_pass( $order ): bool {
        if ( ! is_object( $order ) || ! method_exists( $order, 'get_items' ) ) {
            return false;
        }
        foreach ( $order->get_items( 'line_item' ) as $item ) {
            if ( (int) $item->get_product_id() !== self::PASS_PRODUCT['product_id'] ) {
                continue;
            }
            $product = wc_get_product( self::PASS_PRODUCT['product_id'] );
            return $product && $product->get_sku() === self::PASS_PRODUCT['sku'];
        }
        return false;
    }

    public static function apply_cart_discount( $cart ): void {
        if ( is_admin() && ! wp_doing_ajax() ) {
            return;
        }
        if ( ! is_object( $cart ) || ! method_exists( $cart, 'get_cart' ) ) {
            return;
        }
        foreach ( $cart->get_cart() as $cart_key => $item ) {
            $adjustment_key = spl_object_hash( $cart ) . ':' . $cart_key;
            if ( isset( self::$adjusted_prices[ $adjustment_key ] ) && isset( $item['data'] ) && is_object( $item['data'] ) ) {
                $item['data']->set_price( self::$adjusted_prices[ $adjustment_key ] );
                unset( self::$adjusted_prices[ $adjustment_key ] );
            }
        }
        $user_id = get_current_user_id();
        if ( $user_id <= 0 || ! empty( $cart->get_applied_coupons() ) ) {
            return;
        }
        $state = self::state( $user_id );
        $percent = (int) $state['discount_percent'];
        if ( $percent <= 0 ) {
            return;
        }
        foreach ( $cart->get_cart() as $cart_key => $item ) {
            $product = $item['data'] ?? null;
            if ( ! self::discount_eligible_product( $product ) ) {
                continue;
            }
            $regular = (float) $product->get_regular_price();
            $current = (float) $product->get_price();
            if ( $regular <= 0 || $current <= 0 || abs( $current - $regular ) > 0.00001 ) {
                continue;
            }
            self::$adjusted_prices[ spl_object_hash( $cart ) . ':' . $cart_key ] = $current;
            $product->set_price( wc_format_decimal( $regular * ( 1 - $percent / 100 ), wc_get_price_decimals() ) );
        }
    }

    private static function discount_eligible_product( $product ): bool {
        if ( ! is_object( $product ) || ! method_exists( $product, 'get_id' ) || $product->is_on_sale() ) {
            return false;
        }
        $id = (int) $product->get_id();
        $parent_id = (int) $product->get_parent_id();
        $classification_id = $parent_id > 0 ? $parent_id : $id;
        if ( isset( self::PRODUCTS[ $classification_id ] ) || self::PASS_PRODUCT['product_id'] === $classification_id || in_array( $classification_id, self::PAYMENT_PLAN_PRODUCTS, true ) ) {
            return false;
        }
        return ! has_term( array( 'membership', 'bulk' ), 'product_cat', $classification_id );
    }

    private static function cache_state( int $user_id, array $state ): void {
        foreach ( array( 'level', 'status', 'subscription_id', 'product_id', 'sku', 'badge_key', 'badge_label' ) as $key ) {
            $meta_key = self::META_PREFIX . $key;
            if ( (string) get_user_meta( $user_id, $meta_key, true ) !== (string) $state[ $key ] ) {
                update_user_meta( $user_id, $meta_key, $state[ $key ] );
                update_user_meta( $user_id, self::META_PREFIX . 'transition_utc', gmdate( 'Y-m-d H:i:s' ) );
            }
        }
    }

    public static function capabilities( array $allcaps, array $caps, array $args, $user ): array {
        if ( ! isset( $args[0] ) || ! in_array( $args[0], array( 'ccc_wnb_pass_access', 'ccc_wnb_community_access', 'ccc_wnb_member_access', 'ccc_wnb_elite_access' ), true ) ) {
            return $allcaps;
        }
        $state = self::state( (int) $user->ID );
        $allcaps['ccc_wnb_pass_access'] = $state['community_access'];
        $allcaps['ccc_wnb_community_access'] = $state['community_access'];
        $allcaps['ccc_wnb_member_access'] = $state['member_access'];
        $allcaps['ccc_wnb_elite_access'] = $state['elite_access'];
        return $allcaps;
    }

    public static function protected_content( array $attributes, ?string $content = null ): string {
        $attributes = shortcode_atts( array( 'level' => 'pass' ), $attributes, 'ccc_wnb_protected' );
        $level = strtolower( (string) $attributes['level'] );
        if ( ! in_array( $level, array( 'pass', 'member', 'elite' ), true ) || ! self::can_access_level( get_current_user_id(), $level ) ) {
            return '';
        }
        return do_shortcode( (string) $content );
    }

    public static function can_access_level( int $user_id, string $level ): bool {
        $state = self::state( $user_id );
        if ( 'elite' === $level ) {
            return (bool) $state['elite_access'];
        }
        if ( 'member' === $level ) {
            return (bool) $state['member_access'];
        }
        return (bool) $state['community_access'];
    }

    public static function render_community_hub(): string {
        $user_id = (int) get_current_user_id();
        $state = self::state( $user_id );
        $level = $state['level'];

        $out = '<div class="ccc-wnb-community-hub">';
        $out .= '<div class="ccc-wnb-community-header">';
        $out .= '<h2>Wake&#8217;n&#8217;Bake Lounge Community</h2>';
        if ( ! empty( $state['badge_label'] ) && 'none' !== $level ) {
            $badge_key = function_exists( 'esc_attr' ) ? esc_attr( $state['badge_key'] ) : htmlspecialchars( $state['badge_key'], ENT_QUOTES );
            $badge_lbl = function_exists( 'esc_html' ) ? esc_html( $state['badge_label'] ) : htmlspecialchars( $state['badge_label'], ENT_QUOTES );
            $out .= '<span class="ccc-wnb-badge ccc-wnb-badge-' . $badge_key . '">' . $badge_lbl . '</span>';
        }
        $out .= '</div>';

        if ( 'none' === $level ) {
            $out .= '<div class="ccc-wnb-community-unauthorized">';
            $out .= '<p>Welcome to the Wake&#8217;n&#8217;Bake Lounge. Access to community discussions, member areas, and VIP content requires a verified membership or free Lounge Pass.</p>';
            $out .= '<p>Please log in to your account or claim your free Wake&#8217;n&#8217;Bake Lounge Pass to enter.</p>';
            $out .= '</div>';
            $out .= '</div>';
            return $out;
        }

        // 1. Pass Level (Pass, Member, Elite)
        if ( self::can_access_level( $user_id, 'pass' ) ) {
            $out .= '<div class="ccc-wnb-section ccc-wnb-section-pass">';
            $out .= '<h3>Community Lounge &amp; Announcements</h3>';
            $out .= '<p>Welcome to the Wake&#8217;n&#8217;Bake Lounge Community! Explore plant culture discussions, recipes, and educational announcements.</p>';
            $out .= '</div>';
        }

        // 2. Member Level (Member, Elite)
        if ( self::can_access_level( $user_id, 'member' ) ) {
            $out .= '<div class="ccc-wnb-section ccc-wnb-section-member">';
            $out .= '<h3>Member-Only Lounge</h3>';
            $out .= '<p>Active Member benefits unlocked: Early product drop access, priority event reservations, and 10% off eligible store items.</p>';
            $out .= '</div>';
        }

        // 3. Elite Level (Elite only)
        if ( self::can_access_level( $user_id, 'elite' ) ) {
            $out .= '<div class="ccc-wnb-section ccc-wnb-section-elite">';
            $out .= '<h3>VIP Elite Lounge</h3>';
            $out .= '<p>VIP Elite access unlocked: First product drop access, VIP event invitations, monthly curated Budly content, and 25% off eligible store items.</p>';
            $out .= '</div>';
        }

        $out .= '</div>';
        return $out;
    }

    public static function commercial_truth(): array {
        $path = __DIR__ . '/commercial-truth.json';
        if ( ! is_readable( $path ) ) {
            return array();
        }
        $truth = json_decode( (string) file_get_contents( $path ), true );
        return is_array( $truth ) ? $truth : array();
    }

    public static function answer_budly_membership_question( $result, $server, $request ) {
        if ( ! is_object( $request ) || '/budly-runtime/v1/conversation' !== $request->get_route() || 'POST' !== $request->get_method() ) {
            return $result;
        }
        $payload = $request->get_json_params();
        $message = is_array( $payload ) ? (string) ( $payload['message'] ?? '' ) : '';
        if ( preg_match( '/legends|nft|web3|unlock|torque|chemist|bliss|don|gamma|guardian|monarch|dizel|cookie|azurea|banner|godfather|strawberry/i', $message ) ) {
            return $result;
        }
        if ( ! preg_match( '/(?:wake.?n.?bake\s+)?lounge\s+(pass|member|elite)|community\s+membership/i', $message ) ) {
            return $result;
        }
        $truth = self::commercial_truth();
        if ( empty( $truth ) ) {
            return $result;
        }
        $text = "Wake'n'Bake Lounge Pass is free and includes community access. Lounge Member is $9.99 per month with community and Member access, a Member badge, early drop access, priority event access, and 10% off eligible purchases. Lounge Elite is $24.99 per month with Member benefits plus VIP community access, a VIP badge, first drop access, priority event invitations, monthly curated Budly content, and 25% off eligible purchases. Member and Elite are APPROVED / UNRELEASED and cannot be purchased yet. Discounts exclude memberships, bulk products, payment-plan classes, sale items, and transactions using coupons. LEGENDS NFT memberships are a separate family and remain unchanged.";
        return new \WP_REST_Response( array(
            'success' => true,
            'data' => array( 'response' => array( 'text' => $text, 'links' => array(), 'resulting_action' => 'continue' ) ),
        ), 200 );
    }
}

function ccc_wnb_entitlements_activate(): void {
    $slug = 'wakenbake-lounge-community';
    $title = "Wake'n'Bake Lounge Community";
    $content = '[ccc_wnb_community]';
    if ( function_exists( 'get_page_by_path' ) && function_exists( 'wp_insert_post' ) ) {
        $existing = get_page_by_path( $slug );
        if ( ! $existing ) {
            wp_insert_post( array(
                'post_title'   => $title,
                'post_name'    => $slug,
                'post_content' => $content,
                'post_status'  => 'publish',
                'post_type'    => 'page',
            ) );
        }
    }
}
if ( function_exists( 'register_activation_hook' ) ) {
    register_activation_hook( __FILE__, __NAMESPACE__ . '\\ccc_wnb_entitlements_activate' );
}

add_action( 'plugins_loaded', array( Membership_Entitlements::class, 'bootstrap' ), 20 );

/** Safe integration helpers. Pass an explicit user ID; no customer data is exposed by HTTP. */
function get_membership_state( int $user_id ): array { return Membership_Entitlements::state( $user_id ); }
function get_membership_level( int $user_id ): string { return get_membership_state( $user_id )['level']; }
function has_community_access( int $user_id ): bool { return get_membership_state( $user_id )['community_access']; }
function is_active_member( int $user_id ): bool { return get_membership_state( $user_id )['member_access']; }
function is_active_elite( int $user_id ): bool { return get_membership_state( $user_id )['elite_access']; }
function get_approved_discount_percentage( int $user_id ): int { return get_membership_state( $user_id )['discount_percent']; }
function get_membership_badge( int $user_id ): array {
    $state = get_membership_state( $user_id );
    return array( 'key' => $state['badge_key'], 'label' => $state['badge_label'] );
}
function can_access_level( int $user_id, string $level ): bool { return Membership_Entitlements::can_access_level( $user_id, $level ); }
