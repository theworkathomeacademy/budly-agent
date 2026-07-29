<?php
namespace Budly\SecureMemory\Api;

use Budly\SecureMemory\Audit\AuditService;
use Budly\SecureMemory\Config;
use Budly\SecureMemory\Database\Repository;
use Budly\SecureMemory\Email\WordPressMailTransport;
use Budly\SecureMemory\Errors;
use Budly\SecureMemory\Response;
use Budly\SecureMemory\Validation;
use Budly\SecureMemory\Verification\VerificationRepository;
use Budly\SecureMemory\Verification\VerificationService;
use Budly\SecureMemory\Sessions\SessionGuard;
use Budly\SecureMemory\Sessions\SessionService;
use Budly\SecureMemory\Consent\ConsentRepository;
use Budly\SecureMemory\Consent\ConsentService;
use Budly\SecureMemory\Authorization\AgentRegistry;
use Budly\SecureMemory\Idempotency\IdempotencyService;
use Budly\SecureMemory\Memory\MemoryRepository;
use Budly\SecureMemory\Memory\MemoryService;
use Budly\SecureMemory\Profile\ProfileRepository;
use Budly\SecureMemory\Profile\ProfileService;
use Budly\SecureMemory\Profile\PreferenceService;
use Budly\SecureMemory\Admin\AdminRepository;
use Budly\SecureMemory\Admin\AdminService;
use Budly\SecureMemory\Sessions\SessionRepository;
use Budly\SecureMemory\Cleanup\CleanupService;

if (!defined('ABSPATH')) { exit; }

