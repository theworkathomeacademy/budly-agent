<?php
namespace Budly\SecureMemory\CommercialMemory;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Config;
use Budly\SecureMemory\Consent\ConsentRepository;
use Budly\SecureMemory\Consent\ConsentService;
use Budly\SecureMemory\Errors;

if (!defined('ABSPATH')) { exit; }

final class CommercialMemoryService {
    private $repo; private $consent_repo; private $consent; private $audit;
    public function __construct(CommercialMemoryRepository $repo, ConsentRepository $consent_repo, ConsentService $consent, AuditService $audit) {
        $this->repo=$repo; $this->consent_repo=$consent_repo; $this->consent=$consent; $this->audit=$audit;
    }

    public function read(array $session, array $types = array()) {
        $customer=(int)$session['customer_id'];
        if (!$this->consent->is_granted($customer,'memory_use')) { return $this->deny(Errors::CONSENT_REQUIRED,'Memory-use consent is required.',403); }
        $types=array_values(array_intersect(array_map('sanitize_key',$types),CommercialMemoryPolicy::TYPES));
        $now=current_time('mysql',true); $expired=$this->repo->expire_due($now);
        if($expired)$this->audit->record('commercial_memory.expired','system','retention_policy','success','informational',array('metadata'=>array('count'=>$expired,'policy'=>'configured_expiration')));
        $items=array_map(array($this,'present'),$this->repo->active($customer,$types,200));
        $this->audit->record('commercial_memory.read','customer',(string)$customer,'success','informational',array('metadata'=>array('count'=>count($items),'types'=>$types)));
        return array('items'=>$items,'count'=>count($items),'consent_state'=>'granted','generated_at'=>gmdate('c'));
    }

    public function create(array $session, array $input) {
        $customer=(int)$session['customer_id']; $consent=$this->consent_repo->granted_record($customer,'memory_storage');
        if (!$consent) { return $this->deny(Errors::CONSENT_REQUIRED,'Memory-storage consent is required.',403); }
        if ($this->repo->active_count($customer)>=Config::COMMERCIAL_MEMORY_MAX_ACTIVE) { return $this->deny(Errors::RESOURCE_CONFLICT,'The commercial-memory limit has been reached.',409); }
        $clean=CommercialMemoryPolicy::validate($input); if ($clean===null) { return $this->deny(Errors::INVALID_REQUEST,'The commercial-memory object is unsupported, sensitive, or invalid.',422); }
        $uuid=wp_generate_uuid4(); $now=current_time('mysql',true);
        $audit=$this->audit->record('commercial_memory.create_authorized','customer',(string)$customer,'success','informational',array('metadata'=>array('memory_uuid'=>$uuid,'type'=>$clean['memory_type'],'source'=>$clean['source_type'])));
        $record=$this->record($clean,$uuid,$customer,$consent['consent_id'],$audit,1,null,$now);
        $created=$this->repo->create($record);$this->audit->record('commercial_memory.created','customer',(string)$customer,'success','informational',array('metadata'=>array('memory_uuid'=>$uuid,'audit_reference'=>$audit)));
        return array('item'=>$this->present($created));
    }

    public function update(array $session, $uuid, array $input, $correction=false, $actor_type='customer', $actor_id=null) {
        $customer=(int)$session['customer_id']; $prior=$this->repo->find_owned($customer,$uuid);
        if (!$prior) { return $this->deny(Errors::MEMORY_NOT_FOUND,'The commercial-memory object was not found.',404); }
        $consent=$this->consent_repo->granted_record($customer,'memory_storage');
        if (!$consent) { return $this->deny(Errors::CONSENT_REQUIRED,'Memory-storage consent is required.',403); }
        if ($correction) { $input['source']='customer_correction'; $input['confidence_basis']='customer_confirmed'; }
        $clean=CommercialMemoryPolicy::validate($input); if ($clean===null) { return $this->deny(Errors::INVALID_REQUEST,'The replacement commercial-memory object is unsupported, sensitive, or invalid.',422); }
        if ($clean['memory_type']!==$prior['memory_type']) { return $this->deny(Errors::INVALID_REQUEST,'A memory correction cannot change its governed type.',422); }
        $new_uuid=wp_generate_uuid4(); $now=current_time('mysql',true); $event=$correction?'commercial_memory.corrected':'commercial_memory.updated';
        $actor_id=$actor_id===null?(string)$customer:(string)$actor_id;$audit=$this->audit->record($event.'_authorized',$actor_type,$actor_id,'success','informational',array('metadata'=>array('memory_uuid'=>$new_uuid,'supersedes_uuid'=>$uuid,'version'=>(int)$prior['version']+1)));
        $record=$this->record($clean,$new_uuid,$customer,$consent['consent_id'],$audit,(int)$prior['version']+1,$uuid,$now);
        $replacement=$this->repo->supersede($prior,$record);$this->audit->record($event,$actor_type,$actor_id,'success','informational',array('metadata'=>array('memory_uuid'=>$new_uuid,'supersedes_uuid'=>$uuid,'audit_reference'=>$audit)));
        return array('item'=>$this->present($replacement),'superseded_uuid'=>$uuid);
    }

