<?php
namespace Budly\SecureMemory\Sessions;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Config;
use Budly\SecureMemory\Database\Repository;
use Budly\SecureMemory\Validation;

if (!defined('ABSPATH')) { exit; }

final class SessionService {
    private static $instance;
    private $repository;
    private $audit;

    public function __construct(SessionRepository $repository, AuditService $audit) {
        $this->repository = $repository;
        $this->audit = $audit;
    }

    public static function instance() {
        if (!self::$instance) {
            self::$instance = new self(new SessionRepository(), new AuditService(new Repository()));
        }
        return self::$instance;
    }

    public function create($customer_id, $agent_id) {
        $token = rtrim(strtr(base64_encode(random_bytes(32)), '+/', '-_'), '=');
        $token_hash = $this->token_hash($token);
        $now_epoch = time();
        $now = gmdate('Y-m-d H:i:s', $now_epoch);
        $idle = gmdate('Y-m-d H:i:s', $now_epoch + Config::SESSION_IDLE_SECONDS);
        $absolute = gmdate('Y-m-d H:i:s', $now_epoch + Config::SESSION_ABSOLUTE_SECONDS);
        $session_id = Validation::opaque_id('ses');
        $this->repository->create(array(
            'session_id'=>$session_id, 'customer_id'=>(int) $customer_id,
            'token_hash'=>$token_hash, 'agent_id'=>sanitize_key($agent_id), 'status'=>'active',
            'created_at'=>$now, 'last_seen_at'=>$now, 'idle_expires_at'=>$idle,
            'absolute_expires_at'=>$absolute, 'revoked_at'=>null, 'revoke_reason'=>'',
        ));
        $this->set_cookie($token, $now_epoch + Config::SESSION_ABSOLUTE_SECONDS);
        $this->audit->record('session.created','customer',(string) $customer_id,'success','informational',array('metadata'=>array('session_id'=>$session_id)));
        unset($token);
        return array(
            'session_id'=>$session_id,
            'idle_expires_at'=>gmdate('c', strtotime($idle . ' UTC')),
            'absolute_expires_at'=>gmdate('c', strtotime($absolute . ' UTC')),
            'csrf_token'=>$this->csrf_token($token_hash),
        );
    }

    public function validate($touch = true) {
        $token = isset($_COOKIE[Config::SESSION_COOKIE]) ? (string) wp_unslash($_COOKIE[Config::SESSION_COOKIE]) : '';
        if ($token === '' || strlen($token) > 128) { return array('error'=>'SESSION_REQUIRED'); }
        $record = $this->repository->find_by_token_hash($this->token_hash($token));
        unset($token);
        if (!$record || $record['status'] !== 'active' || !empty($record['revoked_at'])) { return array('error'=>'SESSION_REVOKED'); }
        $now_epoch = time();
        if (strtotime($record['absolute_expires_at'] . ' UTC') <= $now_epoch || strtotime($record['idle_expires_at'] . ' UTC') <= $now_epoch) {
            $this->repository->revoke($record['session_id'], 'expired', gmdate('Y-m-d H:i:s', $now_epoch));
            $this->clear_cookie();
            return array('error'=>'SESSION_EXPIRED');
        }
        if ($touch) {
            $idle_epoch = min($now_epoch + Config::SESSION_IDLE_SECONDS, strtotime($record['absolute_expires_at'] . ' UTC'));
            if (!$this->repository->touch($record['session_id'], gmdate('Y-m-d H:i:s', $now_epoch), gmdate('Y-m-d H:i:s', $idle_epoch))) {
                return array('error'=>'SESSION_REVOKED');
            }
            $record['idle_expires_at'] = gmdate('Y-m-d H:i:s', $idle_epoch);
        }
        $record['csrf_token'] = $this->csrf_token($record['token_hash']);
        unset($record['token_hash']);
        return $record;
    }

    public function csrf_is_valid(array $session, $provided) {
        return is_string($provided) && $provided !== '' && hash_equals($session['csrf_token'], $provided);
    }

    public function logout(array $session) {
        $this->repository->revoke($session['session_id'], 'customer_logout', current_time('mysql', true));
        $this->clear_cookie();
        $this->audit->record('session.revoked','customer',(string) $session['customer_id'],'success','informational',array('metadata'=>array('session_id'=>$session['session_id'],'reason'=>'customer_logout')));
    }

    public function revoke_all_for_customer($customer_id, $reason) {
        return $this->repository->revoke_all_for_customer((int) $customer_id, $reason, current_time('mysql', true));
    }

    private function token_hash($token) { return hash_hmac('sha256', $token, wp_salt('auth')); }
    private function csrf_token($token_hash) { return hash_hmac('sha256', 'csrf|' . $token_hash, wp_salt('secure_auth')); }

    private function set_cookie($token, $expires) {
        setcookie(Config::SESSION_COOKIE, $token, array(
            'expires'=>$expires, 'path'=>'/', 'secure'=>true, 'httponly'=>true, 'samesite'=>'Strict',
        ));
    }

    public function clear_cookie() {
        setcookie(Config::SESSION_COOKIE, '', array(
            'expires'=>time() - 3600, 'path'=>'/', 'secure'=>true, 'httponly'=>true, 'samesite'=>'Strict',
        ));
    }
}
