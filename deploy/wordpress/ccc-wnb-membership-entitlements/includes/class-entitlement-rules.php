<?php
/** Deterministic rules, independent of WordPress persistence. */
namespace CCC\WNB;

final class Entitlement_Rules {
    public static function evaluate( array $subscriptions, int $now, ?array $pass = null ): array {
        $winner = null;
        $fallback = null;
        foreach ( $subscriptions as $subscription ) {
            if ( ! is_array( $subscription ) || ! in_array( $subscription['level'] ?? '', array( 'member', 'elite' ), true ) ) {
                continue;
            }
            $status = $subscription['status'] ?? '';
            $paid = 'active' === $status || ( 'pending-cancel' === $status && (int) ( $subscription['paid_until'] ?? 0 ) > $now );
            if ( $paid && ( null === $winner || self::rank( $subscription['level'] ) > self::rank( $winner['level'] ) ) ) {
                $winner = $subscription;
            }
            if ( ! $paid && ( null === $fallback || self::rank( $subscription['level'] ) > self::rank( $fallback['level'] ) ) ) {
                $fallback = $subscription;
            }
        }
        if ( null !== $winner ) {
            return self::state( $winner['level'], 'active', $winner );
        }
        $status = $fallback['status'] ?? 'none';
        if ( 'pending-cancel' === $status ) {
            $status = 'cancelled';
        }
        if ( ! in_array( $status, array( 'on-hold', 'cancelled', 'expired' ), true ) ) {
            $status = 'none';
        }
        if ( is_array( $pass ) && ! empty( $pass['acquired'] ) ) {
            return self::state( 'pass', 'active', $pass );
        }
        return self::state( 'none', $status, $fallback );
    }

    private static function state( string $level, string $status, ?array $source ): array {
        $badges = array(
            'pass' => array( 'key' => 'wnb_pass', 'label' => "Wake'n'Bake Lounge Pass" ),
            'member' => array( 'key' => 'wnb_member', 'label' => "Wake'n'Bake Lounge Member" ),
            'elite' => array( 'key' => 'wnb_elite', 'label' => "Wake'n'Bake Lounge Elite" ),
            'none' => array( 'key' => 'none', 'label' => '' ),
        );
        $badge = $badges[ $level ] ?? $badges['none'];
        return array(
            'level' => $level,
            'status' => $status,
            'discount_percent' => 'elite' === $level ? 25 : ( 'member' === $level ? 10 : 0 ),
            'community_access' => in_array( $level, array( 'pass', 'member', 'elite' ), true ),
            'member_access' => in_array( $level, array( 'member', 'elite' ), true ),
            'elite_access' => 'elite' === $level,
            'badge_key' => $badge['key'],
            'badge_label' => $badge['label'],
            'subscription_id' => (int) ( $source['subscription_id'] ?? 0 ),
            'product_id' => (int) ( $source['product_id'] ?? 0 ),
            'sku' => (string) ( $source['sku'] ?? '' ),
        );
    }

    private static function rank( string $level ): int {
        return 'elite' === $level ? 3 : ( 'member' === $level ? 2 : ( 'pass' === $level ? 1 : 0 ) );
    }

    public static function eligible_discount( array $state, bool $eligible_product, bool $has_conflicting_discount ): int {
        return $eligible_product && ! $has_conflicting_discount ? (int) ( $state['discount_percent'] ?? 0 ) : 0;
    }
}
