<?php
define( 'ABSPATH', __DIR__ );
$hooks = array(); $meta = array(); $orders = array(); $products = array(); $shortcodes = array(); $current_user_id = 7; $posts = array();
function add_action( $name, $callback, $priority = 10, $args = 1 ) { global $hooks; $hooks[ $name ] = array( $callback, $args ); }
function add_filter( $name, $callback, $priority = 10, $args = 1 ) { global $hooks; $hooks[ $name ] = array( $callback, $args ); }
function add_shortcode( $name, $callback ) { global $shortcodes; $shortcodes[ $name ] = $callback; }
function shortcode_atts( $defaults, $attributes, $tag ) { return array_merge( $defaults, $attributes ); }
function do_shortcode( $content ) { return $content; }
function wp_json_encode( $value ) { return json_encode( $value ); }
function esc_attr( $text ) { return htmlspecialchars( (string) $text, ENT_QUOTES ); }
function esc_html( $text ) { return htmlspecialchars( (string) $text, ENT_QUOTES ); }
function register_activation_hook( $file, $callback ) { global $hooks; $hooks['activation'] = $callback; }
function get_page_by_path( $slug ) { global $posts; return $posts[ $slug ] ?? null; }
function wp_insert_post( $postarr ) { global $posts; $posts[ $postarr['post_name'] ] = $postarr; return count( $posts ); }
class WP_REST_Response { public $data; public $status; function __construct( $data, $status ) { $this->data=$data; $this->status=$status; } }
class Request { private $route; private $method; private $params; function __construct($route,$method,$params){$this->route=$route;$this->method=$method;$this->params=$params;} function get_route(){return $this->route;} function get_method(){return $this->method;} function get_json_params(){return $this->params;} }
function wc_get_orders( $query ) { global $orders; return array_values( array_filter( $orders, function( $order ) use ( $query ) { return $order->get_customer_id() === $query['customer_id'] && $order->get_type() === $query['type'] && ( 'any' === $query['status'] || in_array( $order->get_status(), (array) $query['status'], true ) ); } ) ); }
function wc_get_product( $id ) { global $products; return $products[ $id ] ?? null; }
function get_user_meta( $id, $key, $single ) { global $meta; return $meta[ $id ][ $key ] ?? ''; }
function update_user_meta( $id, $key, $value ) { global $meta; $meta[ $id ][ $key ] = $value; }
function is_admin() { return false; } function wp_doing_ajax() { return false; } function get_current_user_id() { global $current_user_id; return $current_user_id; }
function wc_format_decimal( $value, $decimals ) { return round( $value, $decimals ); } function wc_get_price_decimals() { return 2; }
function has_term( $terms, $taxonomy, $id ) { global $products; return count( array_intersect( $terms, $products[$id]->terms ?? array() ) ) > 0; }
class Product { private $id; private $sku; private $regular; private $price; private $sale; public $terms;
    function __construct( $id, $sku, $regular = 100, $price = 100, $sale = false, $terms = array() ) { $this->id=$id; $this->sku=$sku; $this->regular=$regular; $this->price=$price; $this->sale=$sale; $this->terms=$terms; }
    function get_id(){return $this->id;} function get_parent_id(){return 0;} function get_sku(){return $this->sku;} function get_regular_price(){return $this->regular;} function get_price(){return $this->price;} function set_price($p){$this->price=$p;} function is_on_sale(){return $this->sale;}
}
class Item { private $id; function __construct( $id ) { $this->id = $id; } function get_product_id() { return $this->id; } }
class Subscription {
    public $status; public $until; private $customer; private $product; private $id;
    function __construct( $id, $customer, $product, $status, $until = null ) { $this->id = $id; $this->customer = $customer; $this->product = $product; $this->status = $status; $this->until = $until; }
    function get_id() { return $this->id; } function get_customer_id() { return $this->customer; }
    function get_type() { return 'fsb_subscription'; } function get_status() { return $this->status; }
    function get_items( $kind ) { return array( new Item( $this->product ) ); }
    function get_current_period_end() { return $this->until; }
}
class Order extends Subscription { function get_type(){return 'shop_order';} }
class Cart { public $items; public $coupons; function __construct($items,$coupons=array()){$this->items=$items;$this->coupons=$coupons;} function get_cart(){return $this->items;} function get_applied_coupons(){return $this->coupons;} }
require_once __DIR__ . '/../../deploy/wordpress/ccc-wnb-membership-entitlements/ccc-wnb-membership-entitlements.php';
function verify( $truth, $message ) { if ( ! $truth ) throw new RuntimeException( $message ); }
$hooks['plugins_loaded'][0]();
verify( isset( $hooks['fsub/subscription/status/updated'], $hooks['fsub/subscription/new'], $hooks['woocommerce_order_status_changed'], $hooks['woocommerce_before_calculate_totals'], $hooks['user_has_cap'], $hooks['rest_pre_dispatch'], $shortcodes['ccc_wnb_protected'] ), 'Expected hooks and shortcode' );
$products = array( 1047 => new Product(1047,'WNB-MBR-PASS',0,0), 1048 => new Product(1048,'WNB-MBR-MEMBER'), 1049 => new Product(1049,'WNB-MBR-ELITE'), 42 => new Product(42,'OTHER'), 50 => new Product(50,'BULK',100,100,false,array('bulk')), 455 => new Product(455,'PLAN'), 150 => new Product(150,'COURSE'), 60 => new Product(60,'SALE',100,80,true) );
$orders = array( new Subscription( 1, 7, 1048, 'active' ), new Subscription( 2, 7, 1049, 'active' ), new Subscription( 3, 8, 42, 'active' ), new Order(4,9,1047,'completed') );
verify( 'elite' === CCC\WNB\get_membership_level( 7 ), 'Elite precedence' );
verify( 'none' === CCC\WNB\get_membership_level( 8 ), 'Other product excluded' );
verify( 'pass' === CCC\WNB\get_membership_level( 9 ), 'Pass acquisition' );
verify( 'pass' === CCC\WNB\get_membership_level( 9 ), 'Pass persists on reconciliation' );
verify( 'none' === CCC\WNB\get_membership_level( 10 ), 'Account alone does not grant Pass' );
verify( 'wnb_elite' === CCC\WNB\get_membership_badge( 7 )['key'], 'Elite badge state' );
verify( CCC\WNB\is_active_member( 7 ) && CCC\WNB\is_active_elite( 7 ), 'Hierarchy' );
verify( CCC\WNB\can_access_level( 7, 'pass' ) && CCC\WNB\can_access_level( 7, 'member' ) && CCC\WNB\can_access_level( 7, 'elite' ), 'Elite capability hierarchy' );
$current_user_id = 9;
verify( 'pass content' === $shortcodes['ccc_wnb_protected']( array( 'level' => 'pass' ), 'pass content' ), 'Pass protected content' );
verify( '' === $shortcodes['ccc_wnb_protected']( array( 'level' => 'member' ), 'member content' ), 'Pass cannot access Member content' );
$current_user_id = 7;
verify( 25 === CCC\WNB\get_approved_discount_percentage( 7 ), 'Approved percentage' );
$orders[1]->status = 'on-hold';
verify( 'member' === CCC\WNB\get_membership_level( 7 ), 'Fallback to active Member' );
$orders[0]->status = 'cancelled';
verify( 'none' === CCC\WNB\get_membership_level( 7 ), 'Suspension and cancellation' );
$orders[1]->status = 'active';
$hooks['fsub/subscription/status/updated'][0]( $orders[1], 'active', 'on-hold' );
verify( 'elite' === $meta[7]['_ccc_wnb_membership_level'], 'Reactivation cache' );
$products[1049] = new Product(1049,'WRONG-SKU');
verify( 'none' === CCC\WNB\get_membership_level( 7 ), 'ID plus SKU fail closed' );
$products[1049] = new Product(1049,'WNB-MBR-ELITE'); $orders[1]->status='active';
$cart = new Cart(array(array('data'=>$products[42]),array('data'=>$products[50]),array('data'=>$products[455]),array('data'=>$products[150]),array('data'=>$products[60]),array('data'=>$products[1048])));
$hooks['woocommerce_before_calculate_totals'][0]($cart);
verify( 75.0 === $products[42]->get_price() && 75.0 === $products[150]->get_price(), 'Eligible retail and full course receive Elite discount' );
verify( 100.0 === (float) $products[50]->get_price() && 100.0 === (float) $products[455]->get_price() && 80.0 === (float) $products[60]->get_price() && 100.0 === (float) $products[1048]->get_price(), 'Excluded products unaffected' );
$cart->coupons = array('fam33');
$hooks['woocommerce_before_calculate_totals'][0]($cart);
verify( 100.0 === $products[42]->get_price() && 100.0 === $products[150]->get_price(), 'Later coupon restores membership-adjusted prices before coupon calculation' );
$plain = new Product(70,'PLAIN'); $coupon_cart = new Cart(array(array('data'=>$plain)),array('fam33')); $hooks['woocommerce_before_calculate_totals'][0]($coupon_cart);
verify( 100.0 === (float) $plain->get_price(), 'Coupon blocks membership discount' );
$request = new Request('/budly-runtime/v1/conversation','POST',array('message'=>"Can I buy the Wake'n'Bake Lounge Elite membership?"));
$response = $hooks['rest_pre_dispatch'][0]( null, null, $request );
verify( $response instanceof WP_REST_Response && 200 === $response->status, 'Budly receives governed membership answer' );
verify( false !== strpos( $response->data['data']['response']['text'], 'APPROVED / UNRELEASED' ) && false !== strpos( $response->data['data']['response']['text'], 'cannot be purchased yet' ), 'Budly answer blocks public availability claim' );
$legends = new Request('/budly-runtime/v1/conversation','POST',array('message'=>'Tell me about Torque and LEGENDS NFTs.'));
verify( null === $hooks['rest_pre_dispatch'][0]( null, null, $legends ), 'LEGENDS-only request remains untouched' );
$wnb_torque = new Request('/budly-runtime/v1/conversation','POST',array('message'=>"What are the Wake'n'Bake Torque NFT tiers?"));
verify( null === $hooks['rest_pre_dispatch'][0]( null, null, $wnb_torque ), "Wake'n'Bake Torque NFT bypasses Lounge Pass interceptor" );
$gamma = new Request('/budly-runtime/v1/conversation','POST',array('message'=>'Tell me about Gamma Blaze Bronze tier.'));
verify( null === $hooks['rest_pre_dispatch'][0]( null, null, $gamma ), 'Character tier bypasses Lounge Pass interceptor' );
verify( isset( $hooks['activation'] ), 'Activation hook registered' );
$hooks['activation']();
verify( isset( $posts['wakenbake-lounge-community'] ), 'Activation provisions community page' );
$current_user_id = 10;
$community_non = $shortcodes['ccc_wnb_community']();
verify( false !== strpos( $community_non, 'ccc-wnb-community-unauthorized' ) && false === strpos( $community_non, 'ccc-wnb-section-pass' ), 'Unauthorized user sees login/claim card' );
$current_user_id = 9;
$community_pass = $shortcodes['ccc_wnb_community']();
verify( false !== strpos( $community_pass, 'ccc-wnb-section-pass' ) && false === strpos( $community_pass, 'ccc-wnb-section-member' ) && false === strpos( $community_pass, 'ccc-wnb-section-elite' ), 'Pass user sees pass section only' );
$orders[1]->status = 'cancelled';
$orders[0]->status = 'active';
$current_user_id = 7;
$community_member = $shortcodes['ccc_wnb_community']();
verify( false !== strpos( $community_member, 'ccc-wnb-section-pass' ) && false !== strpos( $community_member, 'ccc-wnb-section-member' ) && false === strpos( $community_member, 'ccc-wnb-section-elite' ), 'Member user sees pass and member sections' );
$orders[1]->status = 'active';
$community_elite = $shortcodes['ccc_wnb_community']();
verify( false !== strpos( $community_elite, 'ccc-wnb-section-pass' ) && false !== strpos( $community_elite, 'ccc-wnb-section-member' ) && false !== strpos( $community_elite, 'ccc-wnb-section-elite' ) && false !== strpos( $community_elite, 'ccc-wnb-badge-wnb_elite' ), 'Elite user sees all sections with VIP badge' );
echo "32 integration checks passed\n";

