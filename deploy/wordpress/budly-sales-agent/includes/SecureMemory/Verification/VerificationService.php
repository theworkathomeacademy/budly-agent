<?php
namespace Budly\SecureMemory\Verification;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Config;
use Budly\SecureMemory\Email\EmailTransport;
use Budly\SecureMemory\Errors;
use Budly\SecureMemory\Validation;

if (!defined('ABSPATH')) { exit; }

final class VerificationService {
    const NEUTRAL_MESSAGE = "If this address is eligible, we've sent a verification code.";
    private $repository;
    private $audit;
    private $email;

    public function __construct(VerificationRepository $repository, AuditService $audit, EmailTransport $email) {
        $this->repository = $repository;
        $this->audit = $audit;
        $this->email = $email;
    }

    public function request_code($email, $ip_address) {
        $normalized = Validation::normalize_email($email);
        if (!$normalized || !is_email($normalized)) { return array('error'=>Errors::INVALID_EMAIL,'status'=>422,'message'=>'Please enter a valid email address.'); }
        $email_hash = Validation::email_hash($normalized);
        $ip_hash = hash_hmac('sha256', (string) $ip_address, wp_salt('nonce'));
        $now = current_time('mysql', true);
        $cooldown_since = gmdate('Y-m-d H:i:s', time() - Config::verification_resend_cooldown_seconds());
        $since = gmdate('Y-m-d H:i:s', time() - Config::VERIFICATION_RATE_WINDOW);
        if ($this->repository->count_since('email_hash', $email_hash, $cooldown_since) > 0 ||
            $this->repository->count_since('email_hash', $email_hash, $since) >= Config::rate_limit('verification_email') ||
            $this->repository->count_since('ip_hash', $ip_hash, $since) >= Config::rate_limit('verification_ip')) {
            $this->audit->record('rate_limit.triggered','visitor',$ip_hash,'denied','warning',array('customer_reference'=>$email_hash,'metadata'=>array('endpoint'=>'auth/request-code')));
            return array('error'=>Errors::RATE_LIMITED,'status'=>429,'message'=>'Please wait before requesting another code.');
        }
        $customer = $this->repository->customer_by_email_hash($email_hash);
        $request_id = Validation::opaque_id('ver');
        $code = str_pad((string) random_int(0, 999999), 6, '0', STR_PAD_LEFT);
        $expires_at = gmdate('Y-m-d H:i:s', time() + Config::VERIFICATION_TTL_SECONDS);
        $this->repository->invalidate_open_for_email($email_hash, $now);
        $this->repository->create(array(
            'request_id'=>$request_id,
            'customer_id'=>$customer ? (int) $customer['id'] : null,
            'email'=>$customer ? $normalized : '',
            'email_hash'=>$email_hash,
            'code_hash'=>wp_hash_password($code),
            'ip_hash'=>$ip_hash,
            'attempts'=>0,
            'locked_at'=>null,
            'consumed_at'=>null,
            'expires_at'=>$expires_at,
            'delivery_status'=>$customer ? 'pending' : 'ineligible',
            'created_at'=>$now,
        ));
        $this->audit->record('verification.requested','visitor',$ip_hash,'success','informational',array('customer_reference'=>$email_hash,'metadata'=>array('request_id'=>$request_id)));
        if ($customer) {
            $sent = $this->email->send_verification_code($normalized, $code, (int) (Config::VERIFICATION_TTL_SECONDS / 60));
            $this->repository->set_delivery_status($request_id, $sent ? 'sent' : 'failed');
            $this->audit->record($sent ? 'verification.sent' : 'verification.delivery_failed','system','email','' . ($sent ? 'success' : 'failure'),$sent ? 'informational' : 'error',array('customer_reference'=>$email_hash,'metadata'=>array('request_id'=>$request_id)));
        }
        unset($code);
        return array('request_id'=>$request_id,'expires_in_seconds'=>Config::VERIFICATION_TTL_SECONDS,'message'=>self::NEUTRAL_MESSAGE);
    }

    public function verify($request_id, $code) {
        try {
            $request_id = Validation::bounded_text($request_id, 40);
        } catch (\InvalidArgumentException $error) {
            return array('error'=>Errors::INVALID_REQUEST,'status'=>400,'message'=>'The verification request is invalid.');
        }
        $code = preg_replace('/[^0-9]/', '', (string) $code);
        if (strlen($code) !== 6) { return array('error'=>Errors::INVALID_CODE,'status'=>422,'message'=>"That code doesn't match. Please try again."); }
        $result = $this->repository->consume($request_id, $code, current_time('mysql', true), Config::rate_limit('verification_attempts'));
        if (!empty($result['error'])) {
            $map = array(
                'CODE_EXPIRED'=>array(Errors::CODE_EXPIRED,410,'That code has expired. Request a new one to continue.'),
                'CODE_ALREADY_USED'=>array(Errors::CODE_ALREADY_USED,409,'That code is no longer available. Request a new one to continue.'),
                'VERIFICATION_LOCKED'=>array(Errors::VERIFICATION_LOCKED,429,'For your security, this verification request has been locked. Please request a new code.'),
                'INVALID_CODE'=>array(Errors::INVALID_CODE,401,"That code doesn't match. Please try again."),
            );
            $safe = $map[$result['error']];
            $this->audit->record($result['error']==='VERIFICATION_LOCKED'?'verification.locked':'verification.failed','visitor','public','failure',$result['error']==='VERIFICATION_LOCKED'?'warning':'informational',array('metadata'=>array('request_id'=>$request_id,'reason'=>$result['error'])));
            return array('error'=>$safe[0],'status'=>$safe[1],'message'=>$safe[2]);
        }
        $this->audit->record('verification.succeeded','customer',(string) $result['customer_id'],'success','informational',array('metadata'=>array('request_id'=>$request_id)));
        return $result;
    }
}
