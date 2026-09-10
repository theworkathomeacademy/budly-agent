<?php
define('ABSPATH', __DIR__);
define('DAY_IN_SECONDS', 86400);
define('HOUR_IN_SECONDS', 3600);

$GLOBALS['sts2_transients'] = array();
$GLOBALS['sts2_posts'] = array(101 => 'wakenbake-lounge-cannabis-botanical-collection-volume-1', 102 => 'unrelated-product');
$GLOBALS['sts2_cookie'] = array();
function sanitize_text_field($value) { return preg_replace('/[\r\n\t]+/', ' ', strip_tags((string)$value)); }
function sanitize_key($value) { return preg_replace('/[^a-z0-9_\-]/', '', strtolower((string)$value)); }
function wp_unslash($value) { return $value; }
function wp_salt($scheme = 'auth') { return 'sts2-test-auth-salt'; }
function is_ssl() { return true; }
function set_transient($key, $value, $ttl) { $GLOBALS['sts2_transients'][$key] = $value; return true; }
function get_transient($key) { return $GLOBALS['sts2_transients'][$key] ?? false; }
function get_post_field($field, $id) { return $field === 'post_name' ? ($GLOBALS['sts2_posts'][$id] ?? '') : ''; }
function wc_setcookie($name, $value, $expire, $secure = false, $httponly = false) { $GLOBALS['sts2_cookie'][$name] = $value; }
function add_action() {}
function add_filter() {}

final class STS2Session {
    public $values = array();
    public function set($key, $value) { $this->values[$key] = $value; }
    public function get($key) { return $this->values[$key] ?? null; }
    public function __unset($key) { unset($this->values[$key]); }
}
final class STS2Cart {
    public $items = array();
    public function get_cart() { return $this->items; }
}
final class STS2Woo {
    public $session;
    public $cart;
    public function __construct() { $this->session = new STS2Session(); $this->cart = new STS2Cart(); }
}
$GLOBALS['sts2_woo'] = new STS2Woo();
function WC() { return $GLOBALS['sts2_woo']; }

final class STS2Order {
    public $meta = array();
    public function update_meta_data($key, $value) { $this->meta[$key] = $value; }
}

require_once dirname(__DIR__, 2) . '/deploy/wordpress/budly-sales-agent/includes/Commerce/CommerceCorrelationService.php';
use Budly\Commerce\CommerceCorrelationService;

function sts2_assert($condition, $message) {
    if (!$condition) { fwrite(STDERR, "FAIL: {$message}\n"); exit(1); }
}

$decision = array(
    'outcome' => 'recommended',
    'decision_id' => 'dec_1234567890abcdef',
    'selected_product_id' => 'wakenbake-lounge-cannabis-botanical-collection-volume-1',
    'attribution' => array('source' => 'social', 'platform' => 'instagram', 'content_id' => 'IG-STS2-001', 'campaign_id' => 'STS-2', 'cta_id' => 'CTA-ASK-BUDLY-001', 'product_or_topic' => 'BOTANICAL_COLLECTION'),
);
$request = array('conversation_id' => 'conv_1234567890abcdef', 'journey' => 'education');
$token = CommerceCorrelationService::issue($decision, $request);
sts2_assert(is_string($token) && preg_match('/^sts2_[a-f0-9]{32}\.[a-f0-9]{64}$/', $token), 'token shape');
$payload = CommerceCorrelationService::validate($token, 101);
sts2_assert(is_array($payload), 'valid token and selected product');
sts2_assert($payload['conversation_id'] === $request['conversation_id'], 'conversation association');
sts2_assert($payload['decision_id'] === $decision['decision_id'], 'decision association');
sts2_assert($payload['attribution']['campaign_id'] === 'STS-2', 'attribution retained server-side');
sts2_assert(CommerceCorrelationService::validate($token . '0', 101) === null, 'tampered token rejected');
sts2_assert(CommerceCorrelationService::validate($token, 102) === null, 'different product rejected');

WC()->session->set(CommerceCorrelationService::COOKIE_KEY, $token);
$cart = CommerceCorrelationService::attach_cart_data(array('quantity' => 1, 'line_total' => '999.99'), 101, 0);
sts2_assert(isset($cart['_budly_commerce_correlation']), 'valid correlation attached to cart');
sts2_assert($cart['quantity'] === 1 && $cart['line_total'] === '999.99', 'commercial values unchanged');
$unrelated = CommerceCorrelationService::attach_cart_data(array('quantity' => 1), 102, 0);
sts2_assert(!isset($unrelated['_budly_commerce_correlation']), 'unrelated product not attributed');

WC()->cart->items = array(array('_budly_commerce_correlation' => $cart['_budly_commerce_correlation']));
$order = new STS2Order();
CommerceCorrelationService::attach_order_metadata($order, array());
sts2_assert($order->meta['_budly_commerce_correlation_id'] === $payload['correlation_id'], 'order correlation persisted');
sts2_assert($order->meta['_budly_conversation_id'] === $payload['conversation_id'], 'order conversation persisted');
sts2_assert($order->meta['_budly_decision_id'] === $payload['decision_id'], 'order decision persisted');
sts2_assert(WC()->session->get(CommerceCorrelationService::COOKIE_KEY) === null, 'session token cleared after order linkage');

$second = $payload;
$second['correlation_id'] = 'sts2_' . str_repeat('b', 32);
WC()->cart->items[] = array('_budly_commerce_correlation' => $second);
$ambiguous = new STS2Order();
CommerceCorrelationService::attach_order_metadata($ambiguous, array());
sts2_assert($ambiguous->meta === array(), 'ambiguous multi-correlation order fails unattributed');

$not_recommended = CommerceCorrelationService::issue(array('outcome' => 'nurture'), $request);
sts2_assert($not_recommended === null, 'no correlation without authoritative recommendation');

echo "STS-2 commerce correlation runtime tests passed\n";
