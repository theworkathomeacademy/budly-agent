<?php
require_once __DIR__ . '/../../deploy/wordpress/ccc-wnb-membership-entitlements/includes/class-entitlement-rules.php';

use CCC\WNB\Entitlement_Rules as Rules;

function check( $condition, string $message ): void {
    if ( ! $condition ) { throw new RuntimeException( $message ); }
}
function sub( string $level, string $status, int $until = 0 ): array {
    return array( 'level' => $level, 'status' => $status, 'paid_until' => $until, 'subscription_id' => 12, 'product_id' => 'elite' === $level ? 1049 : 1048, 'sku' => 'elite' === $level ? 'WNB-MBR-ELITE' : 'WNB-MBR-MEMBER' );
}
$now = 1000;
$member = Rules::evaluate( array( sub( 'member', 'active' ) ), $now );
$elite = Rules::evaluate( array( sub( 'elite', 'active' ) ), $now );
check( 'member' === $member['level'] && $member['member_access'] && ! $member['elite_access'], 'Active Member' );
check( 'elite' === $elite['level'] && $elite['member_access'] && $elite['elite_access'], 'Active Elite hierarchy' );
check( 'elite' === Rules::evaluate( array( sub( 'member', 'active' ), sub( 'elite', 'active' ) ), $now )['level'], 'Elite precedence' );
check( 'none' === Rules::evaluate( array( sub( 'member', 'on-hold' ) ), $now )['level'], 'On hold suspension' );
check( 'active' === Rules::evaluate( array( sub( 'member', 'pending-cancel', 1001 ) ), $now )['status'], 'Paid-through cancellation' );
check( 'none' === Rules::evaluate( array( sub( 'member', 'pending-cancel', 1000 ) ), $now )['level'], 'Cancellation effective date' );
check( 'none' === Rules::evaluate( array( sub( 'elite', 'cancelled' ) ), $now )['level'], 'Cancelled removal' );
check( 'none' === Rules::evaluate( array( sub( 'elite', 'expired' ) ), $now )['level'], 'Expired removal' );
check( 'elite' === Rules::evaluate( array( sub( 'elite', 'on-hold' ), sub( 'elite', 'active' ) ), $now )['level'], 'Reactivation' );
check( 10 === Rules::eligible_discount( $member, true, false ), 'Member 10 percent' );
check( 25 === Rules::eligible_discount( $elite, true, false ), 'Elite 25 percent' );
check( 0 === Rules::eligible_discount( $elite, true, true ), 'Membership coupon does not stack' );
check( 0 === Rules::eligible_discount( $elite, false, false ), 'Unrelated product excluded' );
check( 0 === Rules::eligible_discount( Rules::evaluate( array(), $now ), true, false ), 'Nonmember excluded' );
echo "14 entitlement rule checks passed\n";
