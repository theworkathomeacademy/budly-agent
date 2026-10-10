<?php
/**
 * Phase 3D Comprehensive Lifecycle & Entitlement Verification Suite
 */
define( 'ABSPATH', __DIR__ );

// Load the integration test harness environment
require_once __DIR__ . '/wnb_membership_integration.php';

echo "\n=======================================================\n";
echo "STARTING PHASE 3D DETERMINISTIC LIFECYCLE VERIFICATION\n";
echo "=======================================================\n\n";

// Helper for assertions
function assert_test( $condition, $message ) {
    if ( ! $condition ) {
        throw new RuntimeException( "ASSERTION FAILED: " . $message );
    }
    echo "  [PASS] " . $message . "\n";
}

$now = time();

// -----------------------------------------------------------------
// PART A: LIFECYCLE STATE MATRIX
// -----------------------------------------------------------------
echo "--- PART A: LIFECYCLE STATE MATRIX ---\n";

// 1. NONE
$state_none = CCC\WNB\Entitlement_Rules::evaluate( array(), $now, null );
assert_test( 'none' === $state_none['level'], "NONE: level === 'none'" );
assert_test( false === $state_none['community_access'], "NONE: community_access === false" );
assert_test( false === $state_none['member_access'], "NONE: member_access === false" );
assert_test( false === $state_none['elite_access'], "NONE: elite_access === false" );
assert_test( 0 === $state_none['discount_percent'], "NONE: discount_percent === 0" );

// 2. PASS
$pass_candidate = array( 'product_id' => 1047, 'sku' => 'WNB-MBR-PASS', 'level' => 'pass', 'acquired' => true, 'order_id' => 1105 );
$state_pass = CCC\WNB\Entitlement_Rules::evaluate( array(), $now, $pass_candidate );
assert_test( 'pass' === $state_pass['level'], "PASS: level === 'pass'" );
assert_test( true === $state_pass['community_access'], "PASS: community_access === true" );
assert_test( false === $state_pass['member_access'], "PASS: member_access === false" );
assert_test( false === $state_pass['elite_access'], "PASS: elite_access === false" );
assert_test( 0 === $state_pass['discount_percent'], "PASS: discount_percent === 0" );

// 3. MEMBER
$member_sub = array( array( 'product_id' => 1048, 'sku' => 'WNB-MBR-MEMBER', 'level' => 'member', 'status' => 'active', 'subscription_id' => 101 ) );
$state_member = CCC\WNB\Entitlement_Rules::evaluate( $member_sub, $now, null );
assert_test( 'member' === $state_member['level'], "MEMBER: level === 'member'" );
assert_test( true === $state_member['community_access'], "MEMBER: community_access === true" );
assert_test( true === $state_member['member_access'], "MEMBER: member_access === true" );
assert_test( false === $state_member['elite_access'], "MEMBER: elite_access === false" );
assert_test( 10 === $state_member['discount_percent'], "MEMBER: discount_percent === 10" );

// 4. ELITE
$elite_sub = array( array( 'product_id' => 1049, 'sku' => 'WNB-MBR-ELITE', 'level' => 'elite', 'status' => 'active', 'subscription_id' => 102 ) );
$state_elite = CCC\WNB\Entitlement_Rules::evaluate( $elite_sub, $now, null );
assert_test( 'elite' === $state_elite['level'], "ELITE: level === 'elite'" );
assert_test( true === $state_elite['community_access'], "ELITE: community_access === true" );
assert_test( true === $state_elite['member_access'], "ELITE: member_access === true" );
assert_test( true === $state_elite['elite_access'], "ELITE: elite_access === true" );
assert_test( 25 === $state_elite['discount_percent'], "ELITE: discount_percent === 25" );

// -----------------------------------------------------------------
// PART B: PAID SUBSCRIPTION STATUS BEHAVIOR
// -----------------------------------------------------------------
echo "\n--- PART B: PAID SUBSCRIPTION STATUS BEHAVIOR ---\n";

