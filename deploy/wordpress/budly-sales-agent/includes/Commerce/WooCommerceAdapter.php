<?php
namespace Budly\Commerce;

use Budly\SecureMemory\Audit\AuditService;

if (!defined('ABSPATH')) { exit; }

final class WooCommerceAdapter {
    private $repo;
    private $audit;
    private $attribution;
    private $revenue;

    public function __construct(CommerceRepository $repo, AuditService $audit) {
        $this->repo = $repo;
        $this->audit = $audit;
        $this->attribution = new AttributionService($repo, $audit);
        $this->revenue = new RevenueService($repo);
    }

    public static function register() {
        foreach (array(
            'woocommerce_new_order' => 'order_created',
            'woocommerce_payment_complete' => 'payment_completed',
            'woocommerce_order_status_completed' => 'order_completed',
            'woocommerce_order_status_cancelled' => 'order_cancelled',
            'woocommerce_order_status_failed' => 'order_failed',
            'woocommerce_order_refunded' => 'order_refunded',
        ) as $hook => $event) {
            add_action($hook, function($order_id) use ($event) {
                self::instance()->ingest($order_id, $event);
            }, 20, 1);
        }

        // Capture incoming attribution params from URL into WC session / cookie
        add_action('init', array(__CLASS__, 'capture_attribution_params'), 10);
        // Persist captured attribution to order meta at checkout
        add_action('woocommerce_checkout_create_order', array(__CLASS__, 'attach_order_attribution'), 20, 2);
    }

    public static function capture_attribution_params() {
        $param_map = array(
            'session_id' => '_budly_session_id',
            'journey_id' => '_budly_journey_id',
            'source' => '_budly_source',
            'platform' => '_budly_platform',
            'content_id' => '_budly_content_id',
            'campaign_id' => '_budly_campaign_id',
            'cta_id' => '_budly_cta_id',
            'canonical_id' => '_budly_canonical_id',
            'catalog_version' => '_budly_catalog_version',
            'correlation_id' => 'budly_correlation',
        );
        $direct_map = array(
            'source' => 'source',
            'platform' => 'platform',
            'content_id' => 'content_id',
            'campaign_id' => 'campaign_id',
            'cta_id' => 'cta_id',
            'canonical_id' => 'canonical_id',
            'catalog_version' => 'catalog_version',
        );

        $captured = array();
        foreach ($param_map as $key => $param) {
            if (isset($_GET[$param])) {
                $val = sanitize_text_field(wp_unslash($_GET[$param]));
                if ($val !== '') {
                    $captured[$key] = $val;
                }
            } elseif (isset($direct_map[$key]) && isset($_GET[$direct_map[$key]])) {
                $val = sanitize_text_field(wp_unslash($_GET[$direct_map[$key]]));
                if ($val !== '') {
                    $captured[$key] = $val;
                }
            }
        }

        if (!empty($captured)) {
            if (function_exists('WC') && WC() && WC()->session) {
                $existing = (array) WC()->session->get('budly_attribution', array());
                WC()->session->set('budly_attribution', array_merge($existing, $captured));
            }
            if (!headers_sent()) {
                setcookie('budly_attr', wp_json_encode($captured), time() + (7 * DAY_IN_SECONDS), COOKIEPATH ? COOKIEPATH : '/', COOKIE_DOMAIN, is_ssl(), true);
            }
        }
    }

    public static function attach_order_attribution($order, $data = null) {
        $attr = array();
        if (function_exists('WC') && WC() && WC()->session) {
            $attr = (array) WC()->session->get('budly_attribution', array());
        }
        if (empty($attr) && isset($_COOKIE['budly_attr'])) {
            $decoded = json_decode(wp_unslash($_COOKIE['budly_attr']), true);
            if (is_array($decoded)) {
                $attr = $decoded;
            }
        }
        if (!empty($attr)) {
            foreach (array('session_id', 'journey_id', 'source', 'platform', 'content_id', 'campaign_id', 'cta_id', 'canonical_id', 'catalog_version') as $k) {
                if (!empty($attr[$k])) {
                    $order->update_meta_data('_budly_' . $k, sanitize_text_field((string)$attr[$k]));
                }
            }
            if (!empty($attr['correlation_id'])) {
                $order->update_meta_data('_budly_commerce_correlation_id', sanitize_text_field((string)$attr['correlation_id']));
            }
        }
    }

    public static function instance() {
        static $instance;
        if (!$instance) {
            $repo = new CommerceRepository();
            $instance = new self($repo, new AuditService(new \Budly\SecureMemory\Database\Repository()));
        }
        return $instance;
    }

