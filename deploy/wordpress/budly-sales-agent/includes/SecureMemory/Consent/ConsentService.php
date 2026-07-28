<?php
namespace Budly\SecureMemory\Consent;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Config;
use Budly\SecureMemory\Errors;

if (!defined('ABSPATH')) { exit; }

final class ConsentService {
    const TYPES = array('memory_storage','memory_use','marketing');
    const UPDATE_STATUSES = array('granted','denied','withdrawn');
    const SOURCES = array('privacy_settings','verification_flow','memory_prompt','customer_support');
    private $repository;
    private $audit;

    public function __construct(ConsentRepository $repository, AuditService $audit) {
        $this->repository = $repository;
        $this->audit = $audit;
    }

    public function read($customer_id) {
        $result = array();
        foreach (self::TYPES as $type) {
            $result[$type] = array('status'=>'unknown','version'=>Config::CONSENT_VERSION,'updated_at'=>null);
        }
        foreach ($this->repository->all_for_customer((int) $customer_id) as $row) {
            if (!in_array($row['consent_type'], self::TYPES, true)) { continue; }
            $result[$row['consent_type']] = array(
                'status'=>$row['status'], 'version'=>$row['consent_version'],
                'updated_at'=>gmdate('c', strtotime($row['updated_at'] . ' UTC')),
            );
        }
        return $result;
    }

    public function is_granted($customer_id, $type) {
        if (!in_array($type, self::TYPES, true)) { return false; }
        return $this->repository->status((int) $customer_id, $type) === 'granted';
    }

    public function update($customer_id, array $input) {
        $changes = array();
        foreach (self::TYPES as $type) {
            if (!array_key_exists($type, $input)) { continue; }
            $status = sanitize_key((string) $input[$type]);
            if (!in_array($status, self::UPDATE_STATUSES, true)) {
                return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'A consent status is invalid.');
            }
            $changes[$type] = $status;
        }
        if (!$changes) { return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'At least one consent choice is required.'); }
        $version = isset($input['consent_version']) ? sanitize_text_field($input['consent_version']) : '';
        if (!hash_equals(Config::CONSENT_VERSION, $version)) {
            return array('error'=>Errors::RESOURCE_CONFLICT,'status'=>409,'message'=>'The consent notice version has changed. Please review it again.');
        }
        $source = isset($input['source']) ? sanitize_key($input['source']) : '';
        if (!in_array($source, self::SOURCES, true)) {
            return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'The consent source is invalid.');
        }
        $now = current_time('mysql', true);
        $this->repository->update_many((int) $customer_id, $changes, $version, $source, $now);
        foreach ($changes as $type => $status) {
            $this->audit->record('consent.updated','customer',(string) $customer_id,'success','informational',array('customer_reference'=>(string) $customer_id,'metadata'=>array('consent_type'=>$type,'status'=>$status,'version'=>$version,'source'=>$source)));
        }
        return array('updated'=>array_keys($changes),'effective_at'=>gmdate('c', strtotime($now . ' UTC')));
    }
}
