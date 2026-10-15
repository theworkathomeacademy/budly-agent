<?php
/**
 * Phase 3E: Member Account UX Deterministic Test Suite
 */
define( 'ABSPATH', __DIR__ );

// Load test harness
require_once __DIR__ . '/wnb_membership_integration.php';

echo "\n=======================================================\n";
echo "STARTING PHASE 3E MEMBER ACCOUNT UX VERIFICATION\n";
echo "=======================================================\n\n";

$pass_count = 0;
function assert_ux( $condition, $message ) {
    global $pass_count;
    if ( ! $condition ) {
        throw new RuntimeException( "ASSERTION FAILED: " . $message );
    }
    $pass_count++;
    echo "  [PASS] " . $message . "\n";
}

// -------------------------------------------------------------
// SECTION 1: NONE / GUEST DASHBOARD CARD
// -------------------------------------------------------------
echo "--- 1. NONE / GUEST DASHBOARD CARD ---\n";
// User 10 has no orders / no subscriptions
$html_none = CCC\WNB\get_account_dashboard_card( 10 );

assert_ux( false !== strpos( $html_none, 'ccc-wnb-tier-none' ), "None: contains container class ccc-wnb-tier-none" );
assert_ux( false !== strpos( $html_none, 'No active Lounge membership' ), "None: displays 'No active Lounge membership'" );
assert_ux( false !== strpos( $html_none, 'Claim Free Lounge Pass' ), "None: displays 'Claim Free Lounge Pass' CTA" );
assert_ux( false !== strpos( $html_none, 'https://cccultivate.com/product/lounge-pass/' ), "None: CTA links to /product/lounge-pass/" );
assert_ux( false !== strpos( $html_none, 'Ask Budly' ), "None: displays Ask Budly entry" );
assert_ux( false !== strpos( $html_none, 'https://cccultivate.com/ask-budly/' ), "None: Ask Budly links to /ask-budly/" );
// Isolation checks
assert_ux( false === strpos( $html_none, 'ccc-wnb-badge-wnb_' ), "None: does NOT render any tier badge" );
assert_ux( false === strpos( $html_none, 'Enter the Lounge' ), "None: does NOT render 'Enter the Lounge' CTA" );
assert_ux( false === strpos( $html_none, 'Manage Subscription' ), "None: does NOT render 'Manage Subscription' link" );
assert_ux( false === strpos( $html_none, '10% eligible discount' ), "None: does NOT render 10% discount" );
assert_ux( false === strpos( $html_none, '25% eligible discount' ), "None: does NOT render 25% discount" );

// -------------------------------------------------------------
// SECTION 2: PASS DASHBOARD CARD
// -------------------------------------------------------------
echo "\n--- 2. PASS DASHBOARD CARD ---\n";
// User 9 has completed Pass order #1105
$html_pass = CCC\WNB\get_account_dashboard_card( 9 );

assert_ux( false !== strpos( $html_pass, 'ccc-wnb-tier-pass' ), "Pass: contains container class ccc-wnb-tier-pass" );
assert_ux( false !== strpos( $html_pass, 'Lounge Pass' ), "Pass: displays Lounge Pass heading" );
assert_ux( false !== strpos( $html_pass, 'ccc-wnb-badge-wnb_pass' ), "Pass: renders Pass badge ccc-wnb-badge-wnb_pass" );
assert_ux( false !== strpos( $html_pass, '0%' ), "Pass: displays Discount 0%" );
assert_ux( false !== strpos( $html_pass, 'Community access' ), "Pass: lists benefit 'Community access'" );
assert_ux( false !== strpos( $html_pass, 'Enter the Lounge' ), "Pass: renders 'Enter the Lounge' CTA" );
assert_ux( false !== strpos( $html_pass, 'https://cccultivate.com/wakenbake-lounge-community/' ), "Pass: CTA links to /wakenbake-lounge-community/" );
assert_ux( false !== strpos( $html_pass, 'Ask Budly' ), "Pass: displays Ask Budly entry" );
// Isolation checks
assert_ux( false === strpos( $html_pass, 'ccc-wnb-badge-wnb_member' ), "Pass: does NOT render Member badge" );
assert_ux( false === strpos( $html_pass, 'ccc-wnb-badge-wnb_elite' ), "Pass: does NOT render Elite badge" );
assert_ux( false === strpos( $html_pass, 'Manage Subscription' ), "Pass: does NOT render 'Manage Subscription' link" );
assert_ux( false === strpos( $html_pass, '10% eligible discount' ), "Pass: does NOT render 10% discount" );
assert_ux( false === strpos( $html_pass, '25% eligible discount' ), "Pass: does NOT render 25% discount" );
assert_ux( false === strpos( $html_pass, 'early drop access' ), "Pass: does NOT render Member benefit 'early drop access'" );