    public function ingest($order_id, $event_type) {
        if (!function_exists('wc_get_order')) return array('status' => 'degraded', 'reason' => 'woocommerce_unavailable');
        $order = wc_get_order((int)$order_id);
        if (!$order) {
            $this->audit->record('commerce.event_rejected', 'system', 'woocommerce', 'failure', 'warning', array(
                'metadata' => array('order_id' => (int)$order_id, 'reason' => 'missing_order')
            ));
            return array('status' => 'rejected', 'reason' => 'missing_order');
        }

        $allowed = array('order_created', 'payment_completed', 'order_completed', 'order_cancelled', 'order_failed', 'order_refunded');
        if (!in_array($event_type, $allowed, true)) return array('status' => 'rejected', 'reason' => 'unsupported_event');

        $refund_total = '0.000000';
        if ($event_type === 'order_refunded') {
            foreach ($order->get_refunds() as $refund) {
                $refund_total = self::money((float)$refund_total + abs((float)$refund->get_total()));
            }
        }

        $revision = $event_type === 'order_refunded' ? $refund_total : (string)$order->get_status();
        $key = 'wc:' . $order->get_id() . ':' . $event_type . ':' . hash('sha256', $revision);

        if ($this->repo->event_by_key($key)) {
            $this->audit->record('commerce.event_replay', 'system', 'woocommerce', 'success', 'informational', array(
                'metadata' => array('order_id' => $order->get_id(), 'event_type' => $event_type)
            ));
            return array('status'=>'duplicate','key'=>$key);
        }

        $evidence = array(
            'correlation_id' => $order->get_meta('_budly_commerce_correlation_id', true),
            'session_id' => $order->get_meta('_budly_session_id', true),
            'conversation_id' => $order->get_meta('_budly_conversation_id', true),
            'decision_id' => $order->get_meta('_budly_decision_id', true),
            'customer_id' => $order->get_meta('_budly_customer_id', true),
            'journey_id' => $order->get_meta('_budly_journey_id', true),
            'source' => $order->get_meta('_budly_source', true),
            'platform' => $order->get_meta('_budly_platform', true),
            'content_id' => $order->get_meta('_budly_content_id', true),
            'campaign_id' => $order->get_meta('_budly_campaign_id', true),
            'cta_id' => $order->get_meta('_budly_cta_id', true),
            'canonical_id' => $order->get_meta('_budly_canonical_id', true),
            'catalog_version' => $order->get_meta('_budly_catalog_version', true),
        );

        $link = $this->attribution->resolve($order, $evidence);
        $status = (string)$order->get_status();
        $is_revenue = in_array($event_type, array('payment_completed', 'order_completed'), true)
            && in_array($status,array('processing','completed'),true)
            && !$this->repo->recorded_revenue_event($order->get_id());
        $is_refund = $event_type === 'order_refunded';
        $is_reversal = in_array($event_type, array('order_cancelled','order_failed'), true);
        $recorded = $is_reversal ? $this->repo->recorded_commercial_totals($order->get_id()) : array();

        $gross = $is_revenue ? self::money($order->get_total()) : ($is_reversal ? self::money(-max(0, (float)$recorded['gross_amount'])) : '0.000000');
        $discount = $is_revenue ? self::money($order->get_discount_total()) : ($is_reversal ? self::money(-max(0, (float)$recorded['discount_amount'])) : '0.000000');
        $shipping = $is_revenue ? self::money($order->get_shipping_total()) : ($is_reversal ? self::money(-max(0, (float)$recorded['shipping_amount'])) : '0.000000');
        $tax = $is_revenue ? self::money($order->get_total_tax()) : ($is_reversal ? self::money(-max(0, (float)$recorded['tax_amount'])) : '0.000000');
        $refund = $is_refund ? self::money(max(0, (float)$refund_total - (float)$this->repo->recorded_refund_total($order->get_id()))) : '0.000000';
        $net = $is_reversal ? self::money(-max(0, (float)$this->repo->recorded_net_total($order->get_id()))) : self::money((float)$gross - (float)$refund);
        $occurred = $order->get_date_modified() ? $order->get_date_modified()->date('Y-m-d H:i:s') : current_time('mysql', true);

        $audit = $this->audit->record(
            'commerce.event_verified',
            'system',
            'woocommerce',
            'success',
            'informational',
            array(
                'customer_reference' => (string)$order->get_customer_id(),
                'conversation_id' => (string)$evidence['conversation_id'],
                'metadata' => array('order_id' => $order->get_id(), 'event_type' => $event_type)
            )
        );

        $this->repo->insert_event(array(
            'event_uuid' => wp_generate_uuid4(),
            'external_event_key' => $key,
            'order_id' => $order->get_id(),
            'event_type' => $event_type,
            'source' => 'woocommerce',
            'verification_status' => 'verified',
            'customer_id' => $order->get_customer_id() ?: null,
            'session_id' => $evidence['session_id'] ?: null,
            'conversation_id' => $evidence['conversation_id'] ?: null,
            'decision_id' => $evidence['decision_id'] ?: null,
            'product_id' => null,
            'affiliate_id' => sanitize_text_field((string)$order->get_meta('_budly_affiliate_id', true)) ?: null,
            'currency' => strtoupper((string)$order->get_currency()),
            'gross_amount' => $gross,
            'discount_amount' => $discount,
            'shipping_amount' => $shipping,
            'tax_amount' => $tax,
            'refund_amount' => $refund,
            'net_amount' => $net,
            'attribution_status' => $link['attribution_status'],
            'reconciliation_status' => $link['resolution_state'] === 'resolved' ? 'reconciled' : 'pending',
            'evidence_json' => wp_json_encode(array_filter(array(
                'order_status' => $order->get_status(),
                'woocommerce_order_id' => $order->get_id(),
                'commerce_correlation_id' => sanitize_text_field((string)$evidence['correlation_id']),
                'journey_id' => $evidence['journey_id'] ?: null,
                'source' => $evidence['source'] ?: null,
                'platform' => $evidence['platform'] ?: null,
                'content_id' => $evidence['content_id'] ?: null,
                'campaign_id' => $evidence['campaign_id'] ?: null,
                'cta_id' => $evidence['cta_id'] ?: null,
                'canonical_id' => $evidence['canonical_id'] ?: null,
                'catalog_version' => $evidence['catalog_version'] ?: null,
            ))),
            'audit_reference' => $audit ?: 'audit_unavailable',
            'source_occurred_at' => $occurred,
            'processed_at' => current_time('mysql', true),
            'created_at' => current_time('mysql', true)
        ));

        $this->revenue->rebuild_day(substr($occurred, 0, 10));

        if ($is_revenue) {
            do_action('budly_commerce_revenue_recorded', $order, $link, $event_type, $evidence);
        }

        return array('status' => 'recorded', 'key' => $key);
    }

    private static function money($value) {
        return number_format((float)$value, 6, '.', '');
    }
}
