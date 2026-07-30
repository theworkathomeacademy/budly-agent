<?php
namespace Budly\SecureMemory\Security;
use Budly\SecureMemory\Errors;use Budly\SecureMemory\Response;
if(!defined('ABSPATH')){exit;}
final class RequestSecurity{
 public static function before($result,$server,$request){if(strpos($request->get_route(),'/budly-identity/v1/')!==0)return$result;if(!is_ssl())return Response::error(Errors::INVALID_REQUEST,'Secure HTTPS is required.',400);$origin=$request->get_header('Origin');if($origin){$origin_host=wp_parse_url($origin,PHP_URL_HOST);$site_host=wp_parse_url(home_url('/'),PHP_URL_HOST);if(!$origin_host||!$site_host||!hash_equals(strtolower($site_host),strtolower($origin_host)))return Response::error(Errors::CSRF_VALIDATION_FAILED,'Cross-origin requests are not allowed.',403);}return$result;}
 public static function after($response,$server,$request){if(strpos($request->get_route(),'/budly-identity/v1/')!==0)return$response;if($response instanceof \WP_REST_Response){$response->header('Cache-Control','no-store, private, max-age=0');$response->header('Pragma','no-cache');$response->header('X-Content-Type-Options','nosniff');$response->header('Referrer-Policy','no-referrer');$response->header('X-Frame-Options','DENY');}return$response;}
}
