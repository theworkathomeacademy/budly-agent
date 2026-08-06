<?php
namespace Budly\Commerce;
use Budly\SecureMemory\Audit\AuditService;
if(!defined('ABSPATH')){exit;}
final class WooCommerceAdapter{
 private $repo;private $audit;private $attribution;private $revenue;
 public function __construct(CommerceRepository $repo,AuditService $audit){$this->repo=$repo;$this->audit=$audit;$this->attribution=new AttributionService($repo,$audit);$this->revenue=new RevenueService($repo);}
 public static function register(){foreach(array('woocommerce_new_order'=>'order_created','woocommerce_payment_complete'=>'payment_completed','woocommerce_order_status_completed'=>'order_completed','woocommerce_order_status_cancelled'=>'order_cancelled','woocommerce_order_status_failed'=>'order_failed','woocommerce_order_refunded'=>'order_refunded') as $hook=>$event){add_action($hook,function($order_id)use($event){self::instance()->ingest($order_id,$event);},20,1);}}
 public static function instance(){static $instance;if(!$instance){$repo=new CommerceRepository();$instance=new self($repo,new AuditService(new \Budly\SecureMemory\Database\Repository()));}return$instance;}
 public function ingest($order_id,$event_type){
  if(!function_exists('wc_get_order'))return array('status'=>'degraded','reason'=>'woocommerce_unavailable');
  $order=wc_get_order((int)$order_id);
  if(!$order){$this->audit->record('commerce.event_rejected','system','woocommerce','failure','warning',array('metadata'=>array('order_id'=>(int)$order_id,'reason'=>'missing_order')));return array('status'=>'rejected','reason'=>'missing_order');}
  $allowed=array('order_created','payment_completed','order_completed','order_cancelled','order_failed','order_refunded');
  if(!in_array($event_type,$allowed,true))return array('status'=>'rejected','reason'=>'unsupported_event');
  $refund_total='0.000000';if($event_type==='order_refunded'){foreach($order->get_refunds() as $refund){$refund_total=self::money((float)$refund_total+abs((float)$refund->get_total()));}}
  $revision=$event_type==='order_refunded'?$refund_total:(string)$order->get_status();
  $key='wc:'.$order->get_id().':'.$event_type.':'.hash('sha256',$revision);
  if($this->repo->event_by_key($key)){$this->audit->record('commerce.event_replay','system','woocommerce','success','informational',array('metadata'=>array('order_id'=>$order->get_id(),'event_type'=>$event_type)));return array('status'=>'duplicate','key'=>$key);}
  $evidence=array('session_id'=>$order->get_meta('_budly_session_id',true),'conversation_id'=>$order->get_meta('_budly_conversation_id',true),'decision_id'=>$order->get_meta('_budly_decision_id',true),'customer_id'=>$order->get_meta('_budly_customer_id',true));
  $link=$this->attribution->resolve($order,$evidence);
  $status=(string)$order->get_status();
  $is_revenue=in_array($event_type,array('payment_completed','order_completed'),true)&&in_array($status,array('processing','completed'),true)&&!$this->repo->recorded_revenue_event($order->get_id());
  $is_refund=$event_type==='order_refunded';
  $is_reversal=in_array($event_type,array('order_cancelled','order_failed'),true);
  $gross=$is_revenue?self::money($order->get_total()):'0.000000';
  $refund=$is_refund?self::money(max(0,(float)$refund_total-(float)$this->repo->recorded_refund_total($order->get_id()))):'0.000000';
  $net=$is_reversal?self::money(-max(0,(float)$this->repo->recorded_net_total($order->get_id()))):self::money((float)$gross-(float)$refund);
  $occurred=$order->get_date_modified()?$order->get_date_modified()->date('Y-m-d H:i:s'):current_time('mysql',true);
  $audit=$this->audit->record('commerce.event_verified','system','woocommerce','success','informational',array('customer_reference'=>(string)$order->get_customer_id(),'conversation_id'=>(string)$evidence['conversation_id'],'metadata'=>array('order_id'=>$order->get_id(),'event_type'=>$event_type)));
  $this->repo->insert_event(array('event_uuid'=>wp_generate_uuid4(),'external_event_key'=>$key,'order_id'=>$order->get_id(),'event_type'=>$event_type,'source'=>'woocommerce','verification_status'=>'verified','customer_id'=>$order->get_customer_id()?:null,'session_id'=>$evidence['session_id']?:null,'conversation_id'=>$evidence['conversation_id']?:null,'decision_id'=>$evidence['decision_id']?:null,'product_id'=>null,'affiliate_id'=>sanitize_text_field((string)$order->get_meta('_budly_affiliate_id',true))?:null,'currency'=>strtoupper((string)$order->get_currency()),'gross_amount'=>$gross,'discount_amount'=>$is_revenue?self::money($order->get_discount_total()):'0.000000','shipping_amount'=>$is_revenue?self::money($order->get_shipping_total()):'0.000000','tax_amount'=>$is_revenue?self::money($order->get_total_tax()):'0.000000','refund_amount'=>$refund,'net_amount'=>$net,'attribution_status'=>$link['attribution_status'],'reconciliation_status'=>$link['resolution_state']==='resolved'?'reconciled':'pending','evidence_json'=>wp_json_encode(array('order_status'=>$order->get_status(),'woocommerce_order_id'=>$order->get_id())),'audit_reference'=>$audit?:'audit_unavailable','source_occurred_at'=>$occurred,'processed_at'=>current_time('mysql',true),'created_at'=>current_time('mysql',true)));
  $this->revenue->rebuild_day(substr($occurred,0,10));return array('status'=>'recorded','key'=>$key);
 }
 private static function money($value){return number_format((float)$value,6,'.','');}
}
