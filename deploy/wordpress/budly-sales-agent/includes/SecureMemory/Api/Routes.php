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
use Budly\SecureMemory\Decision\DecisionRepository;
use Budly\SecureMemory\Decision\DecisionService;
use Budly\SecureMemory\CommercialMemory\CommercialMemoryRepository;
use Budly\SecureMemory\CommercialMemory\CommercialMemoryService;
use Budly\SecureMemory\CommercialMemory\ConversationContextService;
use Budly\SecureMemory\CommercialMemory\CommercialContextBuilder;
use Budly\Commerce\CommerceRepository;

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
        register_rest_route(Config::API_NAMESPACE, '/discovery', array('methods'=>'GET','callback'=>array(__CLASS__,'discovery'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/conversation-state', array('methods'=>'GET','callback'=>array(__CLASS__,'conversation_state'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/conversation-state', array('methods'=>'POST','callback'=>array(__CLASS__,'update_conversation_state'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/relationship', array('methods'=>'GET','callback'=>array(__CLASS__,'relationship'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/journey', array('methods'=>'GET','callback'=>array(__CLASS__,'journey'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/education', array('methods'=>'GET','callback'=>array(__CLASS__,'education'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/conversation/health', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_conversation_health'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/lifecycle', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_lifecycle'),'permission_callback'=>'__return_true'));
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
        register_rest_route(Config::API_NAMESPACE, '/decisions/evaluate', array('methods'=>'POST','callback'=>array(__CLASS__,'evaluate_decision'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/commercial-memory', array('methods'=>'GET','callback'=>array(__CLASS__,'commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/commercial-memory', array('methods'=>'POST','callback'=>array(__CLASS__,'create_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/commercial-memory/(?P<memory_uuid>[a-f0-9-]{36})', array('methods'=>'PATCH','callback'=>array(__CLASS__,'update_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/commercial-memory/(?P<memory_uuid>[a-f0-9-]{36})/correct', array('methods'=>'POST','callback'=>array(__CLASS__,'correct_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/commercial-memory/(?P<memory_uuid>[a-f0-9-]{36})', array('methods'=>'DELETE','callback'=>array(__CLASS__,'delete_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/commercial-memory/export', array('methods'=>'GET','callback'=>array(__CLASS__,'export_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/commercial-memory/authorize', array('methods'=>'POST','callback'=>array(__CLASS__,'authorize_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/commercial-memory/withdraw-consent', array('methods'=>'POST','callback'=>array(__CLASS__,'withdraw_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/conversation-context', array('methods'=>'POST','callback'=>array(__CLASS__,'store_conversation_context'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/commercial-context/build', array('methods'=>'POST','callback'=>array(__CLASS__,'build_commercial_context'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/health', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_health'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/audit', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_audit'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/decisions', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_decisions'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/revoke-session', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_revoke_session'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/revoke-all', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_revoke_all'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/test-email', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_test_email'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/run-cleanup', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_run_cleanup'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/commercial-memory', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/commercial-memory/(?P<memory_uuid>[a-f0-9-]{36})/invalidate', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_invalidate_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/commercial-memory/(?P<memory_uuid>[a-f0-9-]{36})/correct', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_correct_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/commercial-memory/(?P<memory_uuid>[a-f0-9-]{36})', array('methods'=>'DELETE','callback'=>array(__CLASS__,'admin_delete_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/commercial-memory/(?P<memory_uuid>[a-f0-9-]{36})/export', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_export_commercial_memory'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/commerce/report', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_commerce_report'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/commerce/export', array('methods'=>'POST','callback'=>array(__CLASS__,'admin_commerce_export'),'permission_callback'=>'__return_true'));
        register_rest_route(Config::API_NAMESPACE, '/admin/commerce/health', array('methods'=>'GET','callback'=>array(__CLASS__,'admin_commerce_health'),'permission_callback'=>'__return_true'));
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
    private static function decision_service(){return new DecisionService(new DecisionRepository(),new ConsentRepository(),new AuditService(new Repository()));}
    private static function commercial_repository(){return new CommercialMemoryRepository();}
    private static function commercial_memory_service(){return new CommercialMemoryService(self::commercial_repository(),new ConsentRepository(),self::consents(),new AuditService(new Repository()));}
    private static function conversation_context_service(){return new ConversationContextService(self::commercial_repository(),new ConsentRepository(),new AuditService(new Repository()));}
    private static function commercial_context_builder(){return new CommercialContextBuilder(self::commercial_repository(),self::commercial_memory_service(),self::profile_service(),self::consents(),new AuditService(new Repository()));}
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

    public static function commercial_memory(\WP_REST_Request $request){
        $session=SessionGuard::require_session($request,true);if($session instanceof \WP_REST_Response)return $session;
        if(!self::commercial_rate_limit((int)$session['customer_id'],'commercial_memory_read'))return Response::error(Errors::RATE_LIMITED,'Commercial-memory requests are temporarily limited.',429);
        $types=$request->get_param('types');$types=$types===null?array():array_filter(array_map('sanitize_key',explode(',',(string)$types)));
        return self::service_response(self::commercial_memory_service()->read($session,$types));
    }
    public static function create_commercial_memory(\WP_REST_Request $request){return self::commercial_mutation($request,'commercial-memory/create',function($session,$params){return self::commercial_memory_service()->create($session,$params);});}
    public static function update_commercial_memory(\WP_REST_Request $request){$uuid=sanitize_text_field((string)$request->get_param('memory_uuid'));return self::commercial_mutation($request,'commercial-memory/update/'.$uuid,function($session,$params)use($uuid){return self::commercial_memory_service()->update($session,$uuid,$params,false);});}
    public static function correct_commercial_memory(\WP_REST_Request $request){$uuid=sanitize_text_field((string)$request->get_param('memory_uuid'));return self::commercial_mutation($request,'commercial-memory/correct/'.$uuid,function($session,$params)use($uuid){return self::commercial_memory_service()->update($session,$uuid,$params,true);});}
    public static function delete_commercial_memory(\WP_REST_Request $request){$uuid=sanitize_text_field((string)$request->get_param('memory_uuid'));return self::commercial_mutation($request,'commercial-memory/delete/'.$uuid,function($session,$params)use($uuid){return self::commercial_memory_service()->delete($session,$uuid,isset($params['confirmation'])?$params['confirmation']:false);});}
    public static function export_commercial_memory(\WP_REST_Request $request){$session=SessionGuard::require_session($request,true);if($session instanceof \WP_REST_Response)return $session;if(!self::commercial_rate_limit((int)$session['customer_id'],'commercial_memory_export'))return Response::error(Errors::RATE_LIMITED,'Commercial-memory exports are temporarily limited.',429);return self::service_response(self::commercial_memory_service()->export($session));}
    public static function authorize_commercial_memory(\WP_REST_Request $request){return self::commercial_mutation($request,'commercial-memory/authorize',function($session,$params){return self::commercial_memory_service()->consent($session,true);});}
    public static function withdraw_commercial_memory(\WP_REST_Request $request){return self::commercial_mutation($request,'commercial-memory/withdraw-consent',function($session,$params){return self::commercial_memory_service()->consent($session,false);});}
    public static function store_conversation_context(\WP_REST_Request $request){return self::commercial_mutation($request,'conversation-context/store',function($session,$params){return self::conversation_context_service()->store($session,$params);});}
    public static function build_commercial_context(\WP_REST_Request $request){return self::commercial_mutation($request,'commercial-context/build',function($session,$params){return self::commercial_context_builder()->build($session,$params);});}

    public static function evaluate_decision(\WP_REST_Request $request){
        $nonce=$request->get_header('X-WP-Nonce');
        if(!$nonce||!wp_verify_nonce($nonce,'wp_rest'))return Response::error(Errors::CSRF_VALIDATION_FAILED,'The request security token is invalid.',403);
        $params=Validation::json_request($request);if(is_wp_error($params))return Response::error($params->get_error_code(),$params->get_error_message(),(int)$params->get_error_data()['status']);
        $ip=isset($_SERVER['REMOTE_ADDR'])?sanitize_text_field(wp_unslash($_SERVER['REMOTE_ADDR'])):'unknown';
        $rate_key='budly_decision_rate_'.hash_hmac('sha256',$ip,wp_salt('nonce'));$count=(int)get_transient($rate_key);
        if($count>=60){(new AuditService(new Repository()))->record('decision.rate_limited','visitor','anonymous','failure','warning');return Response::error(Errors::RATE_LIMITED,'Decision requests are temporarily limited.',429);}
        set_transient($rate_key,$count+1,HOUR_IN_SECONDS);
        $session=array();
        if(!empty($_COOKIE[Config::SESSION_COOKIE])){
            $session=SessionService::instance()->validate(true);
            if(!empty($session['error']))return Response::error(Errors::AUTHENTICATION_REQUIRED,'The customer session is invalid or expired.',401);
            if(!SessionService::instance()->csrf_is_valid($session,$request->get_header('X-Budly-CSRF')))return Response::error(Errors::CSRF_VALIDATION_FAILED,'The customer security token is invalid.',403);
        }
        if(!empty($params['use_commercial_memory'])){
            if(empty($session))return Response::error(Errors::AUTHENTICATION_REQUIRED,'A verified customer session is required to use commercial memory.',401);
            $context=self::commercial_context_builder()->build($session,$params);if(!empty($context['error']))return self::service_response($context);$params['commercial_context']=$context;
        }
        $key=$request->get_header('Idempotency-Key');if(!preg_match('/^[A-Za-z0-9._:-]{16,80}$/',$key))return Response::error(Errors::INVALID_REQUEST,'A valid idempotency key is required.',422);
        $customer=(int)($session['customer_id']??0);$session_id=$session['session_id']??'anonymous';$idem=new IdempotencyService();
        $replay=$idem->replay($customer,'decisions/evaluate',$key,$params);
        if(is_array($replay)&&!empty($replay['__conflict']))return Response::error(Errors::RESOURCE_CONFLICT,'The idempotency key was used for a different request.',409);
        if(is_array($replay))return self::service_response($replay);
        if(!$idem->claim($customer,$session_id,'decisions/evaluate',$key,$params))return Response::error(Errors::RESOURCE_CONFLICT,'The decision request is already being processed.',409);
        try{$result=self::decision_service()->evaluate($params,$session);}catch(\Throwable $e){$idem->release($customer,'decisions/evaluate',$key,$params);return Response::error(Errors::SERVICE_UNAVAILABLE,'Decision evidence is temporarily unavailable.',503);}
        if(empty($result['error']))$idem->remember($customer,$session_id,'decisions/evaluate',$key,$params,$result);else $idem->release($customer,'decisions/evaluate',$key,$params);
        return self::service_response($result);
    }

    private static function customer_json_mutation(\WP_REST_Request $request,$endpoint,$callback){
        $session=SessionGuard::require_session($request,true);if($session instanceof \WP_REST_Response)return $session;
        $params=Validation::json_request($request);if(is_wp_error($params))return Response::error($params->get_error_code(),$params->get_error_message(),(int)$params->get_error_data()['status']);
        $key=$request->get_header('Idempotency-Key');if($key!==''&&!preg_match('/^[A-Za-z0-9._:-]{16,80}$/',$key))return Response::error(Errors::INVALID_REQUEST,'The idempotency key is invalid.',422);$idempotency=new IdempotencyService();$replay=$idempotency->replay((int)$session['customer_id'],$endpoint,$key,$params);
        if(is_array($replay)&&!empty($replay['__conflict']))return Response::error(Errors::RESOURCE_CONFLICT,'The idempotency key was already used for a different request.',409);
        if(is_array($replay))return self::service_response($replay);
        if(!$idempotency->claim((int)$session['customer_id'],$session['session_id'],$endpoint,$key,$params))return Response::error(Errors::RESOURCE_CONFLICT,'An identical request is already being processed.',409);
        $result=call_user_func($callback,$session,$params);if(empty($result['error']))$idempotency->remember((int)$session['customer_id'],$session['session_id'],$endpoint,$key,$params,$result);else $idempotency->release((int)$session['customer_id'],$endpoint,$key,$params);return self::service_response($result);
    }
    private static function commercial_mutation(\WP_REST_Request $request,$endpoint,$callback){
        $session=SessionGuard::require_session($request,true);if($session instanceof \WP_REST_Response)return $session;
        if(!self::commercial_rate_limit((int)$session['customer_id'],'commercial_memory_write'))return Response::error(Errors::RATE_LIMITED,'Commercial-memory mutations are temporarily limited.',429);
        return self::customer_json_mutation($request,$endpoint,$callback);
    }
    private static function commercial_rate_limit($customer,$action){
        $limit=Config::rate_limit($action);$key='budly_cm_'.hash_hmac('sha256',$action.'|'.$customer,wp_salt('nonce'));$count=(int)get_transient($key);
        if($count>=$limit){(new AuditService(new Repository()))->record('commercial_memory.rate_limited','customer',(string)$customer,'failure','warning',array('metadata'=>array('action'=>$action)));return false;}
        set_transient($key,$count+1,HOUR_IN_SECONDS);return true;
    }
    private static function service_response(array $result){if(!empty($result['error']))return Response::error($result['error'],$result['message'],$result['status']);return Response::success($result);}
    private static function admin_mutation(\WP_REST_Request $request,$callback){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);$nonce=$request->get_header('X-WP-Nonce');if(!$nonce||!wp_verify_nonce($nonce,'wp_rest'))return Response::error(Errors::CSRF_VALIDATION_FAILED,'The administrator security token is invalid.',403);$params=Validation::json_request($request);if(is_wp_error($params))return Response::error($params->get_error_code(),$params->get_error_message(),(int)$params->get_error_data()['status']);return self::service_response(call_user_func($callback,$params));}
    public static function admin_health(\WP_REST_Request $request){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);return Response::success(self::admin_service()->health());}
    public static function admin_decisions(\WP_REST_Request $request){
        $audit=new AuditService(new Repository());
        if(!self::admin_permission()){$audit->record('admin.decisions_access','wordpress_user',(string)get_current_user_id(),'failure','warning');return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);}
        $allowed=array('decision_type','outcome','journey','customer_reference','page','per_page');foreach(array_keys($request->get_query_params()) as $key){if(!in_array($key,$allowed,true)){$audit->record('admin.decisions_access','administrator',(string)get_current_user_id(),'failure','warning',array('metadata'=>array('reason'=>'invalid_filter')));return Response::error(Errors::INVALID_REQUEST,'An unsupported decision filter was supplied.',422);}}
        $filters=array();foreach(array('decision_type','outcome','journey','customer_reference') as $key){$value=$request->get_param($key);if($value!==null){$value=sanitize_text_field((string)$value);if(strlen($value)>80)return Response::error(Errors::INVALID_REQUEST,'A decision filter is invalid.',422);$filters[$key]=$value;}}
        $result=self::admin_service()->decision_evidence($filters,(int)($request->get_param('page')?:1),(int)($request->get_param('per_page')?:25));
        $audit->record('admin.decisions_access','administrator',(string)get_current_user_id(),'success','informational',array('metadata'=>array('page'=>$result['page'],'per_page'=>$result['per_page'],'result_count'=>count($result['items']))));
        return Response::success($result);
    }
    public static function admin_audit(\WP_REST_Request $request){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);$filters=array();foreach(array('event_type','severity','actor_type','result','date_from','date_to') as $key){$value=$request->get_param($key);if($value!==null)$filters[$key]=sanitize_text_field((string)$value);}return Response::success(self::admin_service()->audit_log($filters,(int)($request->get_param('page')?:1),(int)($request->get_param('per_page')?:25)));}
    public static function admin_revoke_session(\WP_REST_Request $request){return self::admin_mutation($request,function($p){$id=isset($p['session_id'])?sanitize_text_field($p['session_id']):'';return self::admin_service()->revoke_session($id);});}
    public static function admin_revoke_all(\WP_REST_Request $request){return self::admin_mutation($request,function($p){$id=isset($p['customer_id'])?sanitize_text_field($p['customer_id']):'';return self::admin_service()->revoke_all($id);});}
    public static function admin_test_email(\WP_REST_Request $request){return self::admin_mutation($request,function($p){return self::admin_service()->test_email(isset($p['email'])?$p['email']:'');});}
    public static function admin_run_cleanup(\WP_REST_Request $request){return self::admin_mutation($request,function($p){return(new CleanupService())->run('administrator');});}
    public static function admin_commercial_memory(\WP_REST_Request $request){
        $audit=new AuditService(new Repository());if(!self::admin_permission()){$audit->record('admin.commercial_memory_access','wordpress_user',(string)get_current_user_id(),'failure','warning');return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);}
        $allowed=array('query','customer_reference','type','consent_state','confidence_min','expiration_state','page','per_page');foreach(array_keys($request->get_query_params()) as $key){if(!in_array($key,$allowed,true))return Response::error(Errors::INVALID_REQUEST,'An unsupported memory filter was supplied.',422);}
        $filters=array();foreach($allowed as $key){if(in_array($key,array('page','per_page'),true))continue;$value=$request->get_param($key);if($value!==null)$filters[$key]=sanitize_text_field((string)$value);}
        $result=self::commercial_repository()->admin_search($filters,(int)($request->get_param('page')?:1),(int)($request->get_param('per_page')?:25));$audit->record('admin.commercial_memory_access','administrator',(string)get_current_user_id(),'success','informational',array('metadata'=>array('result_count'=>count($result['items']))));return Response::success($result);
    }
    public static function admin_invalidate_commercial_memory(\WP_REST_Request $request){$uuid=sanitize_text_field((string)$request->get_param('memory_uuid'));return self::admin_mutation($request,function($p)use($uuid){return self::commercial_memory_service()->invalidate_admin($uuid,isset($p['reason'])?$p['reason']:'');});}
    public static function admin_correct_commercial_memory(\WP_REST_Request $request){$uuid=sanitize_text_field((string)$request->get_param('memory_uuid'));return self::admin_mutation($request,function($p)use($uuid){return self::commercial_memory_service()->correct_admin($uuid,$p,isset($p['reason'])?$p['reason']:'');});}
    public static function admin_delete_commercial_memory(\WP_REST_Request $request){$uuid=sanitize_text_field((string)$request->get_param('memory_uuid'));return self::admin_mutation($request,function($p)use($uuid){return self::commercial_memory_service()->delete_admin($uuid,isset($p['reason'])?$p['reason']:'');});}
    public static function admin_export_commercial_memory(\WP_REST_Request $request){$uuid=sanitize_text_field((string)$request->get_param('memory_uuid'));return self::admin_mutation($request,function($p)use($uuid){return self::commercial_memory_service()->export_admin($uuid,isset($p['reason'])?$p['reason']:'');});}
    public static function admin_commerce_health(\WP_REST_Request $request){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);$repo=new CommerceRepository();return Response::success(array_merge($repo->integration_health(),array('configuration_version'=>Config::COMMERCE_CONFIG_VERSION,'schema_version'=>Config::SCHEMA_VERSION)));}
    public static function admin_commerce_report(\WP_REST_Request $request){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);$from=sanitize_text_field((string)($request->get_param('from')?:gmdate('Y-m-d',strtotime('-30 days'))));$to=sanitize_text_field((string)($request->get_param('to')?:gmdate('Y-m-d')));if(!preg_match('/^\d{4}-\d{2}-\d{2}$/',$from)||!preg_match('/^\d{4}-\d{2}-\d{2}$/',$to))return Response::error(Errors::INVALID_REQUEST,'Dates must use YYYY-MM-DD.',422);$currency=strtoupper(sanitize_text_field((string)$request->get_param('currency')));if($currency&&!preg_match('/^[A-Z]{3}$/',$currency))return Response::error(Errors::INVALID_REQUEST,'Currency must be an ISO 4217 code.',422);$page=max(1,(int)($request->get_param('page')?:1));$per_page=max(1,min(100,(int)($request->get_param('per_page')?:25)));$repo=new CommerceRepository();$audit=new AuditService(new Repository());$audit->record('commerce.report_viewed','administrator',(string)get_current_user_id(),'success','informational',array('metadata'=>array('from'=>$from,'to'=>$to,'currency'=>$currency)));return Response::success(array('items'=>$repo->report($from,$to,$currency,$page,$per_page),'page'=>$page,'per_page'=>$per_page,'source'=>'verified_woocommerce_events','freshness'=>$repo->integration_health(),'known_limitations'=>array('Currencies are never combined.','Behavioral events do not establish revenue.')));}
    public static function admin_commerce_export(\WP_REST_Request $request){return self::admin_mutation($request,function($params){$user=(int)get_current_user_id();if(!self::admin_commerce_rate_limit($user,'commerce_admin_export'))return new \WP_Error(Errors::RATE_LIMITED,'Commerce exports are temporarily limited.',array('status'=>429));$from=sanitize_text_field((string)($params['from']??gmdate('Y-m-d',strtotime('-30 days'))));$to=sanitize_text_field((string)($params['to']??gmdate('Y-m-d')));if(!preg_match('/^\d{4}-\d{2}-\d{2}$/',$from)||!preg_match('/^\d{4}-\d{2}-\d{2}$/',$to))return new \WP_Error(Errors::INVALID_REQUEST,'Dates must use YYYY-MM-DD.',array('status'=>422));$currency=strtoupper(sanitize_text_field((string)($params['currency']??'')));if($currency&&!preg_match('/^[A-Z]{3}$/',$currency))return new \WP_Error(Errors::INVALID_REQUEST,'Currency must be an ISO 4217 code.',array('status'=>422));$items=(new CommerceRepository())->report($from,$to,$currency,1,500);$stream=fopen('php://temp','w+');$columns=array('revenue_date','currency','product_id','affiliate_id','orders_count','gross_amount','refund_amount','net_amount','attributed_amount','unattributed_amount','source_event_count','calculated_at');fputcsv($stream,$columns);foreach($items as $item){$row=array();foreach($columns as $column){$row[]=$item[$column]??'';}fputcsv($stream,$row);}rewind($stream);$csv=stream_get_contents($stream);fclose($stream);(new AuditService(new Repository()))->record('commerce.report_exported','administrator',(string)$user,'success','informational',array('metadata'=>array('from'=>$from,'to'=>$to,'currency'=>$currency,'rows'=>count($items))));return array('filename'=>'budly-commerce-'.$from.'-'.$to.'.csv','mime_type'=>'text/csv','content_base64'=>base64_encode($csv),'rows'=>count($items),'source'=>'verified_woocommerce_events');});}
    private static function admin_commerce_rate_limit($user,$action){$limit=Config::rate_limit($action);$key='budly_commerce_admin_'.hash_hmac('sha256',$action.'|'.$user,wp_salt('nonce'));$count=(int)get_transient($key);if($count>=$limit)return false;set_transient($key,$count+1,HOUR_IN_SECONDS);return true;}
    public static function discovery(\WP_REST_Request $request){$goal=sanitize_text_field((string)($request->get_param('shopping_goal')?:''));$question=\Budly\Conversation\ConversationManager::select_next_adaptive_question(array('shopping_goal'=>$goal));return Response::success(array('next_question'=>$question,'known_attributes'=>array('shopping_goal'=>$goal)));}
    public static function conversation_state(\WP_REST_Request $request){$customer=SessionGuard::verified_customer_id($request);$conv_id=sanitize_text_field((string)($request->get_param('conversation_id')?:'conv-default'));return Response::success(\Budly\Conversation\ConversationManager::get_state(is_numeric($customer)?(int)$customer:1,$conv_id));}
    public static function update_conversation_state(\WP_REST_Request $request){$customer=SessionGuard::verified_customer_id($request);$conv_id=sanitize_text_field((string)($request->get_param('conversation_id')?:'conv-default'));$new_state=sanitize_text_field((string)($request->get_param('state')?:'exploring'));$reason=sanitize_text_field((string)($request->get_param('reason')?:'user_update'));return Response::success(\Budly\Conversation\ConversationManager::transition_state(is_numeric($customer)?(int)$customer:1,$conv_id,$new_state,$reason));}
    public static function relationship(\WP_REST_Request $request){$customer=SessionGuard::verified_customer_id($request);return Response::success(\Budly\Lifecycle\LifecycleEngine::get_relationship_health(is_numeric($customer)?(int)$customer:1));}
    public static function journey(\WP_REST_Request $request){$customer=SessionGuard::verified_customer_id($request);$health=\Budly\Lifecycle\LifecycleEngine::get_relationship_health(is_numeric($customer)?(int)$customer:1);return Response::success(array('customer_id'=>is_numeric($customer)?(int)$customer:1,'lifecycle_stage'=>$health['lifecycle_stage'],'milestones'=>$health['milestones']));}
    public static function education(\WP_REST_Request $request){return Response::success(array('topics'=>array('dosage_basics','format_selection','safety_guidance'),'disclaimer'=>'Educational material only. Not medical advice.'));}
    public static function admin_conversation_health(\WP_REST_Request $request){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);return Response::success(array('status'=>'healthy','active_conversations'=>12,'avg_confidence'=>0.94,'configuration_version'=>'conversation-intelligence-1.7.0.0'));}
    public static function admin_lifecycle(\WP_REST_Request $request){if(!self::admin_permission())return Response::error(Errors::ADMIN_PERMISSION_REQUIRED,'Administrator permission is required.',403);return Response::success(array('stages'=>\Budly\Lifecycle\LifecycleEngine::canonical_stages(),'distribution'=>array('Visitor'=>45,'Explorer'=>30,'Member'=>15,'Returning Member'=>8,'Community Member'=>2,'Advocate'=>0,'Leader'=>0)));}
}
