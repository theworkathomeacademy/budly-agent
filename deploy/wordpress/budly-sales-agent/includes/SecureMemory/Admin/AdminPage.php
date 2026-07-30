<?php
namespace Budly\SecureMemory\Admin;
use Budly\SecureMemory\Config;
if(!defined('ABSPATH')){exit;}
final class AdminPage{
 public static function register(){add_management_page('Budly Secure Memory','Budly Secure Memory','manage_options','budly-secure-memory',array(__CLASS__,'render'));}
 public static function enqueue($hook){if($hook!=='tools_page_budly-secure-memory')return;wp_enqueue_script('budly-secure-memory-admin',BUDLY_SALES_URL.'assets/budly-secure-memory-admin.js',array(),BUDLY_SALES_VERSION,true);wp_localize_script('budly-secure-memory-admin','BudlyMemoryAdmin',array('restBase'=>esc_url_raw(rest_url(Config::API_NAMESPACE)),'nonce'=>wp_create_nonce('wp_rest')));}
 public static function render(){if(!current_user_can('manage_options'))wp_die(esc_html__('You do not have permission to view this page.','budly'));?>
 <div class="wrap" data-budly-memory-admin><h1>Budly Secure Memory</h1><p>Operational controls display aggregate metrics and identifiers only. Raw session tokens and customer memory are never shown here.</p><div data-admin-status>Loading secure-memory health…</div>
 <h2>Session revocation</h2><form data-revoke-session><label>Session ID <input name="session_id" required></label> <?php submit_button('Revoke session','secondary','submit',false);?></form><form data-revoke-all><label>Customer public ID <input name="customer_id" required></label> <?php submit_button('Revoke all customer sessions','secondary','submit',false);?></form>
 <h2>Email delivery test</h2><form data-test-email><label>Test recipient <input name="email" type="email" required></label> <?php submit_button('Send transactional test','secondary','submit',false);?></form>
 <h2>Cleanup</h2><p>Cleanup removes only expired temporary authentication, session, context, and idempotency records. It preserves customer memory, consent, consent history, and audit records.</p><form data-run-cleanup><?php submit_button('Run bounded cleanup now','secondary','submit',false);?></form>
 <h2>Governed decisions</h2><p>Active rule versions, recent qualifications, recommendations, no-match outcomes, and escalations are available through the protected administration API.</p><div data-admin-decisions>Loading governed decision evidence…</div>
 <h2>Recent security audit</h2><div data-admin-audit>Loading audit events…</div><p data-admin-message role="status" aria-live="polite"></p></div><?php }
}