$statuses_to_test = array(
    'active'         => true,
    'pending-cancel' => 'conditional', // true if paid_until > now, false if paid_until <= now
    'pending'        => false,
    'on-hold'        => false,
    'cancelled'      => false,
    'expired'        => false,
    'failed'         => false,
    'completed'      => false,
);

foreach ( $statuses_to_test as $status => $expected_grant ) {
    if ( 'conditional' === $expected_grant ) {
        // Test pending-cancel unexpired
        $unexpired_sub = array( array( 'product_id' => 1048, 'sku' => 'WNB-MBR-MEMBER', 'level' => 'member', 'status' => 'pending-cancel', 'paid_until' => $now + 3600, 'subscription_id' => 201 ) );
        $res_unexpired = CCC\WNB\Entitlement_Rules::evaluate( $unexpired_sub, $now, null );
        assert_test( 'member' === $res_unexpired['level'] && true === $res_unexpired['member_access'], "Status 'pending-cancel' (paid_until > now) GRANTS Member access until period end" );

        // Test pending-cancel expired
        $expired_sub = array( array( 'product_id' => 1048, 'sku' => 'WNB-MBR-MEMBER', 'level' => 'member', 'status' => 'pending-cancel', 'paid_until' => $now - 3600, 'subscription_id' => 202 ) );
        $res_expired = CCC\WNB\Entitlement_Rules::evaluate( $expired_sub, $now, null );
        assert_test( 'none' === $res_expired['level'] && false === $res_expired['member_access'], "Status 'pending-cancel' (paid_until <= now) REVOKES Member access" );
    } else {
        $test_sub = array( array( 'product_id' => 1048, 'sku' => 'WNB-MBR-MEMBER', 'level' => 'member', 'status' => $status, 'subscription_id' => 203 ) );
        $res = CCC\WNB\Entitlement_Rules::evaluate( $test_sub, $now, null );
        if ( $expected_grant ) {
            assert_test( 'member' === $res['level'] && true === $res['member_access'], "Status '$status' GRANTS Member access" );
        } else {
            assert_test( 'none' === $res['level'] && false === $res['member_access'], "Status '$status' REVOKES Member access (evaluates to none)" );
        }
    }
}

// -----------------------------------------------------------------
// PART C: DOWNGRADE / FALLBACK RESULTS
// -----------------------------------------------------------------
echo "\n--- PART C: DOWNGRADE / FALLBACK RESULTS ---\n";

// 1. Elite active -> elite
$subs_combo = array(
    array( 'product_id' => 1048, 'sku' => 'WNB-MBR-MEMBER', 'level' => 'member', 'status' => 'active', 'subscription_id' => 301 ),
    array( 'product_id' => 1049, 'sku' => 'WNB-MBR-ELITE', 'level' => 'elite', 'status' => 'active', 'subscription_id' => 302 )
);
$c1 = CCC\WNB\Entitlement_Rules::evaluate( $subs_combo, $now, $pass_candidate );
assert_test( 'elite' === $c1['level'] && 25 === $c1['discount_percent'] && true === $c1['elite_access'], "1. Elite active outranks Member and Pass -> 'elite'" );

// 2. Elite becomes nonqualifying (cancelled) while Member remains active -> fallback to member
$subs_combo[1]['status'] = 'cancelled';
$c2 = CCC\WNB\Entitlement_Rules::evaluate( $subs_combo, $now, $pass_candidate );
assert_test( 'member' === $c2['level'] && 10 === $c2['discount_percent'] && false === $c2['elite_access'], "2. Elite cancelled while Member active falls back cleanly to 'member' (no stale Elite privileges)" );

// 3. Member also becomes nonqualifying (expired) while Pass remains -> fallback to pass
$subs_combo[0]['status'] = 'expired';
$c3 = CCC\WNB\Entitlement_Rules::evaluate( $subs_combo, $now, $pass_candidate );
assert_test( 'pass' === $c3['level'] && 0 === $c3['discount_percent'] && false === $c3['member_access'] && true === $c3['community_access'], "3. All paid memberships nonqualifying falls back to 'pass' (0% discount, community access only)" );

