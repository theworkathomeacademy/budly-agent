<?php
define( 'ABSPATH', __DIR__ );
$hooks = array(); $meta = array(); $orders = array(); $products = array();
function add_action( $name, $callback, $priority = 10, $args = 1 ) { global $hooks; $hooks[ $name ] = array( $callback, $args ); }
function add_filter( $name, $callback, $priority = 10, $args = 1 ) { global $hooks; $hooks[ $name ] = array( $callback, $args ); }
function wc_get_orders( $query ) { global $orders; return array_values( array_filter( $orders, function( $order ) use ( $query ) { return $order->get_customer_id() === $query['customer_id'] && $order->get_type() === $query['type']; } ) ); }
function wc_get_product( $id ) { global $products; return $products[ $id ] ?? null; }
function get_user_meta( $id, $key, $single ) { global $meta; return $meta[ $id ][ $key ] ?? ''; }
function update_user_meta( $id, $key, $value ) { global $meta; $meta[ $id ][ $key ] = $value; }
class Product { private $sku; function __construct( $sku ) { $this->sku = $sku; } function get_sku() { return $this->sku; } }
class Item { private $id; function __construct( $id ) { $this->id = $id; } function get_product_id() { return $this->id; } }
class Subscription {
    public $status; public $until; private $customer; private $product; private $id;
    function __construct( $id, $customer, $product, $status, $until = null ) { $this->id = $id; $this->customer = $customer; $this->product = $product; $this->status = $status; $this->until = $until; }
    function get_id() { return $this->id; } function get_customer_id() { return $this->customer; }
    function get_type() { return 'fsb_subscription'; } function get_status() { return $this->status; }
    function get_items( $kind ) { return array( new Item( $this->product ) ); }
    function get_current_period_end() { return $this->until; }
}
require_once __DIR__ . '/../../deploy/wordpress/ccc-wnb-membership-entitlements/ccc-wnb-membership-entitlements.php';
function verify( $truth, $message ) { if ( ! $truth ) throw new RuntimeException( $message ); }
$hooks['plugins_loaded'][0]();
verify( isset( $hooks['fsub/subscription/status/updated'], $hooks['fsub/subscription/new'], $hooks['user_has_cap'] ), 'Expected hooks' );
verify( ! isset( $hooks['woocommerce_before_calculate_totals'] ), 'Discount activation must be absent' );
$products = array( 1048 => new Product( 'WNB-MBR-MEMBER' ), 1049 => new Product( 'WNB-MBR-ELITE' ), 42 => new Product( 'OTHER' ) );
$orders = array( new Subscription( 1, 7, 1048, 'active' ), new Subscription( 2, 7, 1049, 'active' ), new Subscription( 3, 8, 42, 'active' ) );
verify( 'elite' === CCC\WNB\get_membership_level( 7 ), 'Elite precedence' );
verify( 'none' === CCC\WNB\get_membership_level( 8 ), 'Other product excluded' );
verify( 'none' === CCC\WNB\get_membership_level( 9 ), 'Other customer excluded' );
verify( CCC\WNB\is_active_member( 7 ) && CCC\WNB\is_active_elite( 7 ), 'Hierarchy' );
verify( 25 === CCC\WNB\get_approved_discount_percentage( 7 ), 'Approved percentage' );
$orders[1]->status = 'on-hold';
verify( 'member' === CCC\WNB\get_membership_level( 7 ), 'Fallback to active Member' );
$orders[0]->status = 'cancelled';
verify( 'none' === CCC\WNB\get_membership_level( 7 ), 'Suspension and cancellation' );
$orders[1]->status = 'active';
$hooks['fsub/subscription/status/updated'][0]( $orders[1], 'active', 'on-hold' );
verify( 'elite' === $meta[7]['_ccc_wnb_membership_level'], 'Reactivation cache' );
$products[1049] = new Product( 'WRONG-SKU' );
verify( 'none' === CCC\WNB\get_membership_level( 7 ), 'ID plus SKU fail closed' );
echo "10 integration checks passed\n";
