<?php
require_once __DIR__ . '/php/wnb_membership_integration.php';

$css = CCC\WNB\Membership_Entitlements::get_membership_css();
$card_none = CCC\WNB\get_account_dashboard_card(10);
$card_pass = CCC\WNB\get_account_dashboard_card(9);
$orders[1]->status = 'cancelled';
$orders[0]->status = 'active';
$card_member = CCC\WNB\get_account_dashboard_card(7);
$orders[1]->status = 'active';
$card_elite = CCC\WNB\get_account_dashboard_card(7);
$order_pass = new Order(1105, 9, 1047, 'processing');
$welcome_pass = CCC\WNB\get_post_order_welcome($order_pass);

$html = '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>' . $css . '</style></head><body style="margin:0;padding:20px;background:#f5f5f5;">'
  . '<div class="woocommerce-MyAccount-content" style="max-width:1000px;margin:0 auto;box-sizing:border-box;">'
  . '<h2>None Card</h2>' . $card_none
  . '<h2>Pass Card</h2>' . $card_pass
  . '<h2>Member Card</h2>' . $card_member
  . '<h2>Elite Card</h2>' . $card_elite
  . '<h2>Order Welcome</h2>' . $welcome_pass
  . '</div></body></html>';

file_put_contents(__DIR__ . '/test_account_responsive.html', $html);
echo "HTML written successfully (" . strlen($html) . " bytes)\n";