// 4. All qualifying relationships absent -> none
$c4 = CCC\WNB\Entitlement_Rules::evaluate( $subs_combo, $now, null );
assert_test( 'none' === $c4['level'] && false === $c4['community_access'] && 0 === $c4['discount_percent'], "4. All qualifying relationships absent -> 'none'" );

// 5. Account creation alone (empty candidates, no pass) -> none
$c5 = CCC\WNB\Entitlement_Rules::evaluate( array(), $now, null );
assert_test( 'none' === $c5['level'] && false === $c5['community_access'], "5. Account creation alone -> 'none'" );

// 6. Higher-tier removal never leaves stale higher-tier privileges
assert_test( false === $c2['elite_access'] && false === $c3['elite_access'] && false === $c3['member_access'], "6. Complete isolation: No higher-tier privilege leaks down" );

// -----------------------------------------------------------------
// PART D: COMMUNITY RENDERING
// -----------------------------------------------------------------
echo "\n--- PART D: COMMUNITY RENDERING & BADGES ---\n";

// Set user 10 (no orders)
$current_user_id = 10;
$rendered_none = $shortcodes['ccc_wnb_community']();
assert_test( false !== strpos( $rendered_none, 'ccc-wnb-community-unauthorized' ), "Community Hub for NONE renders unauthorized notice" );
assert_test( false === strpos( $rendered_none, 'ccc-wnb-section-pass' ), "Community Hub for NONE conceals Pass section" );
assert_test( false === strpos( $rendered_none, 'ccc-wnb-section-member' ), "Community Hub for NONE conceals Member section" );
assert_test( false === strpos( $rendered_none, 'ccc-wnb-section-elite' ), "Community Hub for NONE conceals Elite section" );

// Set user 9 (Pass order)
$current_user_id = 9;
$rendered_pass = $shortcodes['ccc_wnb_community']();
assert_test( false !== strpos( $rendered_pass, 'ccc-wnb-section-pass' ), "Community Hub for PASS renders Pass section" );
assert_test( false !== strpos( $rendered_pass, 'ccc-wnb-badge-wnb_pass' ), "Community Hub for PASS renders Pass badge ('Wake\'n\'Bake Lounge Pass')" );
assert_test( false === strpos( $rendered_pass, 'ccc-wnb-section-member' ), "Community Hub for PASS conceals Member section" );
assert_test( false === strpos( $rendered_pass, 'ccc-wnb-section-elite' ), "Community Hub for PASS conceals Elite section" );

// Set user 7 (Member active, Elite cancelled)
$orders[1]->status = 'cancelled';
$orders[0]->status = 'active';
$current_user_id = 7;
$rendered_member = $shortcodes['ccc_wnb_community']();
assert_test( false !== strpos( $rendered_member, 'ccc-wnb-section-pass' ), "Community Hub for MEMBER renders Pass section" );
assert_test( false !== strpos( $rendered_member, 'ccc-wnb-section-member' ), "Community Hub for MEMBER renders Member section" );
assert_test( false !== strpos( $rendered_member, 'ccc-wnb-badge-wnb_member' ), "Community Hub for MEMBER renders Member badge ('Wake\'n\'Bake Lounge Member')" );
assert_test( false === strpos( $rendered_member, 'ccc-wnb-section-elite' ), "Community Hub for MEMBER strictly conceals Elite section" );

// Set user 7 (Elite active)
$orders[1]->status = 'active';
$rendered_elite = $shortcodes['ccc_wnb_community']();
assert_test( false !== strpos( $rendered_elite, 'ccc-wnb-section-pass' ), "Community Hub for ELITE renders Pass section" );
assert_test( false !== strpos( $rendered_elite, 'ccc-wnb-section-member' ), "Community Hub for ELITE renders Member section" );
assert_test( false !== strpos( $rendered_elite, 'ccc-wnb-section-elite' ), "Community Hub for ELITE renders Elite VIP section" );
assert_test( false !== strpos( $rendered_elite, 'ccc-wnb-badge-wnb_elite' ), "Community Hub for ELITE renders VIP Elite badge ('Wake\'n\'Bake Lounge Elite')" );

// -----------------------------------------------------------------
// PART E: DISCOUNT LIFECYCLE & EXCLUSIONS
// -----------------------------------------------------------------
echo "\n--- PART E: DISCOUNT LIFECYCLE & EXCLUSIONS ---\n";

