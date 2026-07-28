<?php
namespace Budly\SecureMemory\Profile;
use Budly\SecureMemory\Audit\AuditService;use Budly\SecureMemory\Consent\ConsentService;use Budly\SecureMemory\Errors;use Budly\SecureMemory\Memory\MemoryPolicy;
if(!defined('ABSPATH')){exit;}
final class PreferenceService{
 const FIELDS=array('product_interests','format_preferences','shopping_preferences');private $repo;private $consent;private $audit;
 public function __construct(ProfileRepository $repo,ConsentService $consent,AuditService $audit){$this->repo=$repo;$this->consent=$consent;$this->audit=$audit;}
 public function read($customer){$out=array();foreach($this->repo->preferences($customer) as $row){if(!in_array($row['preference_key'],self::FIELDS,true))continue;$out[$row['preference_key']]=json_decode($row['preference_json'],true);}return $out;}
 public function update($customer,array $input){if(!$this->consent->is_granted($customer,'memory_storage'))return array('error'=>Errors::CONSENT_REQUIRED,'status'=>403,'message'=>'Memory-storage consent is required before preferences can be saved.');$clean=array();foreach($input as $key=>$value){if(!in_array($key,self::FIELDS,true))return array('error'=>Errors::FIELD_NOT_ALLOWED,'status'=>422,'message'=>'A preference field is not supported.');if(!is_array($value)||count($value)>20||MemoryPolicy::contains_sensitive($value))return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'A preference value is invalid or sensitive.');$clean[$key]=$value;}if(!$clean)return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'At least one preference is required.');$now=current_time('mysql',true);$this->repo->update_preferences($customer,$clean,$now);$this->audit->record('preferences.updated','customer',(string)$customer,'success','informational',array('metadata'=>array('fields'=>array_keys($clean))));return array('updated_fields'=>array_keys($clean),'updated_at'=>gmdate('c',strtotime($now.' UTC')));}
}
