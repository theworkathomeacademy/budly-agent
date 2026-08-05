<?php
namespace Budly\SecureMemory\CommercialMemory;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Config;
use Budly\SecureMemory\Consent\ConsentRepository;
use Budly\SecureMemory\Errors;

if (!defined('ABSPATH')) { exit; }

final class ConversationContextService {
    private $repo; private $consent; private $audit;
    public function __construct(CommercialMemoryRepository $repo, ConsentRepository $consent, AuditService $audit) { $this->repo=$repo; $this->consent=$consent; $this->audit=$audit; }
    public function store(array $session,array $input) {
        $customer=(int)$session['customer_id']; $consent=$this->consent->granted_record($customer,'memory_storage');
        if (!$consent) return array('error'=>Errors::CONSENT_REQUIRED,'status'=>403,'message'=>'Memory-storage consent is required.');
        $conversation=sanitize_text_field(isset($input['conversation_id'])?$input['conversation_id']:'');
        if (!preg_match('/^(?:conv_[A-Za-z0-9_-]{6,55}|[a-f0-9-]{36})$/',$conversation)) return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'The conversation reference is invalid.');
        $summary=CommercialMemoryPolicy::conversation_summary(isset($input['summary'])?$input['summary']:null);
        if ($summary===null) return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'The conversation summary is unsupported, sensitive, or invalid.');
        $now=current_time('mysql',true); $uuid=wp_generate_uuid4();
        $audit=$this->audit->record('conversation_context.stored','customer',(string)$customer,'success','informational',array('conversation_id'=>$conversation,'metadata'=>array('context_uuid'=>$uuid)));
        $record=$this->repo->store_conversation(array('context_uuid'=>$uuid,'customer_id'=>$customer,'conversation_id'=>$conversation,
            'summary_json'=>wp_json_encode($summary),'source_type'=>'structured_conversation_summary','consent_reference'=>$consent['consent_id'],
            'audit_reference'=>$audit,'observed_at'=>$now,'expires_at'=>gmdate('Y-m-d H:i:s',time()+Config::COMMERCIAL_MEMORY_DEFAULT_RETENTION_DAYS*DAY_IN_SECONDS),
            'status'=>'active','created_at'=>$now,'updated_at'=>$now,'deleted_at'=>null));
        return array('context_uuid'=>$uuid,'conversation_id'=>$conversation,'version'=>(int)$record['version'],'stored'=>true);
    }
}
