<?php
namespace Budly\SecureMemory\Memory;

use Budly\SecureMemory\Config;

if (!defined('ABSPATH')) { exit; }

final class MemoryPolicy {
    const SUMMARY_FIELDS=array('topic','customer_goal','resolved_questions','open_questions','confirmed_preferences','customer_corrections','next_recommended_step','summary_created_at');
    const SENSITIVE_PATTERNS=array(
        '/\b(?:password|passcode|session[_ -]?token|verification[_ -]?code)\b/i',
        '/\b(?:system prompt|developer message|chain[- ]of[- ]thought|ignore (?:all )?previous)\b/i',
        '/\b(?:diagnosed with|medical diagnosis|social security|passport number|driver.?s license)\b/i',
        '/\b(?:payment card|credit card|debit card|card security code|cvv|cvc)\b/i',
        '/\b(?:\d[ -]*?){13,19}\b/', '/\b\d{3}-\d{2}-\d{4}\b/'
    );
    public static function validate_summary($summary) {
        if(!is_array($summary)||self::bytes($summary)>Config::SUMMARY_MAX_BYTES)return null;
        $clean=array();
        foreach($summary as $key=>$value){
            if(!in_array($key,self::SUMMARY_FIELDS,true))return null;
            if(self::contains_sensitive($value))return null;
            if(in_array($key,array('resolved_questions','open_questions','customer_corrections'),true)){
                if(!is_array($value)||count($value)>Config::SUMMARY_MAX_LIST_ITEMS)return null;$items=array();
                foreach($value as $item){if(!is_string($item)||mb_strlen($item)>Config::SUMMARY_MAX_ITEM_CHARS)return null;$items[]=sanitize_text_field($item);} $clean[$key]=$items;
            } elseif($key==='confirmed_preferences') {
                if(!is_array($value)||count($value)>Config::SUMMARY_MAX_LIST_ITEMS)return null;$prefs=array();
                foreach($value as $k=>$v){if(!is_scalar($v)||mb_strlen((string)$v)>Config::SUMMARY_MAX_ITEM_CHARS)return null;$prefs[sanitize_key($k)]=is_bool($v)?$v:sanitize_text_field((string)$v);} $clean[$key]=$prefs;
            } else {
                if(!is_string($value)||mb_strlen($value)>Config::SUMMARY_MAX_ITEM_CHARS)return null;$clean[$key]=sanitize_text_field($value);
            }
        }
        return $clean;
    }
    public static function contains_sensitive($value){$text=is_string($value)?$value:wp_json_encode($value);foreach(self::SENSITIVE_PATTERNS as $pattern){if(preg_match($pattern,$text))return true;}return false;}
    private static function bytes($value){return strlen(wp_json_encode($value));}
}