final class Routes {
    public static function register() {
        register_rest_route(Config::API_NAMESPACE, '/auth/request-code', array('methods'=>'POST','callback'=>array(__CLASS__,'request_code'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/auth/verify', array('methods'=>'POST','callback'=>array(__CLASS__,'verify'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/auth/session', array('methods'=>'GET','callback'=>array(__CLASS__,'session'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/auth/logout', array('methods'=>'POST','callback'=>array(__CLASS__,'logout'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/consent', array('methods'=>'GET','callback'=>array(__CLASS__,'consent'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/consent', array('methods'=>'PATCH','callback'=>array(__CLASS__,'update_consent'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/identity', array('methods'=>'GET','callback'=>array(__CLASS__,'identity'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/profile', array('methods'=>'GET','callback'=>array(__CLASS__,'profile'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/profile', array('methods'=>'PATCH','callback'=>array(__CLASS__,'update_profile'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/preferences', array('methods'=>'GET','callback'=>array(__CLASS__,'preferences'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/preferences', array('methods'=>'PATCH','callback'=>array(__CLASS__,'update_preferences'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/memory/preview', array('methods'=>'GET','callback'=>array(__CLASS__,'memory_preview'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/memory/use', array('methods'=>'POST','callback'=>array(__CLASS__,'memory_use'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/memory/start-fresh', array('methods'=>'POST','callback'=>array(__CLASS__,'start_fresh'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/memory/shared', array('methods'=>'GET','callback'=>array(__CLASS__,'shared_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/memory/agent/(?P<namespace>[a-z0-9_-]+)', array('methods'=>'GET','callback'=>array(__CLASS__,'agent_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/memory/summary', array('methods'=>'POST','callback'=>array(__CLASS__,'store_summary'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/memory/(?P<memory_id>mem_[A-Za-z0-9_-]+)', array('methods'=>'PATCH','callback'=>array(__CLASS__,'correct_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/memory/(?P<memory_id>mem_[A-Za-z0-9_-]+)', array('methods'=>'DELETE','callback'=>array(__CLASS__,'delete_memory_item'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/memory/export', array('methods'=>'GET','callback'=>array(__CLASS__,'export_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/memory', array('methods'=>'DELETE','callback'=>array(__CLASS__,'delete_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/health', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_health'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/audit', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_audit'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/decisions', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_decisions'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/revoke-session', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_revoke_session'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/revoke-all', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_revoke_all'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/test-email', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_test_email'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/run-cleanup', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_run_cleanup'),'permission_callback'=>'__return_true'));
    }

    private static function verification() {
        return new VerificationService(new VerificationRepository(), new AuditService(new Repository()), new WordPressMailTransport());
    }

    private static function consents() {
        return new ConsentService(new ConsentRepository(), new AuditService(new Repository()));
    }

    private static function profile_service() { return new ProfileService(new ProfileRepository(), self::consents(), new AuditService(new Repository())); }
    private static function preference_service() { return new PreferenceService(new ProfileRepository(), self::consents(), new AuditService(new Repository())); }
    private static function memory_service() { return new MemoryService(new MemoryRepository(),new ConsentRepository(),self::consents(),new AgentRegistry(),self::profile_service(),SessionService::instance(),new AuditService(new Repository())); }
    private static function admin_service(){return new AdminService(new AdminRepository(),new SessionRepository(),new WordPressMailTransport(),new AuditService(new Repository()));}
    public static function admin_permission(){return current_user_can('manage_options');}

    public static function request_code(\WP_REST_Request $request) {
        if (!is_ssl()) { return Response::error(Errors::INVALID_REQUEST, 'Secure HTTPS is required.', 400); }
        $params = Validation::json_request($request);
        if (is_wp_error($params)) { return Response::error($params->get_error_code(), $params->get_error_message(), (int) $params->get_error_data()['status']); }
        $ip = isset($_SERVER['REMOTE_ADDR']) ? sanitize_text_field(wp_unslash($_SERVER['REMOTE_ADDR'])) : 'unknown';
        $result = self::verification()->request_code(isset($params['email']) ? $params['email'] : '', $ip);
        if (!empty($result['error'])) { return Response::error($result['error'],$result['message'],$result['status']); }
        return Response::success($result);
    }

    public static function verify(\WP_REST_Request $request) {
        if (!is_ssl()) { return Response::error(Errors::INVALID_REQUEST, 'Secure HTTPS is required.', 400); }
        $params = Validation::json_request($request);
        if (is_wp_error($params)) { return Response::error($params->get_error_code(), $params->get_error_message(), (int) $params->get_error_data()['status']); }
        $result = self::verification()->verify(isset($params['request_id'])?$params['request_id']:'', isset($params['code'])?$params['code']:'');
        if (!empty($result['error'])) { return Response::error($result['error'],$result['message'],$result['status']); }
        $session = SessionService::instance()->create((int) $result['customer_id'], Config::DEFAULT_AGENT_ID);
        return Response::success(array('verified'=>true,'session'=>$session));
    }

    public static function session(\WP_REST_Request $request) {
        $session = SessionGuard::require_session($request, false);
        if ($session instanceof \WP_REST_Response) { return $session; }
        return Response::success(array('verified'=>true,'session'=>array(
            'session_id'=>$session['session_id'], 'agent_id'=>$session['agent_id'],
            'idle_expires_at'=>gmdate('c', strtotime($session['idle_expires_at'] . ' UTC')),
            'absolute_expires_at'=>gmdate('c', strtotime($session['absolute_expires_at'] . ' UTC')),
            'csrf_token'=>$session['csrf_token'],
        )));
    }

    public static function logout(\WP_REST_Request $request) {
        $session = SessionGuard::require_session($request, true);
        if ($session instanceof \WP_REST_Response) { return $session; }
        SessionService::instance()->logout($session);
        return Response::success(array('logged_out'=>true));
    }

    public static function consent(\WP_REST_Request $request) {
        $session = SessionGuard::require_session($request, false);
        if ($session instanceof \WP_REST_Response) { return $session; }
        return Response::success(self::consents()->read((int) $session['customer_id']));
    }

    public static function update_consent(\WP_REST_Request $request) {
        $session = SessionGuard::require_session($request, true);
        if ($session instanceof \WP_REST_Response) { return $session; }
        $params = Validation::json_request($request);
        if (is_wp_error($params)) { return Response::error($params->get_error_code(), $params->get_error_message(), (int) $params->get_error_data()['status']); }
        $result = self::consents()->update((int) $session['customer_id'], $params);
        if (!empty($result['error'])) { return Response::error($result['error'],$result['message'],$result['status']); }
        return Response::success($result);
    }

    public static function identity(\WP_REST_Request $request){$session=SessionGuard::require_session($request,false);if($session instanceof \WP_REST_Response)return $session;$profile=self::profile_service()->read((int)$session['customer_id']);if(!$profile)return Response::error(Errors::PROFILE_NOT_FOUND,'The customer profile was not found.',404);return Response::success(array_intersect_key($profile,array_flip(array('customer_id','preferred_name','status','email_verified'))));}
    public static function profile(\WP_REST_Request $request){$session=SessionGuard::require_session($request,false);if($session instanceof \WP_REST_Response)return $session;$result=self::profile_service()->read((int)$session['customer_id']);return $result?Response::success($result):Response::error(Errors::PROFILE_NOT_FOUND,'The customer profile was not found.',404);}
    public static function update_profile(\WP_REST_Request $request){return self::customer_json_mutation($request,'profile/update',function($session,$params){return self::profile_service()->update((int)$session['customer_id'],$params);});}
    public static function preferences(\WP_REST_Request $request){$session=SessionGuard::require_session($request,false);if($session instanceof \WP_REST_Response)return $session;return Response::success(self::preference_service()->read((int)$session['customer_id']));}
    public static function update_preferences(\WP_REST_Request $request){return self::customer_json_mutation($request,'preferences/update',function($session,$params){return self::preference_service()->update((int)$session['customer_id'],$params);});}
    public static function memory_preview(\WP_REST_Request $request){$session=SessionGuard::require_session($request,false);if($session instanceof \WP_REST_Response)return $session;return Response::success(self::memory_service()->preview($session));}
    public static function memory_use(\WP_REST_Request $request){return self::customer_json_mutation($request,'memory/use',function($session,$params){return self::memory_service()->authorize_use($session,$params,false);});}
    public static function start_fresh(\WP_REST_Request $request){return self::customer_json_mutation($request,'memory/start-fresh',function($session,$params){return self::memory_service()->authorize_use($session,$params,true);});}
    public static function shared_memory(\WP_REST_Request $request){$session=SessionGuard::require_session($request,false);if($session instanceof \WP_REST_Response)return $session;return self::service_response(self::memory_service()->shared($session,(string)$request->get_param('conversation_id'),'shared'));}
    public static function agent_memory(\WP_REST_Request $request){$session=SessionGuard::require_session($request,false);if($session instanceof \WP_REST_Response)return $session;$namespace=sanitize_key((string)$request->get_param('namespace'));return self::service_response(self::memory_service()->shared($session,(string)$request->get_param('conversation_id'),$namespace));}
    public static function store_summary(\WP_REST_Request $request){return self::customer_json_mutation($request,'memory/summary',function($session,$params){return self::memory_service()->store($session,$params);});}
    public static function correct_memory(\WP_REST_Request $request){$memory_id=sanitize_text_field((string)$request->get_param('memory_id'));return self::customer_json_mutation($request,'memory/correct/'.$memory_id,function($session,$params)use($memory_id){return self::memory_service()->correct($session,$memory_id,$params);});}
    public static function delete_memory_item(\WP_REST_Request $request){$memory_id=sanitize_text_field((string)$request->get_param('memory_id'));return self::customer_json_mutation($request,'memory/delete/'.$memory_id,function($session,$params)use($memory_id){return self::memory_service()->delete_one($session,$memory_id,isset($params['confirmation'])?$params['confirmation']:false);});}
    public static function export_memory(\WP_REST_Request $request){$session=SessionGuard::require_session($request,false);if($session instanceof \WP_REST_Response)return $session;return Response::success(self::memory_service()->export($session));}
    public static function delete_memory(\WP_REST_Request $request){return self::customer_json_mutation($request,'memory/delete-all',function($session,$params){return self::memory_service()->delete_all($session,$params);});}

    private static function customer_json_mutation(\WP_REST_Request $request,$endpoint,$callback){
        $session=SessionGuard::require_session($request,true);if($session instanceof \WP_REST_Response)return $session;
        $params=Validation::json_request($request);if(is_wp_error($params))return Response::error($params->get_error_code(),$params->get_error_message(),(int)$params->get_error_data()['status']);
        $key=$request->get_header('Idempotency-Key');if($key!==''&&!preg_match('/^[A-Za-z0-9._:-]{16,80}$/',$key))return Response::error(Errors::INVALID_REQUEST,'The idempotency key is invalid.',422);$idempotency=new IdempotencyService();$replay=$idempotency->replay((int)$session['customer_id'],$endpoint,$key,$params);
        if(is_array($replay)&&!empty($replay['__conflict']))return Response::error(Errors::RESOURCE_CONFLICT,'The idempotency key was already used for a different request.',409);
        if(is_array($replay))return self::service_response($replay);
        if(!$idempotency->claim((int)$session['customer_id'],$session['session_id'],$endpoint,$key,$params))return Response::error(Errors::RESOURCE_CONFLICT,'An identical request is already being processed.',409);
        $result=call_user_func($callback,$session,$params);if(empty($result['error']))$idempotency->remember((int)$session['customer_id'],$session['session_id'],$endpoint,$key,$params,$result);else $idempotency->release((int)$session['customer_id'],$endpoint,$key,$params);return self::service_response($result);
    }
    private static function service_response(array $result){if(!empty($result['error']))return Response::error($result['error'],$result['message'],$result['status']);return Response::success($result);}
    private static function admin_mutation(\WP_REST_Request $request,$callback){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);$nonce=$request->get_header('X-WP-Nonce');if(!$nonce||!wp_verify_nonce($nonce,'wp_rest'))return Response::error(Errors::CSRF_VALIDATION_FAILED,'The administrator security token is invalid.',403);$params=Validation::json_request($request);if(is_wp_error($params))return Response::error($params->get_error_code(),$params->get_error_message(),(int)$params->get_error_data()['status']);return self::service_response(call_user_func($callback,$params));}
    public static function admin_health(\WP_REST_Request $request){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);return Response::success(self::admin_service()->health());}
    public static function admin_decisions(\WP_REST_Request $request){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);return Response::success(self::admin_service()->decision_evidence((int)$request->get_param('limit')));}
    public static function admin_audit(\WP_REST_Request $request){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);$filters=array();foreach(array('event_type','severity','actor_type','result','date_from','date_to') as $key){$value=$request->get_param($key);if($value!==null)$filters[$key]=sanitize_text_field((string)$value);}return Response::success(self::admin_service()->audit_log($filters,(int)($request->get_param('page')?:1),(int)($request->get_param('per_page')?:25)));}
    public static function admin_revoke_session(\WP_REST_Request $request){return self::admin_mutation($request,function($p){$id=isset($p['session_id'])?sanitize_text_field($p['session_id']):'';return self::admin_service()->revoke_session($id);});}
    public static function admin_revoke_all(\WP_REST_Request $request){return self::admin_mutation($request,function($p){$id=isset($p['customer_id'])?sanitize_text_field($p['customer_id']):'';return self::admin_service()->revoke_all($id);});}
    public static function admin_test_email(\WP_REST_Request $request){return self::admin_mutation($request,function($p){return self::admin_service()->test_email(isset($p['email'])?$p['email']:'');});}
    public static function admin_run_cleanup(\WP_REST_Request $request){return self::admin_mutation($request,function($p){return(new CleanupService())->run('administrator');});}
}
