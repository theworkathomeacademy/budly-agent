<?php
namespace Budly\SecureMemory\Audit;

use Budly\SecureMemory\Database\Repository;
use Budly\SecureMemory\Validation;

if (!defined('ABSPATH')) { exit; }

final class AuditService {
    private $repository;

    public function __construct(Repository $repository) { $this->repository = $repository; }

    public function record($event_type, $actor_type, $actor_id, $result, $severity = 'informational', array $context = array()) {
        $safe_metadata = self::scrub(isset($context['metadata']) && is_array($context['metadata']) ? $context['metadata'] : array());
        return $this->repository->insert('audit', array(
            'audit_id' => Validation::opaque_id('aud'),
            'event_type' => self::event_type($event_type),
            'actor_type' => sanitize_key($actor_type),
            'actor_id' => sanitize_text_field($actor_id),
            'customer_reference' => sanitize_text_field(isset($context['customer_reference']) ? $context['customer_reference'] : ''),
            'conversation_id' => sanitize_text_field(isset($context['conversation_id']) ? $context['conversation_id'] : ''),
            'result' => sanitize_key($result),
            'severity' => sanitize_key($severity),
            'metadata_json' => wp_json_encode($safe_metadata),
            'created_at' => current_time('mysql', true),
        ));
    }
    private static function event_type($value) {
        return substr(preg_replace('/[^a-z0-9._-]/', '', strtolower((string) $value)), 0, 80);
    }
    private static function scrub(array $metadata){$safe=array();foreach($metadata as $key=>$value){$normalized=sanitize_key((string)$key);if(preg_match('/(?:code|token|password|secret|key|authorization|cookie)/i',$normalized))continue;if(is_array($value)){$safe[$normalized]=self::scrub($value);}elseif(is_scalar($value)||$value===null){$text=$value===null?null:sanitize_text_field((string)$value);$safe[$normalized]=is_string($text)&&strlen($text)>500?substr($text,0,500):$text;}}return$safe;}
}
