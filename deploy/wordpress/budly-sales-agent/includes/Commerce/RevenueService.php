<?php
namespace Budly\Commerce;
use Budly\SecureMemory\Config;
if(!defined('ABSPATH')){exit;}
final class RevenueService{
 private $repo;public function __construct(CommerceRepository $repo){$this->repo=$repo;}
 public function rebuild_day($date){foreach($this->repo->currencies_for_day($date) as $currency){$events=$this->repo->events_for_day($date,$currency);$totals=array('orders_count'=>0,'gross_amount'=>'0.000000','discount_amount'=>'0.000000','shipping_amount'=>'0.000000','tax_amount'=>'0.000000','refund_amount'=>'0.000000','net_amount'=>'0.000000','attributed_amount'=>'0.000000','unattributed_amount'=>'0.000000');$orders=array();foreach($events as $event){if(in_array($event['event_type'],array('payment_completed','order_completed'),true)&&(float)$event['gross_amount']>0)$orders[$event['order_id']]=true;if(in_array($event['event_type'],array('order_cancelled','order_failed'),true)&&(float)$event['gross_amount']<0)unset($orders[$event['order_id']]);foreach(array('gross_amount','discount_amount','shipping_amount','tax_amount','refund_amount','net_amount') as $amount)$totals[$amount]=self::add($totals[$amount],$event[$amount]);$bucket=$event['attribution_status']==='attributed'?'attributed_amount':'unattributed_amount';$totals[$bucket]=self::add($totals[$bucket],$event['net_amount']);}$totals['orders_count']=count($orders);$this->repo->replace_daily(array_merge(array('revenue_date'=>$date,'currency'=>$currency,'product_id'=>0,'affiliate_id'=>'','source_event_count'=>count($events),'calculated_at'=>current_time('mysql',true),'config_version'=>Config::COMMERCE_CONFIG_VERSION),$totals));}}
 private static function add($a,$b){return function_exists('bcadd')?bcadd((string)$a,(string)$b,6):number_format((float)$a+(float)$b,6,'.','');}
}
