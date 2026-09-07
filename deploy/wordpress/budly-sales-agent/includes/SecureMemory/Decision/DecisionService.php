<?php
namespace Budly\SecureMemory\Decision;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Consent\ConsentRepository;
use Budly\SecureMemory\Errors;
use Budly\SecureMemory\Validation;

if (!defined('ABSPATH')) { exit; }

final class DecisionService {
    private $repo; private $consent; private $audit;
    private const REQUIRED_VERSIONS=array(
        'qualification'=>'qualification-1.3.4.1','recommendation'=>'recommendation-1.3.4.1',
        'catalog'=>'catalog-allowlist-2026-07-16','journeys'=>'journey-routing-1.3.4.1',
        'escalation'=>'escalation-1.3.4.1','consent'=>'secure-memory-consent-1.0',
        'retention'=>'secure-memory-retention-1.1.0','commercial_memory'=>'commercial-memory-1.5.0.0',
    );
    private const CATALOG=array(
        array('id'=>'therapeutic-body-butter','category'=>'wellness','terms'=>'body butter topical one-time'),
        array('id'=>'therapeutic-body-butter-monthly','category'=>'wellness','terms'=>'body butter topical monthly subscription'),
        array('id'=>'therapeutic-oil-tincture-1-time','category'=>'wellness','terms'=>'oil tincture one-time'),
        array('id'=>'therapeutic-oil-tincture-monthly','category'=>'wellness','terms'=>'oil tincture monthly subscription'),
        array('id'=>'therapeutic-combo-monthly-subscription','category'=>'wellness','terms'=>'combo oil body butter monthly subscription'),
        array('id'=>'therapeutic-combo-one-time-purchase','category'=>'wellness','terms'=>'combo oil body butter one-time'),
        array('id'=>'infused-cooking-oil-4oz','category'=>'culinary','terms'=>'infused cooking oil culinary'),
        array('id'=>'infused-cooking-oil-8oz','category'=>'culinary','terms'=>'infused cooking oil culinary 8oz'),
        array('id'=>'infused-cooking-oil-12oz','category'=>'culinary','terms'=>'infused cooking oil culinary 12oz'),
        array('id'=>'infused-cooking-oil-16oz','category'=>'culinary','terms'=>'infused cooking oil culinary 16oz'),
        array('id'=>'infused-basics','category'=>'education','terms'=>'beginner book infusion cooking education'),
        array('id'=>'wakenbake-lounge-cannabis-botanical-collection-volume-1','category'=>'education','terms'=>'botanical collection book education digital print'),
        array('id'=>'culinary-cannabis','category'=>'education','terms'=>'culinary course cooking education'),
        array('id'=>'culinary-cannabis-payment-plan','category'=>'education','terms'=>'culinary course cooking education payment plan'),
        array('id'=>'grow-cannabis-home','category'=>'education','terms'=>'grow home course education'),
        array('id'=>'grow-cannabis-home-payment-plan','category'=>'education','terms'=>'grow home course education payment plan'),
        array('id'=>'cook-grow-with-me','category'=>'education','terms'=>'cook grow course education'),
        array('id'=>'cook-grow-with-me-payment-plan','category'=>'education','terms'=>'cook grow course education payment plan'),
        array('id'=>'azurea-skye','category'=>'membership','terms'=>'nft digital membership'),
        array('id'=>'cookie-cutter','category'=>'membership','terms'=>'cookie cutter nft digital membership'),
        array('id'=>'dizel','category'=>'membership','terms'=>'dizel nft digital membership'),
        array('id'=>'the-monarch','category'=>'membership','terms'=>'monarch nft digital membership'),
        array('id'=>'the-original-guardian','category'=>'membership','terms'=>'original guardian nft digital membership'),
        array('id'=>'the-don','category'=>'membership','terms'=>'don godfather nft digital membership'),
        array('id'=>'gamma-blaze','category'=>'membership','terms'=>'gamma blaze nft digital membership'),
        array('id'=>'berry-bliss','category'=>'membership','terms'=>'berry bliss nft digital membership'),
        array('id'=>'torque','category'=>'membership','terms'=>'torque nft digital membership'),
        array('id'=>'the-chemist','category'=>'membership','terms'=>'chemist nft digital membership'),
        array('id'=>'white-label-oil-per-1oz-min-10oz','category'=>'wholesale','terms'=>'bulk oil white label wholesale','human'=>true),
        array('id'=>'white-label-cbd-combo-per-1oz','category'=>'wholesale','terms'=>'bulk cbd combo white label wholesale','human'=>true),
        array('id'=>'white-label-butter-per-1oz-min-16oz','category'=>'wholesale','terms'=>'bulk butter white label wholesale','human'=>true),
        array('id'=>'bulk-butter','category'=>'wholesale','terms'=>'bulk butter wholesale','human'=>true),
    );
    public function __construct(DecisionRepository $repo,ConsentRepository $consent,AuditService $audit){$this->repo=$repo;$this->consent=$consent;$this->audit=$audit;}

