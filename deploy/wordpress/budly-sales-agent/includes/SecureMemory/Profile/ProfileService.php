<?php
namespace Budly\SecureMemory\Profile;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Consent\ConsentService;
use Budly\SecureMemory\Errors;

if (!defined('ABSPATH')) { exit; }

final class ProfileService {
    const FIELDS=array('preferred_name','experience_level','communication_preferences','accessibility_preferences','educational_preferences');
    private $repo; private $consent; private $audit;
    public function __construct(ProfileRepository $repo, ConsentService $consent, AuditService $audit) { $this->repo=$repo;$this->consent=$consent;$this->audit=$audit; }
    public function read($customer_id) {
        $customer=$this->repo->customer($customer_id); if(!$customer) return null;
        $result=array('customer_id'=>$customer['public_id'],'preferred_name'=>$customer['preferred_name'],'status'=>$customer['status'],'email_verified'=>(bool)$customer['email_verified'],'updated_at'=>gmdate('c',strtotime($customer['updated_at'].' UTC')));
        foreach($this->repo->preferences($customer_id) as $row){ if(strpos($row['preference_key'],'profile.')!==0)continue; $key=substr($row['preference_key'],8); if(in_array($key,self::FIELDS,true))$result[$key]=json_decode($row['preference_json'],true); }
        return $result;
    }
    public function update($customer_id,array $input){
        if(!$this->consent->is_granted($customer_id,'memory_storage')) return array('error'=>Errors::CONSENT_REQUIRED,'status'=>403,'message'=>'Memory-storage consent is required before profile information can be saved.');
        $fields=array(); foreach($input as $key=>$value){ if(!in_array($key,self::FIELDS,true)) return array('error'=>Errors::FIELD_NOT_ALLOWED,'status'=>422,'message'=>'A profile field is not supported.'); $fields[$key]=$this->validate($key,$value); if($fields[$key]===null)return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'A profile value is invalid.'); }
        if(!$fields)return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'At least one profile field is required.');
        $now=current_time('mysql',true);$this->repo->update($customer_id,$fields,$now);$this->audit->record('profile.updated','customer',(string)$customer_id,'success','informational',array('metadata'=>array('fields'=>array_keys($fields))));
        return array('updated_fields'=>array_keys($fields),'updated_at'=>gmdate('c',strtotime($now.' UTC')));
    }
    private function validate($key,$value){
        if($key==='preferred_name'){ $v=sanitize_text_field((string)$value); return $v!==''&&mb_strlen($v)<=120?$v:null; }
        if($key==='experience_level')return in_array($value,array('beginner','intermediate','experienced'),true)?$value:null;
        if(!is_array($value)||count($value)>10)return null; $clean=array(); foreach($value as $k=>$v){$k=sanitize_key($k);if($k===''||is_array($v)||is_object($v))return null;$clean[$k]=is_bool($v)?$v:sanitize_text_field((string)$v);} return $clean;
    }
}
