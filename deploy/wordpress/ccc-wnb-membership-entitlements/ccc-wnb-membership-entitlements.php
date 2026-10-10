<?php
/**
 * Plugin Name: CCC Wake'n'Bake Membership Entitlements
 * Description: Derives Lounge membership access from authoritative WooCommerce acquisition and Flexible Subscriptions state.
 * Version: 0.4.0
 * Requires Plugins: woocommerce, flexible-subscriptions
 * License: GPL-2.0-or-later
 */
namespace CCC\WNB;

defined( 'ABSPATH' ) || exit;
require_once __DIR__ . '/includes/class-entitlement-rules.php';
require_once __DIR__ . '/includes/class-lounge-ui.php';

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
        add_shortcode( 'ccc_wnb_lounge', array( __CLASS__, 'render_lounge' ) );
        add_action( 'woocommerce_account_dashboard', array( __CLASS__, 'render_account_dashboard_card' ), 10 );
        add_filter( 'woocommerce_account_menu_items', array( __CLASS__, 'account_menu_items' ), 20, 1 );
        add_filter( 'woocommerce_get_endpoint_url', array( __CLASS__, 'account_endpoint_url' ), 20, 4 );
        add_action( 'woocommerce_thankyou', array( __CLASS__, 'render_order_received_welcome' ), 5, 1 );
        add_action( 'wp_enqueue_scripts', array( __CLASS__, 'enqueue_styles' ) );
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
            $out .= Lounge_UI::render( $user_id, $state );
            $out .= '</div>';
            return $out;
        }

        // 1. Pass Level (Pass, Member, Elite)
        if ( self::can_access_level( $user_id, 'pass' ) ) {
            $out .= '<div class="ccc-wnb-section ccc-wnb-section-pass">';
            $out .= '<h3>Community Lounge &amp; Announcements</h3>';
            $out .= '<p>Welcome to the Wake&#8217;n&#8217;Bake Lounge Community! Explore plant culture discussions, recipes, and educational announcements.</p>';
            $out .= Lounge_UI::render( $user_id, $state );
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

    public static function render_lounge(): string {
        $user_id = (int) get_current_user_id();
        $state = self::state( $user_id );
        return Lounge_UI::render( $user_id, $state );
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
        $text = "Wake'n'Bake Lounge Pass is free and includes community access. Lounge Member is $9.99 per month with community and Member access, a Member badge, early drop access, priority event access, and 10% off eligible purchases. Lounge Elite is $24.99 per month with Member benefits plus VIP community access, a VIP badge, first drop access, priority event invitations, monthly curated Budly content, and 25% off eligible purchases. All three tiers are currently available through the approved Wake'n'Bake / CCCultivate membership journey. Discounts exclude memberships, bulk products, payment-plan classes, sale items, and transactions using coupons. LEGENDS NFT memberships are a separate family and remain unchanged.";
        return new \WP_REST_Response( array(
            'success' => true,
            'data' => array( 'response' => array( 'text' => $text, 'links' => array(), 'resulting_action' => 'continue' ) ),
        ), 200 );
    }

    public static function render_account_dashboard_card(): void {
        $user_id = (int) get_current_user_id();
        if ( $user_id > 0 ) {
            echo self::get_account_card_html( $user_id );
        }
    }

    public static function get_account_card_html( int $user_id ): string {
        if ( $user_id <= 0 ) {
            return '';
        }
        $state = self::state( $user_id );
        $level = (string) ( $state['level'] ?? 'none' );
        $community_url = self::get_community_url();
        $budly_url = self::get_ask_budly_url();
        $sub_url = self::get_subscriptions_url();
        $pass_url = self::get_pass_product_url();

        $out = '<div class="ccc-wnb-account-card ccc-wnb-tier-' . self::esc_attr( $level ) . '">';
        $out .= '<div class="ccc-wnb-card-header">';

        if ( 'none' === $level ) {
            $out .= '<h3 class="ccc-wnb-card-title">Wake&#8217;n&#8217;Bake Lounge Membership</h3>';
            $out .= '</div>';
            $out .= '<div class="ccc-wnb-card-body">';
            $out .= '<p class="ccc-wnb-status-notice">No active Lounge membership</p>';
            $out .= '<p class="ccc-wnb-card-description">Join the Wake&#8217;n&#8217;Bake Lounge to unlock community discussions, events, exclusive drops, and store discounts.</p>';
            $out .= '</div>';
            $out .= '<div class="ccc-wnb-card-actions">';
            $out .= '<a href="' . self::esc_url( $pass_url ) . '" class="ccc-wnb-btn ccc-wnb-btn-primary">Claim Free Lounge Pass</a>';
            $out .= '<a href="' . self::esc_url( $budly_url ) . '" class="ccc-wnb-budly-link" target="_blank" rel="noopener">Ask Budly</a>';
            $out .= '</div>';
        } else {
            $badge_key = self::esc_attr( (string) ( $state['badge_key'] ?? 'none' ) );
            $badge_lbl = self::esc_html( (string) ( $state['badge_label'] ?? '' ) );
            $out .= '<h3 class="ccc-wnb-card-title">' . $badge_lbl . '</h3>';
            $out .= '<span class="ccc-wnb-badge ccc-wnb-badge-' . $badge_key . '">' . $badge_lbl . '</span>';
            $out .= '</div>';

            $out .= '<div class="ccc-wnb-card-body">';
            $out .= '<div class="ccc-wnb-discount-info"><strong>Discount:</strong> ' . ( 'pass' === $level ? '0%' : ( 'member' === $level ? '10% eligible discount' : '25% eligible discount' ) ) . '</div>';

            $out .= '<div class="ccc-wnb-benefits-section">';
            $out .= '<h4>Your Benefits</h4>';
            $out .= '<ul class="ccc-wnb-benefits-list">';
            if ( 'pass' === $level ) {
                $out .= '<li>Community access</li>';
            } elseif ( 'member' === $level ) {
                $out .= '<li>Community access</li>';
                $out .= '<li>10% eligible discount</li>';
                $out .= '<li>early drop access</li>';
                $out .= '<li>member sections</li>';
                $out .= '<li>priority event access</li>';
            } elseif ( 'elite' === $level ) {
                $out .= '<li>Community access</li>';
                $out .= '<li>25% eligible discount</li>';
                $out .= '<li>first-drop access</li>';
                $out .= '<li>VIP community access</li>';
                $out .= '<li>priority event invitations</li>';
                $out .= '<li>monthly curated Budly content</li>';
            }
            $out .= '</ul>';
            $out .= '</div>';
            $out .= '</div>';

            $out .= '<div class="ccc-wnb-card-actions">';
            $out .= '<a href="' . self::esc_url( $community_url ) . '" class="ccc-wnb-btn ccc-wnb-btn-primary">Enter the Lounge &rarr;</a>';
            if ( in_array( $level, array( 'member', 'elite' ), true ) ) {
                $out .= '<a href="' . self::esc_url( $sub_url ) . '" class="ccc-wnb-btn ccc-wnb-btn-secondary ccc-wnb-sub-link">Manage Subscription</a>';
            }
            $out .= '<a href="' . self::esc_url( $budly_url ) . '" class="ccc-wnb-budly-link" target="_blank" rel="noopener">Ask Budly</a>';
            $out .= '</div>';
        }

        $out .= '</div>';
        return $out;
    }

    public static function account_menu_items( array $items ): array {
        $new_items = array();
        foreach ( $items as $key => $label ) {
            $new_items[ $key ] = $label;
            if ( 'dashboard' === $key ) {
                $new_items['wakenbake-lounge-community'] = 'Lounge Community';
            }
        }
        if ( ! isset( $new_items['wakenbake-lounge-community'] ) ) {
            $new_items['wakenbake-lounge-community'] = 'Lounge Community';
        }
        return $new_items;
    }

    public static function account_endpoint_url( string $url, string $endpoint, string $value, string $permalink ): string {
        if ( 'wakenbake-lounge-community' === $endpoint ) {
            return self::get_community_url();
        }
        return $url;
    }

    public static function render_order_received_welcome( $order_id ): void {
        echo self::get_order_received_welcome_html( $order_id );
    }

    public static function get_order_received_welcome_html( $order_id ): string {
        $order = is_object( $order_id ) ? $order_id : ( function_exists( 'wc_get_order' ) ? wc_get_order( (int) $order_id ) : null );
        if ( ! is_object( $order ) || ! method_exists( $order, 'get_items' ) ) {
            return '';
        }
        $tier = null;
        $badge_label = '';
        $badge_key = '';
        foreach ( $order->get_items( 'line_item' ) as $item ) {
            $pid = method_exists( $item, 'get_product_id' ) ? (int) $item->get_product_id() : 0;
            if ( 1049 === $pid ) {
                $tier = 'elite';
                $badge_label = "Wake'n'Bake Lounge Elite";
                $badge_key = 'wnb_elite';
                break;
            } elseif ( 1048 === $pid && 'elite' !== $tier ) {
                $tier = 'member';
                $badge_label = "Wake'n'Bake Lounge Member";
                $badge_key = 'wnb_member';
            } elseif ( 1047 === $pid && null === $tier ) {
                $tier = 'pass';
                $badge_label = "Wake'n'Bake Lounge Pass";
                $badge_key = 'wnb_pass';
            }
        }
        if ( null === $tier ) {
            return '';
        }
        return self::render_welcome_box( $tier, $badge_label, $badge_key );
    }

    private static function render_welcome_box( string $tier, string $badge_label, string $badge_key ): string {
        $community_url = self::get_community_url();
        $budly_url = self::get_ask_budly_url();
        $badge_esc = self::esc_html( $badge_label );
        $badge_key_esc = self::esc_attr( $badge_key );

        $msg = '';
        if ( 'elite' === $tier ) {
            $msg = 'Your Wake&#8217;n&#8217;Bake Lounge Elite VIP subscription is active. Enjoy VIP community sections, 25% eligible store discounts, first access to drops, priority event invitations, and monthly curated Budly content.';
        } elseif ( 'member' === $tier ) {
            $msg = 'Your Wake&#8217;n&#8217;Bake Lounge Member subscription is active. Enjoy exclusive member sections, 10% eligible store discounts, early access to new drops, and priority event access.';
        } else {
            $msg = 'Your free Wake&#8217;n&#8217;Bake Lounge Community Pass is active. Enjoy community access, discussions, recipes, and educational announcements.';
        }

        $out = '<div class="ccc-wnb-welcome-card ccc-wnb-welcome-' . $badge_key_esc . '">';
        $out .= '<div class="ccc-wnb-card-header">';
        $out .= '<h3>Welcome to the Wake&#8217;n&#8217;Bake Lounge!</h3>';
        $out .= '<span class="ccc-wnb-badge ccc-wnb-badge-' . $badge_key_esc . '">' . $badge_esc . '</span>';
        $out .= '</div>';
        $out .= '<p>' . $msg . '</p>';
        $out .= '<div class="ccc-wnb-card-actions">';
        $out .= '<a href="' . self::esc_url( $community_url ) . '" class="ccc-wnb-btn ccc-wnb-btn-primary">Enter the Lounge &rarr;</a>';
        $out .= '<a href="' . self::esc_url( $budly_url ) . '" class="ccc-wnb-budly-link" target="_blank" rel="noopener">Ask Budly</a>';
        $out .= '</div>';
        $out .= '</div>';
        return $out;
    }

    public static function get_community_url(): string {
        return function_exists( 'home_url' ) ? home_url( '/wakenbake-lounge-community/' ) : 'https://cccultivate.com/wakenbake-lounge-community/';
    }

    public static function get_pass_product_url(): string {
        return function_exists( 'home_url' ) ? home_url( '/product/lounge-pass/' ) : 'https://cccultivate.com/product/lounge-pass/';
    }

    public static function get_subscriptions_url(): string {
        if ( function_exists( 'wc_get_endpoint_url' ) && function_exists( 'wc_get_page_permalink' ) ) {
            return wc_get_endpoint_url( 'subscriptions', '', wc_get_page_permalink( 'myaccount' ) );
        }
        return function_exists( 'home_url' ) ? home_url( '/my-account/subscriptions/' ) : 'https://cccultivate.com/my-account/subscriptions/';
    }

    public static function get_ask_budly_url(): string {
        return function_exists( 'home_url' ) ? home_url( '/ask-budly/' ) : 'https://cccultivate.com/ask-budly/';
    }

    public static function enqueue_styles(): void {
        if ( function_exists( 'is_account_page' ) && ( is_account_page() || ( function_exists( 'is_order_received_page' ) && is_order_received_page() ) || ( function_exists( 'is_page' ) && is_page( 'wakenbake-lounge-community' ) ) ) ) {
            wp_register_style( 'ccc-wnb-membership-styles', false );
            wp_enqueue_style( 'ccc-wnb-membership-styles' );
            wp_add_inline_style( 'ccc-wnb-membership-styles', self::get_membership_css() );
        }
    }

    public static function get_membership_css(): string {
        return '
.ccc-wnb-account-card { border: 1px solid #dcdad2; border-radius: 8px; background: #ffffff; padding: 24px; margin: 20px 0 30px; box-sizing: border-box; box-shadow: 0 2px 6px rgba(0,0,0,0.04); }
.ccc-wnb-card-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid #f0eee6; }
.ccc-wnb-card-title { margin: 0; font-size: 1.35rem; font-weight: 700; color: #1a1a1a; }
.ccc-wnb-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.ccc-wnb-badge-wnb_pass { background: #eef1f4; color: #495057; border: 1px solid #ced4da; }
.ccc-wnb-badge-wnb_member { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; }
.ccc-wnb-badge-wnb_elite { background: #fff8e1; color: #b78103; border: 1px solid #ffe082; }
.ccc-wnb-status-notice { font-size: 1.05rem; font-weight: 600; color: #555555; margin: 0 0 8px; }
.ccc-wnb-card-description { color: #666666; margin: 0 0 16px; line-height: 1.5; }
.ccc-wnb-discount-info { margin: 0 0 16px; font-size: 0.95rem; color: #2b2b2b; }
.ccc-wnb-discount-info strong { color: #1a1a1a; }
.ccc-wnb-benefits-section { margin: 0 0 20px; }
.ccc-wnb-benefits-section h4 { margin: 0 0 10px; font-size: 1rem; font-weight: 600; color: #333333; }
.ccc-wnb-benefits-list { list-style: none; padding: 0; margin: 0; }
.ccc-wnb-benefits-list li { position: relative; padding-left: 22px; margin-bottom: 8px; font-size: 0.95rem; color: #444444; line-height: 1.4; }
.ccc-wnb-benefits-list li::before { content: "✓"; position: absolute; left: 0; top: 0; color: #2e7d32; font-weight: 700; }
.ccc-wnb-card-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; padding-top: 14px; border-top: 1px solid #f0eee6; }
.ccc-wnb-btn { display: inline-block; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 0.95rem; text-decoration: none; text-align: center; cursor: pointer; transition: background-color 0.2s, color 0.2s; box-sizing: border-box; }
.ccc-wnb-btn-primary { background: #2d5a27; color: #ffffff !important; border: 1px solid #2d5a27; }
.ccc-wnb-btn-primary:hover { background: #23471f; }
.ccc-wnb-btn-secondary { background: #f8f9fa; color: #333333 !important; border: 1px solid #ced4da; }
.ccc-wnb-btn-secondary:hover { background: #e9ecef; }
.ccc-wnb-budly-link { margin-left: auto; font-size: 0.9rem; color: #2d5a27; text-decoration: underline; font-weight: 600; }
.ccc-wnb-budly-link:hover { color: #1b3817; }
.ccc-wnb-welcome-card { border: 2px solid #2d5a27; border-radius: 8px; background: #f7faf7; padding: 24px; margin: 20px 0 30px; box-sizing: border-box; }
.ccc-wnb-welcome-card h3 { margin-top: 0; margin-bottom: 12px; color: #2d5a27; font-size: 1.35rem; }
.ccc-wnb-welcome-card p { font-size: 1rem; line-height: 1.5; color: #333333; margin: 0 0 18px; }
@media (max-width: 820px) { .ccc-wnb-account-card, .ccc-wnb-welcome-card { padding: 20px; } }
@media (max-width: 480px) {
    .ccc-wnb-account-card, .ccc-wnb-welcome-card { padding: 16px; }
    .ccc-wnb-card-header { flex-direction: column; align-items: flex-start; }
    .ccc-wnb-card-actions { flex-direction: column; align-items: stretch; }
    .ccc-wnb-btn { width: 100%; margin-bottom: 6px; }
    .ccc-wnb-budly-link { margin-left: 0; text-align: center; padding-top: 6px; }
}' . Lounge_UI::get_css();
    }

    private static function esc_attr( string $text ): string {
        return function_exists( 'esc_attr' ) ? esc_attr( $text ) : htmlspecialchars( $text, ENT_QUOTES );
    }

    private static function esc_html( string $text ): string {
        return function_exists( 'esc_html' ) ? esc_html( $text ) : htmlspecialchars( $text, ENT_QUOTES );
    }

    private static function esc_url( string $url ): string {
        return function_exists( 'esc_url' ) ? esc_url( $url ) : htmlspecialchars( $url, ENT_QUOTES );
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
function get_account_dashboard_card( int $user_id ): string { return Membership_Entitlements::get_account_card_html( $user_id ); }
function get_post_order_welcome( $order_id ): string { return Membership_Entitlements::get_order_received_welcome_html( $order_id ); }

