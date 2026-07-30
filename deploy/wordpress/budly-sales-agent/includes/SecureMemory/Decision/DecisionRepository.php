<?php
namespace Budly\SecureMemory\Decision;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class DecisionRepository {
    private $wpdb;
    public function __construct($database = null) { if ($database !== null) { $this->wpdb=$database; } else { global $wpdb; $this->wpdb=$wpdb; } }

    public function active_versions() {
        $rows=$this->wpdb->get_results("SELECT configuration_type,version FROM ".Config::table('rule_configurations')." WHERE status='active'",ARRAY_A);
        $versions=array(); foreach($rows as $row){$versions[$row['configuration_type']]=$row['version'];} return $versions;
    }

    public function append(array $record) {
        $result=$this->wpdb->insert(Config::table('decision_evidence'),$record);
        if($result===false){throw new \RuntimeException('Decision evidence could not be recorded.');}
        return (int)$this->wpdb->insert_id;
    }

    public function approved_memory_context($session_id,$customer_id,$conversation_id){
        return (bool)$this->wpdb->get_var($this->wpdb->prepare(
            "SELECT id FROM ".Config::table('memory_contexts')." WHERE session_id=%s AND customer_id=%d AND conversation_id=%s AND agent_id=%s AND approved=1 AND start_fresh=0 AND expires_at>%s LIMIT 1",
            $session_id,$customer_id,$conversation_id,Config::DEFAULT_AGENT_ID,current_time('mysql',true)
        ));
    }
}