    public function evaluate(array $input,array $session=array()) {
        try{$conversation=Validation::bounded_text($input['conversation_id']??'',64);$objective=Validation::bounded_text($input['objective']??'',500);}
        catch(\InvalidArgumentException $e){return $this->error('The decision request contains an oversized value.');}
        $journey=sanitize_key($input['journey']??'');
        if(!preg_match('/^(?:conv_[a-z0-9]{12,40}|[a-f0-9-]{36})$/',$conversation)||!in_array($journey,array('wellness','culinary','education','membership','wholesale'),true)||$objective===''){return $this->error('The decision request is invalid.');}
        $answers=array();foreach((array)($input['answers']??array()) as $answer){if(count($answers)>=5)break;$answers[]=Validation::bounded_text($answer,200);}
        $versions=$this->repo->active_versions();
        foreach(self::REQUIRED_VERSIONS as $type=>$version){if(($versions[$type]??'')!==$version){return array('error'=>Errors::RESOURCE_CONFLICT,'status'=>503,'message'=>'Governed decision configuration is unavailable.');}}
        $customer=(int)($session['customer_id']??0);$verified=$customer>0;$commercial_context=is_array($input['commercial_context']??null)?$input['commercial_context']:array();$memory=(bool)($input['use_memory']??false)||!empty($commercial_context);
        $memory_terms=array();$memory_refs=array();foreach((array)($commercial_context['relevant_memory_objects']??array()) as $item){if(count($memory_terms)>=50)break;if(!is_array($item)||empty($item['uuid'])||!array_key_exists('value',$item))continue;$value=is_scalar($item['value'])?(string)$item['value']:'';if($value!=='')$memory_terms[]=$value;$memory_refs[]=array('uuid'=>sanitize_text_field((string)$item['uuid']),'type'=>sanitize_key((string)($item['type']??'')),'version'=>(int)($item['version']??0));}
        $text=strtolower($objective.' '.implode(' ',$answers).' '.implode(' ',$memory_terms));
        $risk=(bool)preg_match('/\b(diagnose|treat|treatment|cure|cancer|dosage|dose|medication|hospital|under 18|under 21|legal advice)\b/',$text);
        $eligible=array();$excluded=array();$selected=null;$confidence='insufficient';$outcome='no_match';$action='request_clarification_or_human_help';$escalation=null;
        if($memory&&(!$verified||$this->consent->status($customer,'memory_use')!=='granted'||(empty($commercial_context)&&!$this->repo->approved_memory_context($session['session_id']??'',$customer,$conversation)))){$outcome='consent_restricted';$action='continue_without_memory';}
        elseif($risk){$outcome='human_review';$action='human_escalation';$escalation=Validation::opaque_id('esc');}
        else{
            $words=array_values(array_unique(preg_split('/[^a-z0-9]+/',$text,-1,PREG_SPLIT_NO_EMPTY)));
            $best=0;
            foreach(self::CATALOG as $product){
                if(in_array($product['id'],(array)($commercial_context['known_exclusions']??array()),true)){$excluded[]=array('product_id'=>$product['id'],'reason'=>'customer_exclusion');continue;}
                if($product['category']!==$journey){$excluded[]=array('product_id'=>$product['id'],'reason'=>'journey_ineligible');continue;}
                if(!empty($product['human'])){$excluded[]=array('product_id'=>$product['id'],'reason'=>'human_sales_required');continue;}
                $score=0;foreach($words as $word){if(strlen($word)>2&&strpos($product['terms'],$word)!==false)$score++;}
                $eligible[]=array('product_id'=>$product['id'],'score'=>$score);
                if($score>$best){$best=$score;$selected=$product['id'];}
            }
            $requested=sanitize_key($input['requested_product_id']??'');
            if($requested&&!in_array($requested,array_column(self::CATALOG,'id'),true)){$excluded[]=array('product_id'=>$requested,'reason'=>'not_allowlisted');}
            if($journey==='wholesale'){$outcome='human_review';$action='human_escalation';$escalation=Validation::opaque_id('esc');}
            elseif(count($answers)<2){$outcome='clarification_required';$confidence='low';$action='request_clarification';$selected=null;}
            elseif(count($answers)===2){$outcome='nurture';$confidence=$best>0?'low':'insufficient';$action='continue_education';$selected=null;}
            elseif($selected===null||$best<1){$outcome='no_match';$action='request_clarification_or_human_help';}
            else{$outcome='recommended';$confidence=$best>=4?'high':($best>=2?'medium':'low');$action='show_approved_product';}
        }
        $qualification=count($answers)>=3?'qualified':(count($answers)===2?'nurture':'insufficient');
        $attribution_input=is_array($input['attribution']??null)?$input['attribution']:array();
        $attr_fields=array('source','platform','content_id','campaign_id','cta_id','product_or_topic','published_post_id');
        $clean_attribution=array();
        foreach($attr_fields as $f){
            if(isset($attribution_input[$f])&&is_scalar($attribution_input[$f])){
                $val=sanitize_text_field(substr(trim((string)$attribution_input[$f]),0,100));
                if($val!=='')$clean_attribution[$f]=$val;
            }
        }
        $inputs_data=array('answer_count'=>count($answers),'qualification'=>$qualification,'qualification_rule_version'=>$versions['qualification'],'memory_requested'=>$memory,'commercial_context_version'=>$commercial_context['context_version']??null,'commercial_memory_references'=>$memory_refs,'verified'=>$verified);
        if(!empty($clean_attribution)){$inputs_data['attribution']=$clean_attribution;}
        $decision=Validation::opaque_id('dec');$customer_ref=$verified?'customer_'.hash_hmac('sha256',(string)$customer,wp_salt('auth')):'';
        $record=array('decision_id'=>$decision,'decision_type'=>'recommendation','customer_reference'=>$customer_ref,'session_id'=>$session['session_id']??'','conversation_id'=>$conversation,'journey'=>$journey,'objective'=>$risk?'[sensitive request withheld]':$objective,'inputs_json'=>wp_json_encode($inputs_data),'rule_version'=>$versions['recommendation'],'eligible_products_json'=>wp_json_encode($eligible),'excluded_products_json'=>wp_json_encode($excluded),'outcome'=>$outcome,'selected_product_id'=>$selected,'confidence'=>$confidence,'escalation_reference'=>$escalation,'resulting_action'=>$action,'created_at'=>current_time('mysql',true));
        $this->repo->append($record);
        $actor=$verified?'customer':'visitor';$actor_id=$verified?(string)$customer:'anonymous';
        $audit_metadata=array('decision_id'=>$decision,'outcome'=>$outcome,'rule_version'=>$versions['recommendation']);
        if(!empty($clean_attribution)){$audit_metadata['attribution']=$clean_attribution;}
        $this->audit->record('decision.recommendation',$actor,$actor_id,'success',$risk?'warning':'informational',array('customer_reference'=>$customer_ref,'conversation_id'=>$conversation,'metadata'=>$audit_metadata));
        $res=array('decision_id'=>$decision,'outcome'=>$outcome,'rule_version'=>$versions['recommendation'],'eligible_products'=>$eligible,'excluded_products'=>$excluded,'selected_product_id'=>$selected,'confidence'=>$confidence,'escalation_reference'=>$escalation,'resulting_action'=>$action,'verified_customer'=>$verified);
        if(!empty($clean_attribution)){$res['attribution']=$clean_attribution;}
        return $res;
    }
    private function error($message){return array('error'=>Errors::INVALID_REQUEST,'status'=>422,'message'=>$message);}
}