// 1. Elite active -> 25%
$orders[1]->status = 'active';
$orders[0]->status = 'active';
$cart_e = new Cart( array( array( 'data' => $products[42] ) ) );
$hooks['woocommerce_before_calculate_totals'][0]( $cart_e );
assert_test( 75.0 === (float) $products[42]->get_price(), "Elite active grants 25% discount on regular item ($100 -> $75)" );

// 2. Elite downgraded to Member -> 10%
$orders[1]->status = 'cancelled';
$products[42] = new Product(42, 'OTHER'); // reset regular price $100
$cart_m = new Cart( array( array( 'data' => $products[42] ) ) );
$hooks['woocommerce_before_calculate_totals'][0]( $cart_m );
assert_test( 90.0 === (float) $products[42]->get_price(), "Downgrade Elite -> Member drops discount to 10% ($100 -> $90)" );

// 3. Member downgraded to Pass -> 0%
$orders[0]->status = 'cancelled';
$current_user_id = 9; // User with Pass
$products[42] = new Product(42, 'OTHER'); // reset regular price $100
$cart_p = new Cart( array( array( 'data' => $products[42] ) ) );
$hooks['woocommerce_before_calculate_totals'][0]( $cart_p );
assert_test( 100.0 === (float) $products[42]->get_price(), "Downgrade Member -> Pass drops discount to 0% ($100 -> $100)" );

// 4. Exclusions verified on Member
$current_user_id = 7;
$orders[0]->status = 'active';
$cart_ex = new Cart( array(
    array( 'data' => $products[50] ),   // bulk
    array( 'data' => $products[455] ),  // payment plan
    array( 'data' => $products[60] ),   // sale
    array( 'data' => $products[1048] ), // membership
) );
$hooks['woocommerce_before_calculate_totals'][0]( $cart_ex );
assert_test( 100.0 === (float) $products[50]->get_price(), "Exclusion: Bulk category excluded from discount" );
assert_test( 100.0 === (float) $products[455]->get_price(), "Exclusion: Payment-plan products excluded from discount" );
assert_test( 80.0 === (float) $products[60]->get_price(), "Exclusion: Sale items preserve sale price without stacking" );
assert_test( 100.0 === (float) $products[1048]->get_price(), "Exclusion: Membership products excluded from discount" );

// 5. Coupon-bearing transactions
$cart_coupon = new Cart( array( array( 'data' => $products[42] ) ), array( 'save5' ) );
$products[42] = new Product(42, 'OTHER');
$hooks['woocommerce_before_calculate_totals'][0]( $cart_coupon );
assert_test( 100.0 === (float) $products[42]->get_price(), "Exclusion: Coupon-bearing transactions block membership discount" );

// -----------------------------------------------------------------
// PART F: ORDER #1105 REGRESSION
// -----------------------------------------------------------------
echo "\n--- PART F: ORDER #1105 REGRESSION ---\n";

$pass_order_status = $orders[3]; // Order 4 in harness representing completed Pass order
assert_test( 'shop_order' === $pass_order_status->get_type(), "Order type is 'shop_order'" );
assert_test( 'completed' === $pass_order_status->get_status(), "Order status is 'completed'" );
assert_test( 1047 === $pass_order_status->get_items('line_item')[0]->get_product_id(), "Order contains Product 1047" );
assert_test( 'pass' === CCC\WNB\get_membership_level( 9 ), "Customer with completed Pass order resolves strictly to level 'pass'" );
assert_test( true === CCC\WNB\has_community_access( 9 ), "Customer with completed Pass order receives community_access === true" );
assert_test( false === CCC\WNB\can_access_level( 9, 'member' ), "Customer with completed Pass order does NOT receive member_access" );
assert_test( false === CCC\WNB\can_access_level( 9, 'elite' ), "Customer with completed Pass order does NOT receive elite_access" );

echo "\n=======================================================\n";
echo "ALL PHASE 3D DETERMINISTIC LIFECYCLE CHECKS PASSED!\n";
echo "=======================================================\n";
