<?php
namespace Budly\SecureMemory\CommercialMemory;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class CommercialMemoryRepository {
    private $wpdb;
    public function __construct($database = null) { if ($database !== null) { $this->wpdb = $database; } else { global $wpdb; $this->wpdb = $wpdb; } }

    public function active_count($customer_id) {
        return (int) $this->wpdb->get_var($this->wpdb->prepare(
            "SELECT COUNT(*) FROM " . Config::table('commercial_memory') . " WHERE customer_id=%d AND status='active' AND deleted_at IS NULL AND (expires_at IS NULL OR expires_at>%s)",
            $customer_id, current_time('mysql', true)
        ));
    }

    public function active($customer_id, array $types = array(), $limit = 100) {
        $where = array("customer_id=%d", "status='active'", 'deleted_at IS NULL', '(expires_at IS NULL OR expires_at>%s)');
        $args = array($customer_id, current_time('mysql', true));
        if ($types) { $where[] = 'memory_type IN (' . implode(',', array_fill(0, count($types), '%s')) . ')'; $args = array_merge($args, $types); }
        $args[] = min(200, max(1, (int) $limit));
        $sql = 'SELECT * FROM ' . Config::table('commercial_memory') . ' WHERE ' . implode(' AND ', $where) . ' ORDER BY memory_type,observed_at DESC,memory_uuid LIMIT %d';
        return $this->wpdb->get_results($this->wpdb->prepare($sql, $args), ARRAY_A);
    }

    public function find_owned($customer_id, $uuid) {
        return $this->wpdb->get_row($this->wpdb->prepare(
            'SELECT * FROM ' . Config::table('commercial_memory') . " WHERE customer_id=%d AND memory_uuid=%s AND status='active' AND deleted_at IS NULL LIMIT 1",
            $customer_id, $uuid
        ), ARRAY_A);
    }

    public function customer_for_uuid($uuid) {
        return $this->wpdb->get_var($this->wpdb->prepare(
            'SELECT customer_id FROM ' . Config::table('commercial_memory') . " WHERE memory_uuid=%s AND status='active' LIMIT 1", $uuid
        ));
    }

    public function create(array $record) {
        if ($this->wpdb->insert(Config::table('commercial_memory'), $record) === false) { throw new \RuntimeException('Commercial memory could not be stored.'); }
        return $record;
    }

    public function supersede(array $prior, array $replacement) {
        $this->wpdb->query('START TRANSACTION');
        try {
            $changed = $this->wpdb->update(Config::table('commercial_memory'), array('status'=>'superseded','updated_at'=>$replacement['updated_at']), array('id'=>(int) $prior['id'],'status'=>'active'));
            if ($changed !== 1) { throw new \RuntimeException('The memory version changed before supersession.'); }
            if ($this->wpdb->insert(Config::table('commercial_memory'), $replacement) === false) { throw new \RuntimeException('The replacement memory could not be stored.'); }
            $this->wpdb->query('COMMIT');
            return $replacement;
        } catch (\Throwable $error) { $this->wpdb->query('ROLLBACK'); throw $error; }
    }

    public function invalidate($customer_id, $uuid, $reason, $audit_reference, $now) {
        return $this->wpdb->update(Config::table('commercial_memory'), array(
            'status'=>'invalidated','invalidated_reason'=>$reason,'audit_reference'=>$audit_reference,'updated_at'=>$now,
        ), array('customer_id'=>$customer_id,'memory_uuid'=>$uuid,'status'=>'active')) === 1;
    }

    public function delete_owned($customer_id, $uuid, $audit_reference, $now) {
        return $this->wpdb->update(Config::table('commercial_memory'), array(
            'status'=>'deleted','value_json'=>'null','audit_reference'=>$audit_reference,'updated_at'=>$now,'deleted_at'=>$now,
        ), array('customer_id'=>$customer_id,'memory_uuid'=>$uuid,'status'=>'active')) === 1;
    }

    public function expire_due($now) {
        return (int) $this->wpdb->query($this->wpdb->prepare(
            'UPDATE ' . Config::table('commercial_memory') . " SET status='expired',updated_at=%s WHERE status='active' AND deleted_at IS NULL AND expires_at IS NOT NULL AND expires_at<=%s",
            $now, $now
        ));
    }