    public function delete(array $session, $uuid, $confirmation, $actor_type='customer', $actor_id=null) {
        if ($confirmation!==true) { return $this->deny(Errors::INVALID_REQUEST,'Explicit deletion confirmation is required.',422); }
        $customer=(int)$session['customer_id']; if (!$this->repo->find_owned($customer,$uuid)) { return $this->deny(Errors::MEMORY_NOT_FOUND,'The commercial-memory object was not found.',404); }
        $actor_id=$actor_id===null?(string)$customer:(string)$actor_id;$now=current_time('mysql',true); $audit=$this->audit->record('commercial_memory.delete_authorized',$actor_type,$actor_id,'success','warning',array('metadata'=>array('memory_uuid'=>$uuid)));
        if (!$this->repo->delete_owned($customer,$uuid,$audit,$now)) { return $this->deny(Errors::MEMORY_NOT_FOUND,'The commercial-memory object was not found.',404); }
        $this->audit->record('commercial_memory.deleted',$actor_type,$actor_id,'success','warning',array('metadata'=>array('memory_uuid'=>$uuid,'audit_reference'=>$audit)));
        return array('deleted'=>true,'memory_uuid'=>$uuid,'effective_at'=>gmdate('c',strtotime($now.' UTC')));
    }

    public function export(array $session) {
        $customer=(int)$session['customer_id'];
        if (!$this->consent->is_granted($customer,'memory_use')) { return $this->deny(Errors::CONSENT_REQUIRED,'Memory-use consent is required.',403); }
        $items=array_map(array($this,'present'),$this->repo->active($customer,array(),200));
        $audit=$this->audit->record('commercial_memory.exported','customer',(string)$customer,'success','informational',array('metadata'=>array('count'=>count($items))));
        return array('export_id'=>$audit,'exported_at'=>gmdate('c'),'items'=>$items,'consent'=>$this->consent->read($customer));
    }

    public function consent(array $session, $authorize) {
        $status=$authorize?'granted':'withdrawn';
        $result=$this->consent->update((int)$session['customer_id'],array(
            'memory_storage'=>$status,'memory_use'=>$status,'consent_version'=>Config::CONSENT_VERSION,'source'=>'privacy_settings',
        ));
        if (!empty($result['error'])) { return $result; }
        $affected=$this->repo->update_consent_state((int)$session['customer_id'],$status,current_time('mysql',true));
        $this->audit->record($authorize?'commercial_memory.authorized':'commercial_memory.consent_withdrawn','customer',(string)$session['customer_id'],'success',$authorize?'informational':'warning');
        $result['commercial_memory_authorized']=$authorize;$result['memory_objects_updated']=$affected; return $result;
    }

    public function invalidate_admin($uuid, $reason) {
        $reason=sanitize_text_field($reason); if (mb_strlen($reason)<3 || mb_strlen($reason)>160) { return $this->deny(Errors::INVALID_REQUEST,'A bounded invalidation reason is required.',422); }
        $customer=(int)$this->repo->customer_for_uuid($uuid); if (!$customer) { return $this->deny(Errors::MEMORY_NOT_FOUND,'The commercial-memory object was not found.',404); }
        $now=current_time('mysql',true); $audit=$this->audit->record('commercial_memory.invalidated','administrator',(string)get_current_user_id(),'success','warning',array('metadata'=>array('memory_uuid'=>$uuid,'reason'=>$reason)));
        if (!$this->repo->invalidate($customer,$uuid,$reason,$audit,$now)) { return $this->deny(Errors::MEMORY_NOT_FOUND,'The commercial-memory object was not found.',404); }
        return array('invalidated'=>true,'memory_uuid'=>$uuid);
    }

