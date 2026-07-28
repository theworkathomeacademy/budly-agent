<?php
namespace Budly\SecureMemory\Memory;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class MemoryRepository {
    private $wpdb;
    public function __construct($database=null){if($database!==null){$this->wpdb=$database;return;}global $wpdb;$this->wpdb=$wpdb;}
    public function active_count($customer_id){return(int)$this->wpdb->get_var($this->wpdb->prepare('SELECT COUNT(*) FROM '.Config::table('conversation_memory').' WHERE customer_id=%d AND deleted_at IS NULL AND (expires_at IS NULL OR expires_at>%s)',$customer_id,current_time('mysql',true)));}
    public function has_summary($customer_id,$conversation_id,$namespace,$agent_id){return(bool)$this->wpdb->get_var($this->wpdb->prepare('SELECT id FROM '.Config::table('conversation_memory').' WHERE customer_id=%d AND conversation_id=%s AND namespace=%s AND source_agent_id=%s AND deleted_at IS NULL LIMIT 1',$customer_id,$conversation_id,$namespace,$agent_id));}
    public function visible($customer_id,$limit=50){return $this->wpdb->get_results($this->wpdb->prepare('SELECT memory_id,conversation_id,namespace,memory_type,schema_version,source_agent_id,summary_json,provenance_json,created_at,updated_at,expires_at,retention_policy,corrected_at FROM '.Config::table('conversation_memory').' WHERE customer_id=%d AND classification=%s AND deleted_at IS NULL AND (expires_at IS NULL OR expires_at>%s) ORDER BY updated_at DESC LIMIT %d',$customer_id,'customer_visible',current_time('mysql',true),min(100,max(1,$limit))),ARRAY_A);}
    public function find_owned($customer_id,$memory_id){return $this->wpdb->get_row($this->wpdb->prepare('SELECT * FROM '.Config::table('conversation_memory').' WHERE customer_id=%d AND memory_id=%s AND deleted_at IS NULL LIMIT 1',$customer_id,$memory_id),ARRAY_A);}
    public function find_context($session_id,$customer_id,$conversation_id,$agent_id){return $this->wpdb->get_row($this->wpdb->prepare('SELECT * FROM '.Config::table('memory_contexts').' WHERE session_id=%s AND customer_id=%d AND conversation_id=%s AND agent_id=%s AND expires_at>%s LIMIT 1',$session_id,$customer_id,$conversation_id,$agent_id,current_time('mysql',true)),ARRAY_A);}
    public function set_context($session_id,$customer_id,$conversation_id,$agent_id,$purpose,$approved,$start_fresh,$expires_at,$now){
        $sql=$this->wpdb->prepare('INSERT INTO '.Config::table('memory_contexts').' (context_id,session_id,customer_id,conversation_id,agent_id,purpose,approved,start_fresh,approved_at,expires_at,created_at,updated_at) VALUES (%s,%s,%d,%s,%s,%s,%d,%d,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE purpose=VALUES(purpose),approved=VALUES(approved),start_fresh=VALUES(start_fresh),approved_at=VALUES(approved_at),expires_at=VALUES(expires_at),updated_at=VALUES(updated_at)', 'ctx_'.bin2hex(random_bytes(12)),$session_id,$customer_id,$conversation_id,$agent_id,$purpose,$approved?1:0,$start_fresh?1:0,$approved?$now:null,$expires_at,$now,$now);
        if($this->wpdb->query($sql)===false)throw new \RuntimeException('Memory context update failed.');
    }
    public function store_summary($customer_id,$conversation_id,$namespace,$agent_id,array $summary,$consent_id,array $provenance,$expires_at,$now){
        $json=wp_json_encode($summary);$hash=hash('sha256',$customer_id.'|'.$namespace.'|'.$conversation_id.'|'.$json);
        $existing=$this->wpdb->get_row($this->wpdb->prepare('SELECT id,memory_id,content_hash FROM '.Config::table('conversation_memory').' WHERE customer_id=%d AND conversation_id=%s AND namespace=%s AND source_agent_id=%s AND deleted_at IS NULL LIMIT 1',$customer_id,$conversation_id,$namespace,$agent_id),ARRAY_A);
        if($existing&&hash_equals($existing['content_hash'],$hash))return array('memory_id'=>$existing['memory_id'],'duplicate'=>true);
        $record=array('conversation_id'=>$conversation_id,'namespace'=>$namespace,'memory_type'=>'conversation_summary','classification'=>'customer_visible','schema_version'=>1,'source_agent_id'=>$agent_id,'summary_json'=>$json,'consent_reference'=>$consent_id,'updated_at'=>$now,'expires_at'=>$expires_at,'provenance_json'=>wp_json_encode($provenance),'content_hash'=>$hash,'retention_policy'=>'customer_memory_default','corrected_at'=>null);
        if($existing){if($this->wpdb->update(Config::table('conversation_memory'),$record,array('id'=>(int)$existing['id']))===false)throw new \RuntimeException('Memory update failed.');return array('memory_id'=>$existing['memory_id'],'duplicate'=>false);}
        $record['memory_id']='mem_'.bin2hex(random_bytes(12));$record['customer_id']=$customer_id;$record['created_at']=$now;$record['deleted_at']=null;
        if($this->wpdb->insert(Config::table('conversation_memory'),$record)===false){
            $duplicate=$this->wpdb->get_row($this->wpdb->prepare('SELECT memory_id FROM '.Config::table('conversation_memory').' WHERE customer_id=%d AND content_hash=%s AND deleted_at IS NULL LIMIT 1',$customer_id,$hash),ARRAY_A);
            if($duplicate)return array('memory_id'=>$duplicate['memory_id'],'duplicate'=>true);
            throw new \RuntimeException('Memory insert failed.');
        }
        return array('memory_id'=>$record['memory_id'],'duplicate'=>false);
    }
    public function correct($customer_id,$memory_id,array $summary,$consent_id,array $provenance,$now){$hash=hash('sha256',$customer_id.'|correction|'.wp_json_encode($summary));$result=$this->wpdb->update(Config::table('conversation_memory'),array('summary_json'=>wp_json_encode($summary),'consent_reference'=>$consent_id,'provenance_json'=>wp_json_encode($provenance),'content_hash'=>$hash,'updated_at'=>$now,'corrected_at'=>$now),array('customer_id'=>$customer_id,'memory_id'=>$memory_id,'classification'=>'customer_visible'));return $result===1;}
    public function delete_one($customer_id,$memory_id,$now){return $this->wpdb->query($this->wpdb->prepare('UPDATE '.Config::table('conversation_memory').' SET deleted_at=%s,summary_json=%s,provenance_json=%s WHERE customer_id=%d AND memory_id=%s AND deleted_at IS NULL',$now,'{}','{}',$customer_id,$memory_id))===1;}
    public function delete_all($customer_id,$now){
        $this->wpdb->query('START TRANSACTION');try{
            if($this->wpdb->query($this->wpdb->prepare('UPDATE '.Config::table('conversation_memory').' SET deleted_at=%s,summary_json=%s,provenance_json=%s WHERE customer_id=%d AND deleted_at IS NULL',$now,'{}','{}',$customer_id))===false)throw new \RuntimeException('Memory deletion failed.');
            if($this->wpdb->delete(Config::table('preferences'),array('customer_id'=>$customer_id))===false)throw new \RuntimeException('Preference deletion failed.');
            if($this->wpdb->delete(Config::table('memory_contexts'),array('customer_id'=>$customer_id))===false)throw new \RuntimeException('Context deletion failed.');
            if($this->wpdb->update(Config::table('customers'),array('preferred_name'=>'','updated_at'=>$now),array('id'=>$customer_id))===false)throw new \RuntimeException('Profile deletion failed.');
            $this->wpdb->query('COMMIT');
        }catch(\Throwable $e){$this->wpdb->query('ROLLBACK');throw $e;}
    }
}