// -------------------------------------------------------------
// SECTION 3: MEMBER DASHBOARD CARD
// -------------------------------------------------------------
echo "\n--- 3. MEMBER DASHBOARD CARD ---\n";
// User 7 with Member active, Elite cancelled
$orders[1]->status = 'cancelled';
$orders[0]->status = 'active';
$html_member = CCC\WNB\get_account_dashboard_card( 7 );

assert_ux( false !== strpos( $html_member, 'ccc-wnb-tier-member' ), "Member: contains container class ccc-wnb-tier-member" );
assert_ux( false !== strpos( $html_member, 'Lounge Member' ), "Member: displays Lounge Member heading" );
assert_ux( false !== strpos( $html_member, 'ccc-wnb-badge-wnb_member' ), "Member: renders Member badge ccc-wnb-badge-wnb_member" );
assert_ux( false !== strpos( $html_member, '10% eligible discount' ), "Member: displays 10% eligible discount" );
assert_ux( false !== strpos( $html_member, 'Community access' ), "Member: lists benefit 'Community access'" );
assert_ux( false !== strpos( $html_member, 'early drop access' ), "Member: lists benefit 'early drop access'" );
assert_ux( false !== strpos( $html_member, 'member sections' ), "Member: lists benefit 'member sections'" );
assert_ux( false !== strpos( $html_member, 'priority event access' ), "Member: lists benefit 'priority event access'" );
assert_ux( false !== strpos( $html_member, 'Enter the Lounge' ), "Member: renders 'Enter the Lounge' CTA" );
assert_ux( false !== strpos( $html_member, 'Manage Subscription' ), "Member: renders 'Manage Subscription' link" );
assert_ux( false !== strpos( $html_member, '/my-account/subscriptions/' ), "Member: subscription link targets /my-account/subscriptions/" );
assert_ux( false !== strpos( $html_member, 'Ask Budly' ), "Member: displays Ask Budly entry" );
// Isolation checks
assert_ux( false === strpos( $html_member, 'ccc-wnb-badge-wnb_elite' ), "Member: does NOT render Elite badge" );
assert_ux( false === strpos( $html_member, '25% eligible discount' ), "Member: does NOT render 25% discount" );
assert_ux( false === strpos( $html_member, 'first-drop access' ), "Member: does NOT render Elite benefit 'first-drop access'" );
assert_ux( false === strpos( $html_member, 'VIP community access' ), "Member: does NOT render Elite benefit 'VIP community access'" );
assert_ux( false === strpos( $html_member, 'monthly curated Budly content' ), "Member: does NOT render Elite benefit 'monthly curated Budly content'" );

// -------------------------------------------------------------
// SECTION 4: ELITE DASHBOARD CARD
// -------------------------------------------------------------
echo "\n--- 4. ELITE DASHBOARD CARD ---\n";
// User 7 with Elite active
$orders[1]->status = 'active';
$html_elite = CCC\WNB\get_account_dashboard_card( 7 );

assert_ux( false !== strpos( $html_elite, 'ccc-wnb-tier-elite' ), "Elite: contains container class ccc-wnb-tier-elite" );
assert_ux( false !== strpos( $html_elite, 'Lounge Elite' ), "Elite: displays Lounge Elite heading" );
assert_ux( false !== strpos( $html_elite, 'ccc-wnb-badge-wnb_elite' ), "Elite: renders VIP Elite badge ccc-wnb-badge-wnb_elite" );
assert_ux( false !== strpos( $html_elite, '25% eligible discount' ), "Elite: displays 25% eligible discount" );
assert_ux( false !== strpos( $html_elite, 'Community access' ), "Elite: lists benefit 'Community access'" );
assert_ux( false !== strpos( $html_elite, 'first-drop access' ), "Elite: lists benefit 'first-drop access'" );
assert_ux( false !== strpos( $html_elite, 'VIP community access' ), "Elite: lists benefit 'VIP community access'" );
assert_ux( false !== strpos( $html_elite, 'priority event invitations' ), "Elite: lists benefit 'priority event invitations'" );
assert_ux( false !== strpos( $html_elite, 'monthly curated Budly content' ), "Elite: lists benefit 'monthly curated Budly content'" );
assert_ux( false !== strpos( $html_elite, 'Enter the Lounge' ), "Elite: renders 'Enter the Lounge' CTA" );
assert_ux( false !== strpos( $html_elite, 'Manage Subscription' ), "Elite: renders 'Manage Subscription' link" );
assert_ux( false !== strpos( $html_elite, '/my-account/subscriptions/' ), "Elite: subscription link targets /my-account/subscriptions/" );
assert_ux( false !== strpos( $html_elite, 'Ask Budly' ), "Elite: displays Ask Budly entry" );

