<?php
namespace Budly\Commerce;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Config;
use Budly\SecureMemory\Validation;

if (!defined('ABSPATH')) { exit; }

final class AttributionService {
    private $repo;
    private $audit;

    public function __construct(CommerceRepository $repo, AuditService $audit) {
        $this->repo = $repo;
        $this->audit = $audit;
    }

    public function resolve($order, array $evidence) {
        $order_id = (int)$order->get_id();
        $session = self::clean($evidence, 'session_id', 64);
        $conversation = self::clean($evidence, 'conversation_id', 64);
        $decision = self::clean($evidence, 'decision_id', 40);
        $journey_id = self::clean($evidence, 'journey_id', 64);
        $source = self::clean($evidence, 'source', 32);
        $platform = self::clean($evidence, 'platform', 32);
        $content_id = self::clean($evidence, 'content_id', 64);
        $campaign_id = self::clean($evidence, 'campaign_id', 64);
        $cta_id = self::clean($evidence, 'cta_id', 64);
        $canonical_id = self::clean($evidence, 'canonical_id', 128);
        $catalog_version = self::clean($evidence, 'catalog_version', 32);

        $customer_id = (int)$order->get_customer_id();
        $conflict = (!empty($evidence['customer_id']) && $customer_id && $customer_id!==(int)$evidence['customer_id']);

        $has_attribution = ($session || $conversation || $decision || $journey_id || $content_id || $cta_id || $campaign_id || $source);
        $status = $conflict ? 'conflicted' : ($has_attribution ? 'attributed' : 'unattributed');

        $audit = $this->audit->record(
            'commerce.attribution',
            'system',
            'woocommerce',
            'success',
            $conflict ? 'warning' : 'informational',
            array(
                'customer_reference' => $customer_id ? (string)$customer_id : '',
                'conversation_id' => $conversation,
                'metadata' => array(
                    'order_id' => $order_id,
                    'status' => $status,
                    'journey_id' => $journey_id,
                    'cta_id' => $cta_id,
                )
            )
        );

        $now = current_time('mysql', true);
        $evidence_data = array_filter(array(
            'session_id' => $session,
            'conversation_id' => $conversation,
            'decision_id' => $decision,
            'journey_id' => $journey_id,
            'source' => $source,
            'platform' => $platform,
            'content_id' => $content_id,
            'campaign_id' => $campaign_id,
            'cta_id' => $cta_id,
            'canonical_id' => $canonical_id,
            'catalog_version' => $catalog_version,
        ));

        $row = array(
            'link_uuid' => self::uuid(),
            'order_id' => $order_id,
            'customer_id' => $customer_id ?: null,
            'session_id' => $session ?: null,
            'conversation_id' => $conversation ?: null,
            'decision_id' => $decision ?: null,
            'attribution_status' => $status,
            'attribution_method' => $status === 'attributed' ? 'verified_order_metadata' : 'none',
            'confidence' => 'deterministic',
            'evidence_json' => wp_json_encode($evidence_data),
            'evidence_observed_at' => $now,
            'rule_version' => Config::COMMERCE_CONFIG_VERSION,
            'conflict_state' => $conflict ? 'customer_mismatch' : 'none',
            'resolution_state' => $conflict ? 'review_required' : 'resolved',
            'audit_reference' => $audit ?: 'audit_unavailable',
            'created_at' => $now,
            'updated_at' => $now,
        );

        $this->repo->save_link($row);
        return $row;
    }

    private static function clean(array $v, $key, $max) {
        return isset($v[$key]) ? substr(sanitize_text_field((string)$v[$key]), 0, $max) : '';
    }

    private static function uuid() {
        return function_exists('wp_generate_uuid4')
            ? wp_generate_uuid4()
            : sprintf('%04x%04x-%04x-4%03x-%04x-%04x%04x%04x', mt_rand(0, 65535), mt_rand(0, 65535), mt_rand(0, 65535), mt_rand(0, 4095), mt_rand(0, 16383) | 0x8000, mt_rand(0, 65535), mt_rand(0, 65535), mt_rand(0, 65535));
    }
}
