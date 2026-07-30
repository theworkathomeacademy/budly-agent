<?php
namespace Budly\SecureMemory\Profile;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class ProfileRepository {
    private $wpdb;
    public function __construct($database = null) { if ($database !== null) { $this->wpdb=$database; return; } global $wpdb; $this->wpdb=$wpdb; }
    public function customer($customer_id) {
        return $this->wpdb->get_row($this->wpdb->prepare('SELECT public_id,preferred_name,status,email_verified,updated_at FROM '.Config::table('customers').' WHERE id = %d AND status = %s LIMIT 1',$customer_id,'active'),ARRAY_A);
    }
    public function preferences($customer_id) {
        return $this->wpdb->get_results($this->wpdb->prepare('SELECT preference_key,preference_json,updated_at FROM '.Config::table('preferences').' WHERE customer_id = %d AND classification = %s',$customer_id,'customer_visible'),ARRAY_A);
    }
    public function update($customer_id, array $fields, $now) {
        $this->wpdb->query('START TRANSACTION');
        try {
            if (array_key_exists('preferred_name',$fields)) {
                if ($this->wpdb->update(Config::table('customers'),array('preferred_name'=>$fields['preferred_name'],'updated_at'=>$now),array('id'=>$customer_id))===false) throw new \RuntimeException('Profile update failed.');
                unset($fields['preferred_name']);
            }
            foreach ($fields as $key=>$value) {
                $sql=$this->wpdb->prepare('INSERT INTO '.Config::table('preferences').' (customer_id,preference_key,preference_json,classification,schema_version,created_at,updated_at) VALUES (%d,%s,%s,%s,%d,%s,%s) ON DUPLICATE KEY UPDATE preference_json=VALUES(preference_json),classification=VALUES(classification),schema_version=VALUES(schema_version),updated_at=VALUES(updated_at)', $customer_id,'profile.'.$key,wp_json_encode($value),'customer_visible',1,$now,$now);
                if ($this->wpdb->query($sql)===false) throw new \RuntimeException('Profile preference update failed.');
            }
            $this->wpdb->query('COMMIT');
        } catch (\Throwable $error) { $this->wpdb->query('ROLLBACK'); throw $error; }
    }
    public function update_preferences($customer_id,array $fields,$now){
        $this->wpdb->query('START TRANSACTION');try{foreach($fields as $key=>$value){$sql=$this->wpdb->prepare('INSERT INTO '.Config::table('preferences').' (customer_id,preference_key,preference_json,classification,schema_version,created_at,updated_at) VALUES (%d,%s,%s,%s,%d,%s,%s) ON DUPLICATE KEY UPDATE preference_json=VALUES(preference_json),classification=VALUES(classification),schema_version=VALUES(schema_version),updated_at=VALUES(updated_at)',$customer_id,$key,wp_json_encode($value),'customer_visible',1,$now,$now);if($this->wpdb->query($sql)===false)throw new \RuntimeException('Preference update failed.');}$this->wpdb->query('COMMIT');}catch(\Throwable $e){$this->wpdb->query('ROLLBACK');throw $e;}
    }
}