// -------------------------------------------------------------
// SECTION 5: MY ACCOUNT NAVIGATION ITEMS & ROUTING
// -------------------------------------------------------------
echo "\n--- 5. MY ACCOUNT NAVIGATION ITEMS & ROUTING ---\n";

$initial_menu = array(
    'dashboard'       => 'Dashboard',
    'orders'          => 'Orders',
    'subscriptions'   => 'Subscriptions',
    'downloads'       => 'Downloads',
    'edit-address'    => 'Addresses',
    'edit-account'    => 'Account details',
    'customer-logout' => 'Logout',
);

$filtered_menu = CCC\WNB\Membership_Entitlements::account_menu_items( $initial_menu );

// Verify existing items preserved
assert_ux( isset( $filtered_menu['dashboard'] ), "Navigation: preserves 'dashboard'" );
assert_ux( isset( $filtered_menu['orders'] ), "Navigation: preserves 'orders'" );
assert_ux( isset( $filtered_menu['subscriptions'] ), "Navigation: preserves 'subscriptions'" );
assert_ux( isset( $filtered_menu['downloads'] ), "Navigation: preserves 'downloads'" );
assert_ux( isset( $filtered_menu['edit-address'] ), "Navigation: preserves 'edit-address'" );
assert_ux( isset( $filtered_menu['edit-account'] ), "Navigation: preserves 'edit-account'" );
assert_ux( isset( $filtered_menu['customer-logout'] ), "Navigation: preserves 'customer-logout'" );

// Verify Lounge Community item added
assert_ux( isset( $filtered_menu['wakenbake-lounge-community'] ), "Navigation: adds 'wakenbake-lounge-community' item" );
assert_ux( 'Lounge Community' === $filtered_menu['wakenbake-lounge-community'], "Navigation: item label is 'Lounge Community'" );

// Verify endpoint URL routing
$endpoint_url = CCC\WNB\Membership_Entitlements::account_endpoint_url( 'https://cccultivate.com/my-account/wakenbake-lounge-community/', 'wakenbake-lounge-community', '', '' );
assert_ux( 'https://cccultivate.com/wakenbake-lounge-community/' === $endpoint_url, "Navigation: endpoint routes to https://cccultivate.com/wakenbake-lounge-community/" );

// Unrelated endpoint untouched
$unrelated_url = CCC\WNB\Membership_Entitlements::account_endpoint_url( 'https://cccultivate.com/my-account/orders/', 'orders', '', '' );
assert_ux( 'https://cccultivate.com/my-account/orders/' === $unrelated_url, "Navigation: preserves other endpoints untouched" );

// -------------------------------------------------------------
// SECTION 6: POST-ACQUISITION WELCOME (ORDER RECEIVED)
// -------------------------------------------------------------
echo "\n--- 6. POST-ACQUISITION WELCOME EXPERIENCE ---\n";

// A. Product 1047 (Pass)
$order_pass = new Order( 1105, 9, 1047, 'processing' );
$welcome_pass = CCC\WNB\get_post_order_welcome( $order_pass );
assert_ux( false !== strpos( $welcome_pass, 'ccc-wnb-welcome-card' ), "Order Welcome (Pass): renders ccc-wnb-welcome-card" );
assert_ux( false !== strpos( $welcome_pass, 'ccc-wnb-badge-wnb_pass' ), "Order Welcome (Pass): renders Pass badge" );
assert_ux( false !== strpos( $welcome_pass, 'Your free Wake&#8217;n&#8217;Bake Lounge Community Pass is active' ), "Order Welcome (Pass): displays Pass welcome text" );
assert_ux( false !== strpos( $welcome_pass, 'Enter the Lounge' ), "Order Welcome (Pass): displays 'Enter the Lounge' CTA" );
assert_ux( false !== strpos( $welcome_pass, 'https://cccultivate.com/wakenbake-lounge-community/' ), "Order Welcome (Pass): CTA targets /wakenbake-lounge-community/" );