    public function update_consent_state($customer_id, $state, $now) {
        return (int)$this->wpdb->query($this->wpdb->prepare(
            'UPDATE '.Config::table('commercial_memory').' SET consent_state=%s,updated_at=%s WHERE customer_id=%d AND status=%s AND deleted_at IS NULL',
            $state,$now,$customer_id,'active'
        ));
    }

    public function conversation_latest($customer_id) {
        return $this->wpdb->get_row($this->wpdb->prepare(
            'SELECT * FROM ' . Config::table('conversation_contexts') . " WHERE customer_id=%d AND status='active' AND deleted_at IS NULL AND (expires_at IS NULL OR expires_at>%s) ORDER BY observed_at DESC,id DESC LIMIT 1",
            $customer_id, current_time('mysql', true)
        ), ARRAY_A);
    }

    public function store_conversation(array $record) {
        $next = (int) $this->wpdb->get_var($this->wpdb->prepare(
            'SELECT COALESCE(MAX(version),0)+1 FROM ' . Config::table('conversation_contexts') . ' WHERE customer_id=%d AND conversation_id=%s',
            $record['customer_id'], $record['conversation_id']
        ));
        $record['version'] = max(1, $next);
        if ($this->wpdb->insert(Config::table('conversation_contexts'), $record) === false) { throw new \RuntimeException('Conversation context could not be stored.'); }
        return $record;
    }

    public function admin_search(array $filters, $page, $per_page) {
        $page=max(1,(int)$page);$per_page=min(100,max(1,(int)$per_page));
        $where = array('1=1'); $args = array();
        foreach (array('memory_type','namespace','status','consent_state') as $key) {
            if (!empty($filters[$key])) { $where[] = $key . '=%s'; $args[] = sanitize_key($filters[$key]); }
        }
        if (!empty($filters['customer_reference'])) { $where[] = 'customer_id=(SELECT id FROM ' . Config::table('customers') . ' WHERE public_id=%s LIMIT 1)'; $args[] = sanitize_text_field($filters['customer_reference']); }
        if (!empty($filters['type'])) { $where[] = 'memory_type=%s'; $args[] = sanitize_key($filters['type']); }
        if (!empty($filters['confidence_min'])) { $where[] = 'confidence>=%f'; $args[] = (float) $filters['confidence_min']; }
        if (!empty($filters['expires_before'])) { $where[] = 'expires_at IS NOT NULL AND expires_at<=%s'; $args[] = sanitize_text_field($filters['expires_before']); }
        if (!empty($filters['expiration_state'])) {
            if ($filters['expiration_state']==='expired') $where[] = "status='expired'";
            elseif ($filters['expiration_state']==='due_soon') {$where[]='expires_at IS NOT NULL AND expires_at>%s AND expires_at<=%s';$args[]=current_time('mysql',true);$args[]=gmdate('Y-m-d H:i:s',time()+30*DAY_IN_SECONDS);}
            elseif ($filters['expiration_state']==='no_expiration') $where[]='expires_at IS NULL';
        }
        if (!empty($filters['query'])) { $where[] = '(source_reference LIKE %s OR memory_type LIKE %s)'; $like = '%' . $this->wpdb->esc_like(sanitize_text_field($filters['query'])) . '%'; $args[] = $like; $args[] = $like; }
        $where_sql=implode(' AND ', $where);$count_args=$args;
        $count_sql='SELECT COUNT(*) FROM ' . Config::table('commercial_memory') . ' WHERE ' . $where_sql;
        $total=(int)($count_args?$this->wpdb->get_var($this->wpdb->prepare($count_sql,$count_args)):$this->wpdb->get_var($count_sql));
        $offset = ($page - 1) * $per_page; $args[] = $per_page; $args[] = $offset;
        $sql = 'SELECT memory_uuid,customer_id,namespace,memory_type,confidence,confidence_basis,source_type,source_reference,observed_at,consent_state,expiration_policy,expires_at,version,supersedes_uuid,status,audit_reference,created_at,updated_at FROM ' . Config::table('commercial_memory') . ' WHERE ' . $where_sql . ' ORDER BY updated_at DESC LIMIT %d OFFSET %d';
        return array('items'=>$this->wpdb->get_results($this->wpdb->prepare($sql,$args),ARRAY_A),'page'=>$page,'per_page'=>$per_page,'total'=>$total);
    }
}