    public function correct_admin($uuid, array $input, $reason) {
        $reason=sanitize_text_field($reason);if(mb_strlen($reason)<3||mb_strlen($reason)>160)return $this->deny(Errors::INVALID_REQUEST,'A bounded correction reason is required.',422);
        $customer=(int)$this->repo->customer_for_uuid($uuid);if(!$customer)return $this->deny(Errors::MEMORY_NOT_FOUND,'The commercial-memory object was not found.',404);
        $input['source']='administrator_correction';$input['confidence_basis']='administrator_verified';
        $result=$this->update(array('customer_id'=>$customer),$uuid,$input,false,'administrator',(string)get_current_user_id());if(!empty($result['error']))return $result;
        $this->audit->record('commercial_memory.admin_corrected','administrator',(string)get_current_user_id(),'success','warning',array('metadata'=>array('memory_uuid'=>$result['item']['uuid'],'supersedes_uuid'=>$uuid,'reason'=>$reason)));
        return $result;
    }

    public function delete_admin($uuid, $reason) {
        $reason=sanitize_text_field($reason);if(mb_strlen($reason)<3||mb_strlen($reason)>160)return $this->deny(Errors::INVALID_REQUEST,'A bounded deletion reason is required.',422);
        $customer=(int)$this->repo->customer_for_uuid($uuid);if(!$customer)return $this->deny(Errors::MEMORY_NOT_FOUND,'The commercial-memory object was not found.',404);
        $result=$this->delete(array('customer_id'=>$customer),$uuid,true,'administrator',(string)get_current_user_id());if(!empty($result['error']))return $result;
        $this->audit->record('commercial_memory.admin_deleted','administrator',(string)get_current_user_id(),'success','warning',array('metadata'=>array('memory_uuid'=>$uuid,'reason'=>$reason)));
        return $result;
    }

    public function export_admin($uuid, $reason) {
        $reason=sanitize_text_field($reason);if(mb_strlen($reason)<3||mb_strlen($reason)>160)return $this->deny(Errors::INVALID_REQUEST,'A bounded export reason is required.',422);
        $customer=(int)$this->repo->customer_for_uuid($uuid);$row=$customer?$this->repo->find_owned($customer,$uuid):null;
        if(!$row)return $this->deny(Errors::MEMORY_NOT_FOUND,'The commercial-memory object was not found.',404);
        $audit=$this->audit->record('commercial_memory.admin_exported','administrator',(string)get_current_user_id(),'success','warning',array('metadata'=>array('memory_uuid'=>$uuid,'reason'=>$reason)));
        return array('export_id'=>$audit,'exported_at'=>gmdate('c'),'item'=>$this->present($row));
    }

    public function present(array $row) {
        return array(
            'uuid'=>$row['memory_uuid'],'namespace'=>$row['namespace'],'type'=>$row['memory_type'],
            'value'=>json_decode($row['value_json'],true),'confidence'=>(float)$row['confidence'],
            'confidence_basis'=>$row['confidence_basis'],'source'=>array('type'=>$row['source_type'],'reference'=>$row['source_reference']),
            'timestamp'=>gmdate('c',strtotime($row['observed_at'].' UTC')),'consent_state'=>$row['consent_state'],
            'expiration_policy'=>$row['expiration_policy'],'expires_at'=>$row['expires_at']?gmdate('c',strtotime($row['expires_at'].' UTC')):null,
            'age_state'=>CommercialMemoryPolicy::age_state($row),'version'=>(int)$row['version'],
            'supersedes_uuid'=>$row['supersedes_uuid']?:null,'status'=>$row['status'],'audit_reference'=>$row['audit_reference'],
        );
    }

    private function record(array $clean,$uuid,$customer,$consent,$audit,$version,$supersedes,$now) {
        return array('memory_uuid'=>$uuid,'customer_id'=>$customer,'namespace'=>$clean['namespace'],'memory_type'=>$clean['memory_type'],
            'value_json'=>wp_json_encode($clean['value']),'confidence'=>$clean['confidence'],'confidence_basis'=>$clean['confidence_basis'],
            'source_type'=>$clean['source_type'],'source_reference'=>$clean['source_reference'],'observed_at'=>$clean['observed_at'],
            'consent_state'=>'granted','consent_reference'=>$consent,'expiration_policy'=>$clean['expiration_policy'],'expires_at'=>$clean['expires_at'],
            'version'=>$version,'supersedes_uuid'=>$supersedes,'status'=>'active','invalidated_reason'=>null,'audit_reference'=>$audit,
            'created_at'=>$now,'updated_at'=>$now,'deleted_at'=>null);
    }
    private function deny($code,$message,$status){return array('error'=>$code,'message'=>$message,'status'=>$status);}
}