// B. Product 1048 (Member)
$order_member = new Order( 1106, 7, 1048, 'active' );
$welcome_member = CCC\WNB\get_post_order_welcome( $order_member );
assert_ux( false !== strpos( $welcome_member, 'ccc-wnb-welcome-card' ), "Order Welcome (Member): renders ccc-wnb-welcome-card" );
assert_ux( false !== strpos( $welcome_member, 'ccc-wnb-badge-wnb_member' ), "Order Welcome (Member): renders Member badge" );
assert_ux( false !== strpos( $welcome_member, 'Your Wake&#8217;n&#8217;Bake Lounge Member subscription is active' ), "Order Welcome (Member): displays Member welcome text" );
assert_ux( false !== strpos( $welcome_member, 'Enter the Lounge' ), "Order Welcome (Member): displays 'Enter the Lounge' CTA" );

// C. Product 1049 (Elite)
$order_elite = new Order( 1107, 7, 1049, 'active' );
$welcome_elite = CCC\WNB\get_post_order_welcome( $order_elite );
assert_ux( false !== strpos( $welcome_elite, 'ccc-wnb-welcome-card' ), "Order Welcome (Elite): renders ccc-wnb-welcome-card" );
assert_ux( false !== strpos( $welcome_elite, 'ccc-wnb-badge-wnb_elite' ), "Order Welcome (Elite): renders Elite badge" );
assert_ux( false !== strpos( $welcome_elite, 'Your Wake&#8217;n&#8217;Bake Lounge Elite VIP subscription is active' ), "Order Welcome (Elite): displays Elite welcome text" );
assert_ux( false !== strpos( $welcome_elite, 'Enter the Lounge' ), "Order Welcome (Elite): displays 'Enter the Lounge' CTA" );

// D. Unrelated product order (Product 42)
$order_unrelated = new Order( 1108, 8, 42, 'completed' );
$welcome_unrelated = CCC\WNB\get_post_order_welcome( $order_unrelated );
assert_ux( '' === $welcome_unrelated, "Order Welcome (Unrelated Product): renders NOTHING (empty string)" );

// -------------------------------------------------------------
// SECTION 7: CSS & RESPONSIVE STYLING INTEGRITY
// -------------------------------------------------------------
echo "\n--- 7. CSS & RESPONSIVE STYLING INTEGRITY ---\n";
$css = CCC\WNB\Membership_Entitlements::get_membership_css();

assert_ux( false !== strpos( $css, '.ccc-wnb-account-card' ), "CSS: defines .ccc-wnb-account-card" );
assert_ux( false !== strpos( $css, '.ccc-wnb-badge' ), "CSS: defines .ccc-wnb-badge" );
assert_ux( false !== strpos( $css, '.ccc-wnb-badge-wnb_pass' ), "CSS: defines .ccc-wnb-badge-wnb_pass" );
assert_ux( false !== strpos( $css, '.ccc-wnb-badge-wnb_member' ), "CSS: defines .ccc-wnb-badge-wnb_member" );
assert_ux( false !== strpos( $css, '.ccc-wnb-badge-wnb_elite' ), "CSS: defines .ccc-wnb-badge-wnb_elite" );
assert_ux( false !== strpos( $css, '.ccc-wnb-btn-primary' ), "CSS: defines .ccc-wnb-btn-primary" );
assert_ux( false !== strpos( $css, '.ccc-wnb-btn-secondary' ), "CSS: defines .ccc-wnb-btn-secondary" );
assert_ux( false !== strpos( $css, '.ccc-wnb-welcome-card' ), "CSS: defines .ccc-wnb-welcome-card" );
assert_ux( false !== strpos( $css, '@media (max-width: 820px)' ), "CSS: defines 820px breakpoint" );
assert_ux( false !== strpos( $css, '@media (max-width: 480px)' ), "CSS: defines mobile breakpoint (<=480px for 390px support)" );
assert_ux( false !== strpos( $css, 'box-sizing: border-box' ), "CSS: enforces box-sizing: border-box to prevent horizontal overflow" );

echo "\n=======================================================\n";
echo "ALL PHASE 3E UX CHECKS PASSED: {$pass_count} checks!\n";
echo "=======================================================\n";
