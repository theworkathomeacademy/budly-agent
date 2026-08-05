<?php
namespace Budly\SecureMemory\CommercialMemory;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Consent\ConsentService;
use Budly\SecureMemory\Errors;
use Budly\SecureMemory\Memory\MemoryPolicy;
use Budly\SecureMemory\Profile\ProfileService;

if (!defined('ABSPATH')) { exit; }

final class CommercialContextBuilder {
    const JOURNEYS = array('wellness','culinary','education','membership','wholesale','general');
    private $repo; private $memory; private $profile; private $consent; private $audit;
    public function __construct(CommercialMemoryRepository $repo, CommercialMemoryService $memory, ProfileService $profile, ConsentService $consent, AuditService $audit) {
        $this->repo=$repo; $this->memory=$memory; $this->profile=$profile; $this->consent=$consent; $this->audit=$audit;
    }

    public function build(array $session,array $input) {
        $customer=(int)$session['customer_id'];
        if (!$this->consent->is_granted($customer,'memory_use')) return array('error'=>Errors::CONSENT_REQUIRED,'status'=>403,'message'=>'Memory-use consent is required.');
        $objective=isset($input['objective'])?sanitize_text_field((string)$input['objective']):'';
        if ($objective===''||mb_strlen($objective)>500||MemoryPolicy::contains_sensitive($objective)) return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'A safe current objective is required.');
        $journey=sanitize_key(isset($input['journey'])?$input['journey']:'general');
        if (!in_array($journey,self::JOURNEYS,true)) return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'The journey stage is invalid.');
        $exclusions=array();
        foreach ((array)(isset($input['known_exclusions'])?$input['known_exclusions']:array()) as $value) {
            if (count($exclusions)>=50) return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'Too many exclusions were supplied.');
            $value=sanitize_key((string)$value); if (!preg_match('/^[a-z0-9][a-z0-9-]{1,99}$/',$value)) return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>'An exclusion is invalid.');
            $exclusions[]=$value;
        }
        $read=$this->memory->read($session,array()); if (!empty($read['error'])) return $read;
        $latest=$this->repo->conversation_latest($customer); $summary=$latest?json_decode($latest['summary_json'],true):null;
        $profile=$this->profile->read($customer);
        $preferences=array_values(array_filter($read['items'],function($item){return in_array($item['type'],array('preferred_format','preferred_communication_style','customer_interest','product_interest'),true);}));
        $context=array(
            'context_version'=>'commercial-context-1.5.0',
            'verified_customer_profile'=>array_intersect_key((array)$profile,array_flip(array('customer_id','preferred_name','experience_level','communication_preferences'))),
            'conversation_history_summary'=>$summary,
            'relevant_memory_objects'=>$read['items'],
            'current_objective'=>$objective,
            'current_consent_state'=>$this->consent->read($customer),
            'journey_stage'=>$journey,
            'known_exclusions'=>array_values(array_unique($exclusions)),
            'known_preferences'=>$preferences,
        );
        $this->audit->record('commercial_context.built','customer',(string)$customer,'success','informational',array('metadata'=>array('memory_count'=>count($read['items']),'journey'=>$journey,'exclusion_count'=>count($exclusions))));
        return $context;
    }
}
