<?php
/**
 * Class Lounge_UI
 *
 * Implements the ratified MX-1 through MX-4A Wake'n'Bake Lounge presentation
 * with dark emerald-and-gold botanical styling, server-side entitlement enforcement,
 * responsive multi-screen navigation, and approved educational curriculum.
 *
 * @package CCC\WNB
 */

namespace CCC\WNB;

defined( 'ABSPATH' ) || exit;

final class Lounge_UI {

    /**
     * Development fixture mode flag. Disabled by default in release builds.
     *
     * @var bool
     */
    private static bool $fixture_mode = false;

    /**
     * Determines whether development fixtures are enabled.
     * Defaults to false for release builds. Can be enabled via constant CCC_WNB_ENABLE_DEV_FIXTURES
     * or via set_fixture_mode(true) in development/test harnesses.
     */
    public static function is_fixture_mode_enabled(): bool {
        if ( defined( 'CCC_WNB_ENABLE_DEV_FIXTURES' ) && CCC_WNB_ENABLE_DEV_FIXTURES ) {
            return true;
        }
        if ( function_exists( 'apply_filters' ) ) {
            return (bool) apply_filters( 'ccc_wnb_lounge_enable_dev_fixtures', self::$fixture_mode );
        }
        return self::$fixture_mode;
    }

    /**
     * Programmatically toggles development fixture mode.
     */
    public static function set_fixture_mode( bool $enabled ): void {
        self::$fixture_mode = $enabled;
    }

    /**
     * Escape attribute fallback.
     */
    public static function esc_attr( string $text ): string {
        return function_exists( 'esc_attr' ) ? esc_attr( $text ) : htmlspecialchars( $text, ENT_QUOTES );
    }

    /**
     * Escape HTML fallback.
     */
    public static function esc_html( string $text ): string {
        return function_exists( 'esc_html' ) ? esc_html( $text ) : htmlspecialchars( $text, ENT_QUOTES );
    }

    /**
     * Escape URL fallback.
     */
    public static function esc_url( string $url ): string {
        return function_exists( 'esc_url' ) ? esc_url( $url ) : htmlspecialchars( $url, ENT_QUOTES );
    }

    /**
     * Sanitize key fallback.
     */
    public static function sanitize_key( string $key ): string {
        return function_exists( 'sanitize_key' ) ? sanitize_key( $key ) : preg_replace( '/[^a-z0-9_-]/', '', strtolower( $key ) );
    }

    /**
     * Sanitize text field fallback.
     */
    public static function sanitize_text_field( string $str ): string {
        return function_exists( 'sanitize_text_field' ) ? sanitize_text_field( $str ) : strip_tags( trim( $str ) );
    }

    /**
     * Add query argument fallback.
     */
    public static function add_query_arg( array $params, string $url ): string {
        if ( function_exists( 'add_query_arg' ) ) {
            return add_query_arg( $params, $url );
        }
        $query = http_build_query( $params );
        return ( false !== strpos( $url, '?' ) ) ? ( $url . '&' . $query ) : ( $url . '?' . $query );
    }

    /**
     * Renders the complete Lounge UI experience.
     *
     * @param int   $user_id The current WordPress user ID.
     * @param array $state   The verified membership entitlement state.
     * @return string Rendered HTML.
     */
    public static function render( int $user_id = 0, ?array $state = null ): string {
        if ( $user_id <= 0 && function_exists( 'get_current_user_id' ) ) {
            $user_id = (int) get_current_user_id();
        }
        if ( null === $state ) {
            if ( class_exists( __NAMESPACE__ . '\\Membership_Entitlements' ) ) {
                $state = Membership_Entitlements::state( $user_id );
            } else {
                $state = array(
                    'level'            => 'none',
                    'community_access' => false,
                    'member_access'    => false,
                    'elite_access'     => false,
                    'discount_percent' => 0,
                    'badge_key'        => 'none',
                    'badge_label'      => 'Guest',
                );
            }
        }
        $view = isset( $_GET['view'] ) ? self::sanitize_key( (string) $_GET['view'] ) : 'home';
        $item_id = isset( $_GET['item'] ) ? self::sanitize_text_field( (string) $_GET['item'] ) : ( isset( $_GET['strain'] ) ? self::sanitize_text_field( (string) $_GET['strain'] ) : '' );

        // Valid views inventory (MX-4A Section IV)
        $valid_views = array( 'home', 'explore', 'detail', 'botanical', 'benefits', 'whats-new', 'account' );
        if ( ! in_array( $view, $valid_views, true ) ) {
            $view = 'home';
        }

        $level = $state['level'] ?? 'none';
        $is_guest = ( 'none' === $level || $user_id <= 0 );

        // Build UI container
        $out = '<div class="wnb-lounge-app" id="wnb-lounge-root" data-current-view="' . self::esc_attr( $view ) . '" data-user-tier="' . self::esc_attr( $level ) . '">';

        // 1. App Header
        $out .= self::render_header( $state, $is_guest );

        // 2. Desktop Navigation Bar
        $out .= self::render_nav( $view, $is_guest );

        // 3. Main Content Screen
        $out .= '<main class="wnb-lounge-main" id="wnb-lounge-content" role="main">';
        switch ( $view ) {
            case 'explore':
                $out .= self::render_explore( $user_id, $state );
                break;
            case 'detail':
                $out .= self::render_detail( $user_id, $state, $item_id );
                break;
            case 'botanical':
                $out .= self::render_botanical( $user_id, $state, $item_id );
                break;
            case 'benefits':
                $out .= self::render_benefits( $user_id, $state );
                break;
            case 'whats-new':
                $out .= self::render_whats_new( $user_id, $state );
                break;
            case 'account':
                $out .= self::render_account( $user_id, $state );
                break;
            case 'home':
            default:
                $out .= self::render_home( $user_id, $state, $is_guest );
                break;
        }
        $out .= '</main>';

        // 4. Mobile Bottom Priority Navigation
        $out .= self::render_mobile_nav( $view, $is_guest );

        // 5. Client-side Interaction Script
        $out .= self::render_interactive_script();

        $out .= '</div>'; // .wnb-lounge-app

        return $out;
    }

    /**
     * Top Header with Brand identity, Tier indicator, and Quick Controls.
     */
    private static function render_header( array $state, bool $is_guest ): string {
        $level = $state['level'] ?? 'none';
        $badge_label = $state['badge_label'] ?? '';
        $badge_key = $state['badge_key'] ?? 'none';

        $home_url = self::get_lounge_url( 'home' );
        $account_url = self::get_account_url();
        $budly_url = self::get_budly_url();

        $out = '<header class="wnb-header" role="banner">';
        $out .= '<div class="wnb-header-inner">';

        // Brand Identity
        $out .= '<a href="' . self::esc_url( $home_url ) . '" class="wnb-brand" aria-label="Wake\'n\'Bake Lounge Home">';
        $out .= '<span class="wnb-brand-emblem" aria-hidden="true">&#10047;</span>';
        $out .= '<div class="wnb-brand-text">';
        $out .= '<span class="wnb-brand-title">Wake&#8217;n&#8217;Bake</span>';
        $out .= '<span class="wnb-brand-subtitle">The Lounge</span>';
        $out .= '</div>';
        $out .= '</a>';

        // Header Actions & Tier Badge
        $out .= '<div class="wnb-header-actions">';
        if ( ! $is_guest && ! empty( $badge_label ) ) {
            $out .= '<span class="ccc-wnb-badge ccc-wnb-badge-' . self::esc_attr( $badge_key ) . '" title="Verified Membership Tier">';
            $out .= self::esc_html( $badge_label );
            $out .= '</span>';
        } else {
            $out .= '<span class="wnb-guest-tag">Public Orientation</span>';
        }

        $out .= '<a href="' . self::esc_url( $budly_url ) . '" class="wnb-header-link wnb-header-budly" target="_blank" rel="noopener">Ask Budly</a>';
        if ( $is_guest ) {
            $out .= '<a href="' . self::esc_url( $account_url ) . '" class="wnb-btn wnb-btn-sm wnb-btn-outline">Log In</a>';
        } else {
            $out .= '<a href="' . self::esc_url( $account_url ) . '" class="wnb-header-link" aria-label="My Account">My Account</a>';
        }
        $out .= '</div>'; // .wnb-header-actions

        $out .= '</div>'; // .wnb-header-inner
        $out .= '</header>';

        return $out;
    }

    /**
     * Desktop Navigation Bar.
     */
    private static function render_nav( string $active_view, bool $is_guest ): string {
        $nav_items = array(
            'home'      => 'Lounge Home',
            'explore'   => 'Explore',
            'botanical' => 'Botanical Discovery',
            'benefits'  => 'Member Benefits',
            'whats-new' => 'What&#8217;s New',
            'account'   => 'Account Return',
        );

        $out = '<nav class="wnb-desktop-nav" aria-label="Lounge Sections">';
        $out .= '<ul class="wnb-nav-list" role="tablist">';
        foreach ( $nav_items as $view_key => $label ) {
            $is_active = ( $active_view === $view_key );
            $url = self::get_lounge_url( $view_key );
            $aria_selected = $is_active ? 'true' : 'false';
            $class = 'wnb-nav-link' . ( $is_active ? ' is-active' : '' );

            $out .= '<li role="presentation">';
            $out .= '<a href="' . self::esc_url( $url ) . '" class="' . self::esc_attr( $class ) . '" role="tab" aria-selected="' . $aria_selected . '" data-view-target="' . self::esc_attr( $view_key ) . '">';
            $out .= $label;
            $out .= '</a>';
            $out .= '</li>';
        }
        $out .= '</ul>';
        $out .= '</nav>';

        return $out;
    }

    /**
     * Mobile Bottom Priority Navigation: Home, Explore, Budly, Account.
     */
    private static function render_mobile_nav( string $active_view, bool $is_guest ): string {
        $home_active = ( 'home' === $active_view || 'botanical' === $active_view ) ? ' is-active' : '';
        $explore_active = ( 'explore' === $active_view || 'detail' === $active_view || 'whats-new' === $active_view ) ? ' is-active' : '';
        $account_active = ( 'account' === $active_view || 'benefits' === $active_view ) ? ' is-active' : '';

        $home_url = self::get_lounge_url( 'home' );
        $explore_url = self::get_lounge_url( 'explore' );
        $budly_url = self::get_budly_url();
        $account_url = self::get_lounge_url( 'account' );

        $out = '<nav class="wnb-mobile-bottom-bar" aria-label="Mobile Priority Navigation">';
        $out .= '<a href="' . self::esc_url( $home_url ) . '" class="wnb-mobile-tab' . $home_active . '" data-view-target="home">';
        $out .= '<span class="wnb-tab-icon" aria-hidden="true">&#127968;</span>';
        $out .= '<span class="wnb-tab-label">Home</span>';
        $out .= '</a>';

        $out .= '<a href="' . self::esc_url( $explore_url ) . '" class="wnb-mobile-tab' . $explore_active . '" data-view-target="explore">';
        $out .= '<span class="wnb-tab-icon" aria-hidden="true">&#128269;</span>';
        $out .= '<span class="wnb-tab-label">Explore</span>';
        $out .= '</a>';

        $out .= '<a href="' . self::esc_url( $budly_url ) . '" class="wnb-mobile-tab" target="_blank" rel="noopener">';
        $out .= '<span class="wnb-tab-icon" aria-hidden="true">&#128172;</span>';
        $out .= '<span class="wnb-tab-label">Budly</span>';
        $out .= '</a>';

        $out .= '<a href="' . self::esc_url( $account_url ) . '" class="wnb-mobile-tab' . $account_active . '" data-view-target="account">';
        $out .= '<span class="wnb-tab-icon" aria-hidden="true">&#128100;</span>';
        $out .= '<span class="wnb-tab-label">Account</span>';
        $out .= '</a>';
        $out .= '</nav>';

        return $out;
    }

    /**
     * Screen 01: Lounge Home
     */
    private static function render_home( int $user_id, array $state, bool $is_guest ): string {
        $level = $state['level'] ?? 'none';
        $badge_label = $state['badge_label'] ?? '';

        $out = '<div class="wnb-screen wnb-screen-home">';

        // Welcome Hero Card
        $out .= '<section class="wnb-card wnb-welcome-hero" aria-labelledby="wnb-welcome-title">';
        $out .= '<div class="wnb-welcome-kicker">Welcome to the Sanctuary</div>';
        $out .= '<h1 id="wnb-welcome-title" class="wnb-hero-title">Wake&#8217;n&#8217;Bake Lounge</h1>';
        $out .= '<p class="wnb-hero-lede">A curated botanical editorial environment dedicated to cannabis plant science, conscious culture, holistic recipes, and living discovery.</p>';

        if ( $is_guest ) {
            $pass_url = self::get_pass_product_url();
            $account_url = self::get_account_url();
            $out .= '<div class="wnb-welcome-cta-group">';
            $out .= '<a href="' . self::esc_url( $pass_url ) . '" class="wnb-btn wnb-btn-gold">Claim Free Lounge Pass &rarr;</a>';
            $out .= '<a href="' . self::esc_url( $account_url ) . '" class="wnb-btn wnb-btn-outline">Sign In to Enter</a>';
            $out .= '</div>';
        } else {
            $out .= '<div class="wnb-tier-status-pill">';
            $out .= '<span class="wnb-status-indicator" aria-hidden="true">&#10003;</span>';
            $out .= '<span>Verified Tier: <strong>' . self::esc_html( $badge_label ) . '</strong></span>';
            $out .= '</div>';
        }
        $out .= '</section>';

        // Screen 01 Featured Learning Card
        $catalog = self::get_content_items();
        $has_featured = self::is_fixture_mode_enabled() && isset( $catalog['VOL1-EDU-01'] );

        $out .= '<section class="wnb-featured-section" aria-labelledby="wnb-featured-heading">';
        $out .= '<h2 id="wnb-featured-heading" class="wnb-section-title">Featured Learning</h2>';

        if ( $has_featured ) {
            $featured_url = self::get_lounge_url( 'detail', 'VOL1-EDU-01' );
            $out .= '<article class="wnb-card wnb-featured-card">';
            $out .= '<div class="wnb-card-badge">Foundations Curriculum &bull; 8 min read</div>';
            $out .= '<h3 class="wnb-card-title"><a href="' . self::esc_url( $featured_url ) . '">Anatomy of a Cannabis Flower: Resins, Trichomes &amp; Chemovars</a></h3>';
            $out .= '<p class="wnb-card-summary">Explore the architecture of the cannabis plant. Discover how glandular trichomes synthesize cannabinoids, terpenes, and flavonoids, and why certificates of analysis matter more than market names.</p>';
            $out .= '<div class="wnb-card-footer">';
            $out .= '<span class="wnb-access-tag wnb-access-pass">Free Pass &amp; Above</span>';
            $out .= '<a href="' . self::esc_url( $featured_url ) . '" class="wnb-btn wnb-btn-sm wnb-btn-primary">Read Lesson &rarr;</a>';
            $out .= '</div>';
            $out .= '</article>';
        } else {
            // Honest pending-content state in release builds
            $out .= '<article class="wnb-card wnb-featured-card">';
            $out .= '<div class="wnb-card-badge">Curriculum Status &bull; In Editorial Review</div>';
            $out .= '<h3 class="wnb-card-title">Foundations Curriculum In Preparation</h3>';
            $out .= '<p class="wnb-card-summary">Official Lounge educational lessons and botanical guides are currently undergoing editorial review. Check back soon for approved releases, or consult Ask Budly for interactive plant guidance.</p>';
            $out .= '<div class="wnb-card-footer">';
            $out .= '<span class="wnb-access-tag wnb-access-pass">Release Pending</span>';
            $out .= '<a href="' . self::esc_url( self::get_budly_url() ) . '" class="wnb-btn wnb-btn-sm wnb-btn-primary" target="_blank" rel="noopener">Ask Budly &rarr;</a>';
            $out .= '</div>';
            $out .= '</article>';
        }
        $out .= '</section>';

        // Explore Quick Grid
        $out .= '<section class="wnb-explore-grid-section" aria-labelledby="wnb-explore-grid-title">';
        $out .= '<h2 id="wnb-explore-grid-title" class="wnb-section-title">Explore The Lounge</h2>';
        $out .= '<div class="wnb-card-grid wnb-grid-4">';

        // 1. Botanical Discovery
        $out .= '<div class="wnb-card wnb-topic-card">';
        $out .= '<span class="wnb-topic-icon" aria-hidden="true">&#127807;</span>';
        $out .= '<h3>Botanical Discovery</h3>';
        $out .= '<p>Explore Volume I botanical profiles, genetic lineage, and authentic terpene sensory vocabularies.</p>';
        $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'botanical' ) ) . '" class="wnb-card-action">View Gallery &rarr;</a>';
        $out .= '</div>';

        // 2. Cannabis Education
        $out .= '<div class="wnb-card wnb-topic-card">';
        $out .= '<span class="wnb-topic-icon" aria-hidden="true">&#128218;</span>';
        $out .= '<h3>Cannabis Education</h3>';
        $out .= '<p>Foundational curriculum covering terpenes, chemovars, extraction dynamics, and plant physiology.</p>';
        $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'explore' ) ) . '" class="wnb-card-action">Browse Lessons &rarr;</a>';
        $out .= '</div>';

        // 3. Culinary & Recipes
        $out .= '<div class="wnb-card wnb-topic-card">';
        $out .= '<span class="wnb-topic-icon" aria-hidden="true">&#127859;</span>';
        $out .= '<h3>Culinary &amp; Recipes</h3>';
        $out .= '<p>Precision decarboxylation guides, low-temperature infusions, and safe holistic preparations.</p>';
        $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'explore' ) ) . '" class="wnb-card-action">Explore Recipes &rarr;</a>';
        $out .= '</div>';

        // 4. What's New
        $out .= '<div class="wnb-card wnb-topic-card">';
        $out .= '<span class="wnb-topic-icon" aria-hidden="true">&#128240;</span>';
        $out .= '<h3>What&#8217;s New</h3>';
        $out .= '<p>Official release updates, curriculum notes, and lounge announcements.</p>';
        $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'whats-new' ) ) . '" class="wnb-card-action">See Updates &rarr;</a>';
        $out .= '</div>';

        $out .= '</div>'; // .wnb-card-grid
        $out .= '</section>';

        // Ask Budly Guide Card
        $out .= '<section class="wnb-card wnb-budly-callout">';
        $out .= '<div class="wnb-budly-content">';
        $out .= '<h2>Have Questions About Strains or Science?</h2>';
        $out .= '<p>Ask Budly, our AI-powered botanical guide. Ask about cultivars, terpene profiles, aroma vocabulary, or cooking temperatures anytime.</p>';
        $out .= '<a href="' . self::esc_url( self::get_budly_url() ) . '" class="wnb-btn wnb-btn-gold" target="_blank" rel="noopener">Open Ask Budly &rarr;</a>';
        $out .= '</div>';
        $out .= '</section>';

        $out .= '</div>'; // .wnb-screen-home

        return $out;
    }

    /**
     * Screen 02: Explore Directory
     */
    private static function render_explore( int $user_id, array $state ): string {
        $level = $state['level'] ?? 'none';
        $catalog = self::get_content_items();

        $out = '<div class="wnb-screen wnb-screen-explore">';
        $out .= '<div class="wnb-screen-header">';
        $out .= '<h1 class="wnb-screen-title">Explore Educational Resources</h1>';
        $out .= '<p class="wnb-screen-lede">Curated cannabis education, practical botanical science, and culinary guides focusing on plant biology, culinary craft, and mindful appreciation.</p>';
        $out .= '</div>';

        // Filter Pills with mobile scroll indicator
        $out .= '<div class="wnb-filter-bar-wrapper">';
        $out .= '<div class="wnb-filter-bar" role="toolbar" aria-label="Content Filters">';
        $out .= '<button type="button" class="wnb-filter-pill is-active" data-filter="all">All Content</button>';
        $out .= '<button type="button" class="wnb-filter-pill" data-filter="education">Education</button>';
        $out .= '<button type="button" class="wnb-filter-pill" data-filter="botanical">Botanical</button>';
        $out .= '<button type="button" class="wnb-filter-pill" data-filter="culinary">Culinary</button>';
        $out .= '<button type="button" class="wnb-filter-pill" data-filter="exclusive">Exclusives</button>';
        $out .= '</div>';
        $out .= '<div class="wnb-filter-fade-cue" aria-hidden="true"></div>';
        $out .= '</div>';
        $out .= '<div class="wnb-filter-helper-cue" aria-hidden="true">Swipe for more &rarr;</div>';

        if ( empty( $catalog ) ) {
            // Honest pending-content empty state in release builds
            $out .= '<div class="wnb-card wnb-empty-card" style="text-align: center; padding: 48px 24px;">';
            $out .= '<span class="wnb-topic-icon" aria-hidden="true">&#128218;</span>';
            $out .= '<h2>Educational Guides In Preparation</h2>';
            $out .= '<p style="max-width: 540px; margin: 12px auto 24px; color: var(--wnb-muted); font-size: 0.95rem; line-height: 1.55;">';
            $out .= 'Curated educational guides and botanical lessons are currently in editorial production and undergoing review. Explore our member benefits or ask Budly for plant science guidance in the interim.';
            $out .= '</p>';
            $out .= '<div style="display: flex; justify-content: center; gap: 12px; flex-wrap: wrap;">';
            $out .= '<a href="' . self::esc_url( self::get_budly_url() ) . '" class="wnb-btn wnb-btn-gold" target="_blank" rel="noopener">Ask Budly &rarr;</a>';
            $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'benefits' ) ) . '" class="wnb-btn wnb-btn-outline">View Member Benefits</a>';
            $out .= '</div>';
            $out .= '</div>';
        } else {
            // Content Cards Grid
            $out .= '<div class="wnb-card-grid wnb-grid-3 wnb-content-items-grid">';
            foreach ( $catalog as $item ) {
                $required_level = $item['tier'];
                $can_access = ( 'none' !== $level ) && Membership_Entitlements::can_access_level( $user_id, $required_level );
                $detail_url = self::get_lounge_url( 'detail', $item['id'] );

                $badge_class = 'wnb-access-pass';
                $badge_text = 'Pass';
                if ( 'member' === $required_level ) {
                    $badge_class = 'wnb-access-member';
                    $badge_text = 'Member';
                } elseif ( 'elite' === $required_level ) {
                    $badge_class = 'wnb-access-elite';
                    $badge_text = 'Elite VIP';
                }

                $out .= '<article class="wnb-card wnb-content-card" data-category="' . self::esc_attr( $item['category'] ) . '" data-tier="' . self::esc_attr( $required_level ) . '">';
                $out .= '<div class="wnb-card-meta">';
                $out .= '<span class="wnb-category-tag">' . self::esc_html( ucfirst( $item['category'] ) ) . '</span>';
                $out .= '<span class="wnb-access-tag ' . self::esc_attr( $badge_class ) . '">' . self::esc_html( $badge_text ) . '</span>';
                $out .= '</div>';

                $out .= '<h2 class="wnb-card-title"><a href="' . self::esc_url( $detail_url ) . '">' . self::esc_html( $item['title'] ) . '</a></h2>';
                $out .= '<p class="wnb-card-excerpt">' . self::esc_html( $item['summary'] ) . '</p>';

                $out .= '<div class="wnb-card-footer">';
                $out .= '<span class="wnb-read-time">' . self::esc_html( $item['read_time'] ) . '</span>';
                if ( $can_access ) {
                    $out .= '<a href="' . self::esc_url( $detail_url ) . '" class="wnb-btn wnb-btn-sm wnb-btn-primary">Read Guide &rarr;</a>';
                } else {
                    $out .= '<a href="' . self::esc_url( $detail_url ) . '" class="wnb-btn wnb-btn-sm wnb-btn-outline wnb-locked-cta">&#128274; ' . self::esc_html( $badge_text ) . '</a>';
                }
                $out .= '</div>';
                $out .= '</article>';
            }
            $out .= '</div>'; // .wnb-card-grid
        }

        $out .= '</div>'; // .wnb-screen-explore
        return $out;
    }

    /**
     * Screen 03: Content Detail (with strict server-side entitlement check)
     */
    private static function render_detail( int $user_id, array $state, string $item_id ): string {
        $level = $state['level'] ?? 'none';
        $catalog = self::get_content_items();

        if ( ! isset( $catalog[ $item_id ] ) ) {
            if ( ! self::is_fixture_mode_enabled() ) {
                return self::render_empty_state( 'Resource In Editorial Review', 'Educational guides and curriculum lessons are currently undergoing final editorial verification and will appear here upon publication.' );
            }
            return self::render_empty_state( 'Resource Not Found', 'The requested educational guide or lesson does not exist or has been archived.' );
        }

        $item = $catalog[ $item_id ];
        $required_level = $item['tier'];
        $can_access = ( 'none' !== $level ) && Membership_Entitlements::can_access_level( $user_id, $required_level );

        // Strict Server-Side Gate: If user does not have permission, display the Restricted State
        if ( ! $can_access ) {
            return self::render_restricted_state( $item, $level );
        }

        $explore_url = self::get_lounge_url( 'explore' );

        $out = '<div class="wnb-screen wnb-screen-detail">';

        // Breadcrumbs
        $out .= '<nav class="wnb-breadcrumbs" aria-label="Breadcrumbs">';
        $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'home' ) ) . '">Lounge</a> &rsaquo; ';
        $out .= '<a href="' . self::esc_url( $explore_url ) . '">Explore</a> &rsaquo; ';
        $out .= '<span>' . self::esc_html( $item['title'] ) . '</span>';
        $out .= '</nav>';

        // Article Header
        $out .= '<article class="wnb-article" aria-labelledby="wnb-article-title">';
        $out .= '<header class="wnb-article-header">';
        $out .= '<div class="wnb-article-meta">';
        $out .= '<span class="wnb-category-tag">' . self::esc_html( ucfirst( $item['category'] ) ) . '</span>';
        $out .= '<span class="wnb-read-time">' . self::esc_html( $item['read_time'] ) . '</span>';
        $out .= '</div>';
        $out .= '<h1 id="wnb-article-title" class="wnb-article-title">' . self::esc_html( $item['title'] ) . '</h1>';
        $out .= '<p class="wnb-article-lede">' . self::esc_html( $item['summary'] ) . '</p>';
        $out .= '</header>';

        // Full Article Body
        $out .= '<div class="wnb-article-body">';
        $out .= $item['body_html'];
        $out .= '</div>';

        // Key Takeaways Block
        if ( ! empty( $item['key_takeaways'] ) && is_array( $item['key_takeaways'] ) ) {
            $out .= '<aside class="wnb-card wnb-takeaways-card" aria-label="Key Takeaways">';
            $out .= '<h3>Key Takeaways</h3>';
            $out .= '<ul>';
            foreach ( $item['key_takeaways'] as $point ) {
                $out .= '<li>' . self::esc_html( $point ) . '</li>';
            }
            $out .= '</ul>';
            $out .= '</aside>';
        }

        // Compliance & Educational Notice
        $out .= '<div class="wnb-compliance-notice">';
        $out .= '<p><small><em>Educational Material: This resource is provided strictly for botanical plant science, culinary technique, and cultural education. It does not constitute medical advice or health claims. Cannabis regulations vary by jurisdiction.</em></small></p>';
        $out .= '</div>';

        // Article Footer & Navigation
        $out .= '<footer class="wnb-article-footer">';
        $out .= '<a href="' . self::esc_url( $explore_url ) . '" class="wnb-btn wnb-btn-outline">&larr; Back to Explore</a>';
        $out .= '<a href="' . self::esc_url( self::get_budly_url() ) . '" class="wnb-btn wnb-btn-gold" target="_blank" rel="noopener">Discuss with Budly</a>';
        $out .= '</footer>';

        $out .= '</article>';
        $out .= '</div>'; // .wnb-screen-detail

        return $out;
    }

    /**
     * Screen 04: Botanical Discovery Gallery & Exhibits
     */
    private static function render_botanical( int $user_id, array $state, string $strain_id ): string {
        $strains = self::get_botanical_strains();

        // If a specific strain is selected, render strain exhibit detail
        if ( ! empty( $strain_id ) ) {
            if ( isset( $strains[ $strain_id ] ) ) {
                return self::render_botanical_detail( $strains[ $strain_id ] );
            }
            foreach ( $strains as $sid => $s ) {
                $slug = self::sanitize_key( str_replace( ' ', '-', $s['name'] ) );
                if ( $slug === self::sanitize_key( $strain_id ) ) {
                    return self::render_botanical_detail( $s );
                }
            }
            if ( ! self::is_fixture_mode_enabled() ) {
                return self::render_empty_state( 'Botanical Exhibit In Preparation', 'The requested botanical exhibit is currently in preparation and undergoing editorial verification.' );
            }
            return self::render_empty_state( 'Exhibit Not Found', 'The requested botanical strain exhibit does not exist in Volume I.' );
        }

        $out = '<div class="wnb-screen wnb-screen-botanical">';
        $out .= '<div class="wnb-screen-header">';
        $out .= '<div class="wnb-welcome-kicker">Botanical Collection &bull; Volume I</div>';
        $out .= '<h1 class="wnb-screen-title">Botanical Discovery Gallery</h1>';
        $out .= '<p class="wnb-screen-lede">Botanical cultivar profiles, lineage traditions, and sensory vocabulary aligned with the Botanical Coloring Collection Volume I.</p>';
        $out .= '</div>';

        if ( empty( $strains ) ) {
            // Honest pending-content empty state in release builds
            $out .= '<div class="wnb-card wnb-empty-card" style="text-align: center; padding: 48px 24px;">';
            $out .= '<span class="wnb-topic-icon" aria-hidden="true">&#127807;</span>';
            $out .= '<h2>Botanical Gallery In Preparation</h2>';
            $out .= '<p style="max-width: 540px; margin: 12px auto 24px; color: var(--wnb-muted); font-size: 0.95rem; line-height: 1.55;">';
            $out .= 'Cultivar exhibits and botanical profiles for Volume I are currently in preparation and will be published following editorial verification. You can consult Ask Budly for botanical guidance anytime.';
            $out .= '</p>';
            $out .= '<div style="display: flex; justify-content: center; gap: 12px; flex-wrap: wrap;">';
            $out .= '<a href="' . self::esc_url( self::get_budly_url() ) . '" class="wnb-btn wnb-btn-gold" target="_blank" rel="noopener">Ask Budly &rarr;</a>';
            $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'home' ) ) . '" class="wnb-btn wnb-btn-outline">&larr; Return to Lounge Home</a>';
            $out .= '</div>';
            $out .= '</div>';
        } else {
            $out .= '<div class="wnb-card-grid wnb-grid-2">';
            foreach ( $strains as $id => $s ) {
                $exhibit_url = self::get_lounge_url( 'botanical', $id );
                $out .= '<article class="wnb-card wnb-botanical-card">';
                $out .= '<div class="wnb-botanical-header">';
                $out .= '<span class="wnb-strain-number">Exhibit #' . self::esc_html( (string) $s['number'] ) . '</span>';
                $out .= '<span class="wnb-access-tag wnb-access-pass">Public &amp; Pass</span>';
                $out .= '</div>';

                $out .= '<h2 class="wnb-strain-title"><a href="' . self::esc_url( $exhibit_url ) . '">' . self::esc_html( $s['name'] ) . '</a></h2>';
                $out .= '<p class="wnb-lineage-text"><strong>Lineage:</strong> ' . $s['lineage'] . '</p>';
                $out .= '<p class="wnb-card-excerpt">' . self::esc_html( $s['overview'] ) . '</p>';

                $out .= '<div class="wnb-aroma-chips">';
                foreach ( $s['aroma'] as $aroma ) {
                    $out .= '<span class="wnb-chip">' . self::esc_html( $aroma ) . '</span>';
                }
                $out .= '</div>';

                $out .= '<div class="wnb-card-footer">';
                $out .= '<a href="' . self::esc_url( $exhibit_url ) . '" class="wnb-btn wnb-btn-sm wnb-btn-primary">View Botanical Exhibit &rarr;</a>';
                $out .= '</div>';
                $out .= '</article>';
            }
            $out .= '</div>'; // .wnb-card-grid
        }

        $out .= '</div>'; // .wnb-screen-botanical
        return $out;
    }

    /**
     * Botanical Single Exhibit View
     */
    private static function render_botanical_detail( array $strain ): string {
        $botanical_url = self::get_lounge_url( 'botanical' );

        $out = '<div class="wnb-screen wnb-screen-botanical-detail">';
        $out .= '<nav class="wnb-breadcrumbs" aria-label="Breadcrumbs">';
        $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'home' ) ) . '">Lounge</a> &rsaquo; ';
        $out .= '<a href="' . self::esc_url( $botanical_url ) . '">Botanical Discovery</a> &rsaquo; ';
        $out .= '<span>' . self::esc_html( $strain['name'] ) . '</span>';
        $out .= '</nav>';

        $out .= '<article class="wnb-card wnb-botanical-exhibit">';
        $out .= '<header class="wnb-exhibit-header">';
        $out .= '<div class="wnb-welcome-kicker">Botanical Exhibit #' . self::esc_html( (string) $strain['number'] ) . '</div>';
        $out .= '<h1 class="wnb-strain-title">' . self::esc_html( $strain['name'] ) . '</h1>';
        $out .= '<p class="wnb-scientific-name"><em>Cannabis sativa L.</em> cultivar / chemovar</p>';
        $out .= '</header>';

        $out .= '<div class="wnb-exhibit-grid">';

        // Lineage & Botany
        $out .= '<div class="wnb-detail-block">';
        $out .= '<h3>Genetic Lineage</h3>';
        $out .= '<p>' . $strain['lineage'] . '</p>';
        $out .= '<p class="wnb-note">' . self::esc_html( $strain['lineage_note'] ) . '</p>';
        $out .= '</div>';

        // Aroma & Terpene Vocabulary
        $out .= '<div class="wnb-detail-block">';
        $out .= '<h3>Aroma &amp; Terpene Vocabulary</h3>';
        $out .= '<div class="wnb-aroma-chips">';
        foreach ( $strain['aroma'] as $aroma ) {
            $out .= '<span class="wnb-chip">' . self::esc_html( $aroma ) . '</span>';
        }
        $out .= '</div>';
        $out .= '<p class="wnb-note">Terpene notes provide qualitative sensory orientation. Chemical ratios vary by batch and farm.</p>';
        $out .= '</div>';

        // Chemical & Aroma Profile
        $out .= '<div class="wnb-detail-block wnb-grid-full">';
        $out .= '<h3>Chemical &amp; Aroma Profile</h3>';
        $out .= '<p>' . self::esc_html( $strain['chemistry'] ) . '</p>';
        $out .= '</div>';

        $out .= '</div>'; // .wnb-exhibit-grid

        // Botanical Disclaimer & Compliance
        $out .= '<div class="wnb-compliance-notice">';
        $out .= '<p><small><em>Botanical Science Notice: Cultivar profiles, terpene notes, and genetic lineages are presented for botanical education and cultural plant history only. Chemical profiles and sensory qualities vary by phenotype, farm terroir, and laboratory testing.</em></small></p>';
        $out .= '</div>';

        $out .= '<footer class="wnb-exhibit-footer">';
        $out .= '<a href="' . self::esc_url( $botanical_url ) . '" class="wnb-btn wnb-btn-outline">&larr; Back to Gallery</a>';
        $out .= '<a href="' . self::esc_url( self::get_budly_url() ) . '" class="wnb-btn wnb-btn-gold" target="_blank" rel="noopener">Ask Budly About This Strain</a>';
        $out .= '</footer>';

        $out .= '</article>';
        $out .= '</div>'; // .wnb-screen-botanical-detail

        return $out;
    }

    /**
     * Screen 05: Member Benefits & Entitlements Overview
     */
    private static function render_benefits( int $user_id, array $state ): string {
        $level = $state['level'] ?? 'none';
        $discount = (int) ( $state['discount_percentage'] ?? 0 );
        $badge_label = $state['badge_label'] ?? 'Guest';

        $out = '<div class="wnb-screen wnb-screen-benefits">';
        $out .= '<div class="wnb-screen-header">';
        $out .= '<h1 class="wnb-screen-title">Lounge Membership Benefits</h1>';
        $out .= '<p class="wnb-screen-lede">Compare verified tier benefits and access privileges across the Wake&#8217;n&#8217;Bake Lounge ecosystem.</p>';
        $out .= '</div>';

        // Current Status Card
        $out .= '<div class="wnb-card wnb-status-card">';
        $out .= '<h2>Your Current Entitlement Status</h2>';
        $out .= '<div class="wnb-status-details">';
        $out .= '<div><strong>Current Tier:</strong> ' . self::esc_html( $badge_label ) . '</div>';
        $out .= '<div><strong>Store Discount:</strong> ' . self::esc_html( (string) $discount ) . '% on eligible products</div>';
        $out .= '<div><strong>Community Access:</strong> ' . ( ! empty( $state['community_access'] ) ? 'Active &#10003;' : 'None' ) . '</div>';
        $out .= '</div>';
        $out .= '<div class="wnb-status-actions">';
        $out .= '<a href="' . self::esc_url( self::get_subscriptions_url() ) . '" class="wnb-btn wnb-btn-sm wnb-btn-outline">Manage Subscriptions</a>';
        $out .= '</div>';
        $out .= '</div>';

        // 3-Tier Comparison Matrix
        $out .= '<div class="wnb-card-grid wnb-grid-3 wnb-tier-matrix">';

        // Tier 1: Lounge Pass
        $out .= '<div class="wnb-card wnb-tier-card' . ( 'pass' === $level ? ' is-current' : '' ) . '">';
        $out .= '<h3>Wake&#8217;n&#8217;Bake Lounge Pass</h3>';
        $out .= '<div class="wnb-tier-price">Free</div>';
        $out .= '<ul class="wnb-benefits-checklist">';
        $out .= '<li>&#10003; Full Lounge Community entry</li>';
        $out .= '<li>&#10003; Foundations educational curriculum</li>';
        $out .= '<li>&#10003; Botanical Volume I exhibit gallery</li>';
        $out .= '<li>&#10003; Full Ask Budly conversational guidance</li>';
        $out .= '<li>&times; No store discounts (0%)</li>';
        $out .= '</ul>';
        if ( 'none' === $level ) {
            $out .= '<a href="' . self::esc_url( self::get_pass_product_url() ) . '" class="wnb-btn wnb-btn-sm wnb-btn-gold">Claim Free Pass</a>';
        }
        $out .= '</div>';

        // Tier 2: Lounge Member
        $out .= '<div class="wnb-card wnb-tier-card' . ( 'member' === $level ? ' is-current' : '' ) . '">';
        $out .= '<h3>Wake&#8217;n&#8217;Bake Lounge Member</h3>';
        $out .= '<div class="wnb-tier-price">$9.99 / month</div>';
        $out .= '<ul class="wnb-benefits-checklist">';
        $out .= '<li>&#10003; All Lounge Pass privileges</li>';
        $out .= '<li>&#10003; <strong>10% eligible store discount</strong></li>';
        $out .= '<li>&#10003; Early drop product access</li>';
        $out .= '<li>&#10003; Member-only educational library</li>';
        $out .= '<li>&#10003; Priority event invitations</li>';
        $out .= '</ul>';
        if ( 'elite' !== $level && 'member' !== $level ) {
            $out .= '<a href="' . self::esc_url( self::get_product_url( 'lounge-member' ) ) . '" class="wnb-btn wnb-btn-sm wnb-btn-primary">Upgrade to Member</a>';
        }
        $out .= '</div>';

        // Tier 3: Lounge Elite VIP
        $out .= '<div class="wnb-card wnb-tier-card' . ( 'elite' === $level ? ' is-current' : '' ) . '">';
        $out .= '<h3>Wake&#8217;n&#8217;Bake Lounge Elite</h3>';
        $out .= '<div class="wnb-tier-price">$24.99 / month</div>';
        $out .= '<ul class="wnb-benefits-checklist">';
        $out .= '<li>&#10003; All Lounge Member privileges</li>';
        $out .= '<li>&#10003; <strong>25% eligible store discount</strong></li>';
        $out .= '<li>&#10003; VIP Elite community lounge sections</li>';
        $out .= '<li>&#10003; First drop guaranteed reservations</li>';
        $out .= '<li>&#10003; Monthly curated Budly premium content</li>';
        $out .= '</ul>';
        if ( 'elite' !== $level ) {
            $out .= '<a href="' . self::esc_url( self::get_product_url( 'lounge-elite' ) ) . '" class="wnb-btn wnb-btn-sm wnb-btn-gold">Upgrade to Elite</a>';
        }
        $out .= '</div>';

        $out .= '</div>'; // .wnb-card-grid
        $out .= '<div class="wnb-card wnb-exclusions-card">';
        $out .= '<p class="wnb-discount-exclusions-note"><small><strong>* Discount Exclusions:</strong> Eligible store discounts apply to regular-priced items only. Excludes other memberships, bulk products, class payment-plan products, sale or clearance items, and transactions using coupons.</small></p>';
        $out .= '</div>';
        $out .= '</div>'; // .wnb-screen-benefits

        return $out;
    }

    /**
     * Screen 06: What's New Chronological Feed
     */
    private static function render_whats_new( int $user_id, array $state ): string {
        $updates = self::get_whats_new_items();

        $out = '<div class="wnb-screen wnb-screen-whats-new">';
        $out .= '<div class="wnb-screen-header">';
        $out .= '<h1 class="wnb-screen-title">What&#8217;s New in The Lounge</h1>';
        $out .= '<p class="wnb-screen-lede">Official release updates, curriculum notes, and lounge announcements.</p>';
        $out .= '</div>';

        if ( empty( $updates ) ) {
            // Useful empty state in release builds
            $out .= '<div class="wnb-card wnb-empty-card" style="text-align: center; padding: 48px 24px;">';
            $out .= '<span class="wnb-topic-icon" aria-hidden="true">&#128240;</span>';
            $out .= '<h2>No Current Announcements</h2>';
            $out .= '<p style="max-width: 540px; margin: 12px auto 24px; color: var(--wnb-muted); font-size: 0.95rem; line-height: 1.55;">';
            $out .= 'Official announcements and curriculum release logs will be posted here as new materials are published. Check back soon for upcoming updates!';
            $out .= '</p>';
            $out .= '<div style="display: flex; justify-content: center; gap: 12px; flex-wrap: wrap;">';
            $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'home' ) ) . '" class="wnb-btn wnb-btn-primary">&larr; Return to Lounge Home</a>';
            $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'benefits' ) ) . '" class="wnb-btn wnb-btn-outline">View Member Benefits</a>';
            $out .= '</div>';
            $out .= '</div>';
        } else {
            $out .= '<div class="wnb-timeline">';
            foreach ( $updates as $u ) {
                $out .= '<article class="wnb-card wnb-timeline-card">';
                $out .= '<time class="wnb-timeline-date">' . self::esc_html( $u['date'] ) . '</time>';
                $out .= '<h2>' . $u['title'] . '</h2>';
                $out .= '<p>' . self::esc_html( $u['summary'] ) . '</p>';
                $out .= '</article>';
            }
            $out .= '</div>';
        }

        $out .= '</div>'; // .wnb-screen-whats-new
        return $out;
    }

    /**
     * Screen 07: Account Return Hub
     */
    private static function render_account( int $user_id, array $state ): string {
        $level = $state['level'] ?? 'none';
        $badge_label = $state['badge_label'] ?? 'Guest';

        $account_url = self::get_account_url();
        $subs_url = self::get_subscriptions_url();

        $out = '<div class="wnb-screen wnb-screen-account">';
        $out .= '<div class="wnb-screen-header">';
        $out .= '<h1 class="wnb-screen-title">Account &amp; Subscriptions Return</h1>';
        $out .= '<p class="wnb-screen-lede">Manage your WooCommerce account details, active subscriptions, payment methods, and order history.</p>';
        $out .= '</div>';

        $out .= '<div class="wnb-card wnb-account-card-panel">';
        $out .= '<div class="wnb-card-meta">';
        $out .= '<span>Verified Account: User #' . self::esc_html( (string) $user_id ) . '</span>';
        $out .= '<span class="ccc-wnb-badge ccc-wnb-badge-' . self::esc_attr( $state['badge_key'] ?? 'none' ) . '">' . self::esc_html( $badge_label ) . '</span>';
        $out .= '</div>';

        $out .= '<div class="wnb-card-grid wnb-grid-2">';
        $out .= '<a href="' . self::esc_url( $account_url ) . '" class="wnb-account-nav-btn">';
        $out .= '<strong>WooCommerce Dashboard</strong>';
        $out .= '<span>View recent orders, addresses, and account details</span>';
        $out .= '</a>';

        $out .= '<a href="' . self::esc_url( $subs_url ) . '" class="wnb-account-nav-btn">';
        $out .= '<strong>Manage Subscriptions</strong>';
        $out .= '<span>Update payment methods, view renewal dates, or change tiers</span>';
        $out .= '</a>';
        $out .= '</div>';

        $out .= '<div class="wnb-account-return-footer">';
        $out .= '<a href="' . self::esc_url( self::get_lounge_url( 'home' ) ) . '" class="wnb-btn wnb-btn-primary">&larr; Return to Lounge Home</a>';
        $out .= '</div>';

        $out .= '</div>'; // .wnb-card
        $out .= '</div>'; // .wnb-screen-account

        return $out;
    }

    /**
     * Renders Restricted State for gated content (Strict Zero-Leak Gate).
     */
    private static function render_restricted_state( array $item, string $current_level ): string {
        $required_level = $item['tier'];
        $tier_name = ( 'elite' === $required_level ) ? 'Lounge Elite VIP' : 'Lounge Member';
        $upgrade_slug = ( 'elite' === $required_level ) ? 'lounge-elite' : 'lounge-member';
        $upgrade_url = self::get_product_url( $upgrade_slug );
        $explore_url = self::get_lounge_url( 'explore' );

        $out = '<div class="wnb-screen wnb-screen-restricted">';
        $out .= '<div class="wnb-card wnb-restricted-card">';
        $out .= '<span class="wnb-restricted-icon" aria-hidden="true">&#128274;</span>';
        $out .= '<h1>Exclusive Member Resource</h1>';
        $out .= '<p class="wnb-restricted-intro">This educational guide is reserved for active <strong>' . self::esc_html( $tier_name ) . '</strong> subscribers.</p>';

        $out .= '<div class="wnb-restricted-explanation">';
        $out .= '<p>Your current tier is: <strong>' . self::esc_html( ucfirst( $current_level ) ) . '</strong>.</p>';
        $out .= '<p>Active members unlock our complete curriculum library, practical extraction guides, early product drop access, and eligible store discounts.</p>';
        $out .= '</div>';

        $out .= '<div class="wnb-restricted-actions">';
        $out .= '<a href="' . self::esc_url( $upgrade_url ) . '" class="wnb-btn wnb-btn-gold">Upgrade to ' . self::esc_html( $tier_name ) . ' &rarr;</a>';
        $out .= '<a href="' . self::esc_url( $explore_url ) . '" class="wnb-btn wnb-btn-outline">Browse Other Topics</a>';
        $out .= '</div>';

        $out .= '</div>'; // .wnb-restricted-card
        $out .= '</div>'; // .wnb-screen-restricted

        return $out;
    }

    /**
     * Renders Empty/Error State fallback.
     */
    private static function render_empty_state( string $title, string $message ): string {
        $home_url = self::get_lounge_url( 'home' );

        $out = '<div class="wnb-screen wnb-screen-empty">';
        $out .= '<div class="wnb-card wnb-empty-card">';
        $out .= '<h1>' . self::esc_html( $title ) . '</h1>';
        $out .= '<p>' . self::esc_html( $message ) . '</p>';
        $out .= '<a href="' . self::esc_url( $home_url ) . '" class="wnb-btn wnb-btn-primary">&larr; Return to Lounge Home</a>';
        $out .= '</div>';
        $out .= '</div>';

        return $out;
    }

    /**
     * Educational Content Catalog.
     * In release builds (default), returns an empty array to ensure unapproved educational articles
     * or lessons do not leak before editorial ratification.
     */
    public static function get_content_items(): array {
        if ( ! self::is_fixture_mode_enabled() ) {
            return array();
        }
        return self::get_dev_fixture_content_items();
    }

    /**
     * Development-only educational fixtures.
     */
    public static function get_dev_fixture_content_items(): array {
        return array(
            'VOL1-EDU-01' => array(
                'id'            => 'VOL1-EDU-01',
                'category'      => 'education',
                'tier'          => 'pass',
                'title'         => 'Anatomy of a Cannabis Flower: Resins, Trichomes & Chemovars',
                'summary'       => 'Understand the biological structures of the female cannabis inflorescence and how glandular trichomes produce secondary metabolites.',
                'read_time'     => '8 min read',
                'body_html'     => '<p>The female cannabis flower, or inflorescence, represents one of the most sophisticated chemical factories in the botanical kingdom. Rather than a single uniform blossom, it consists of dense clusters of individual florets arranged along a central floral axis.</p><h3>Glandular Trichomes</h3><p>The primary site of cannabinoid and terpene synthesis is the capitate-stalked glandular trichome. These microscopic, mushroom-like structures feature a multicellular secretory head where enzymatic pathways convert precursor lipids into CBGA, which is then transformed into THCA, CBDA, or CBCA by specific synthases.</p><h3>Bracts and Calyxes</h3><p>Surrounding the seed site are small, specialized modified leaves known as bracts. Heavily coated with resin glands, these bracts protect developing seeds in wild populations while maximizing aromatic terpene retention in unfertilized (sinsemilla) cultivation.</p>',
                'key_takeaways' => array(
                    'Capitate-stalked trichomes produce the vast majority of active cannabinoids and terpenes.',
                    'Flower density and structure are adaptations designed to shelter resin heads from UV degradation.',
                    'Certificates of analysis provide the true chemical fingerprint of any given flower specimen.',
                ),
            ),
            'VOL1-EDU-02' => array(
                'id'            => 'VOL1-EDU-02',
                'category'      => 'education',
                'tier'          => 'pass',
                'title'         => 'Introduction to Terpenes & Aroma Science',
                'summary'       => 'How volatile hydrocarbons shape plant sensory vocabulary and influence consumer perception.',
                'read_time'     => '6 min read',
                'body_html'     => '<p>Terpenes are organic hydrocarbons synthesized by plants to deter herbivores, attract pollinators, and resist environmental stress. In cannabis, over 150 distinct terpenes have been identified.</p><h3>Major Terpenes</h3><p>The most abundant terpenes include myrcene (earthy, herbal), limonene (bright citrus), beta-caryophyllene (spicy, peppery), and alpha-pinene (fresh pine). Caryophyllene uniquely binds directly to peripheral CB2 receptors, bridging the functional gap between terpenes and cannabinoids.</p>',
                'key_takeaways' => array(
                    'Aroma descriptors reflect measurable chemical ratios of volatile hydrocarbons.',
                    'Beta-caryophyllene acts as a dietary cannabinoid with CB2 receptor affinity.',
                    'Proper storage in sealed, cool, dark environments preserves delicate monoterpenes.',
                ),
            ),
            'VOL1-EDU-03' => array(
                'id'            => 'VOL1-EDU-03',
                'category'      => 'education',
                'tier'          => 'pass',
                'title'         => 'Cultivar Name vs. Chemovar Reality',
                'summary'       => 'Why market names are cultural traditions rather than chemical guarantees, and how to read a certificate of analysis.',
                'read_time'     => '5 min read',
                'body_html'     => '<p>In commercial markets, cannabis is frequently sold under nostalgic or creative strain names. However, botanical science categorizes cannabis into chemovars (chemical varieties) based on quantitative cannabinoid and terpene ratios.</p><p>Genetics establish potential, but cultivation environment, harvest timing, drying kinetics, and packaging determine finished chemistry. Always refer to batch-specific lab testing.</p>',
                'key_takeaways' => array(
                    'Chemovar categorization groups material by measurable chemical composition.',
                    'Two products with the same name from different farms may display distinct terpene profiles.',
                    'Third-party laboratory analysis is the gold standard of product verification.',
                ),
            ),
            'VOL1-MBR-01' => array(
                'id'            => 'VOL1-MBR-01',
                'category'      => 'education',
                'tier'          => 'member',
                'title'         => 'Advanced Extraction & Cannabinoid Synergy',
                'summary'       => 'A technical exploration of full-spectrum versus isolate formulations and minor cannabinoid interactions.',
                'read_time'     => '10 min read',
                'body_html'     => '<p>Modern extraction technologies allow targeted isolation of specific cannabinoids or comprehensive preservation of the entire native phytocomplex. Understanding these processing methodologies empowers conscious consumption.</p><h3>Full-Spectrum vs. Distillate</h3><p>Distillation isolates cannabinoids through boiling-point fractionation, stripping native terpenes and flavonoids. Full-spectrum solventless processes preserve the full entourage of minor compounds including CBG, CBN, and CBC.</p>',
                'key_takeaways' => array(
                    'Full-spectrum extracts maintain native botanical ratios of secondary metabolites.',
                    'Minor cannabinoids modulate receptor affinity and biological responsiveness.',
                    'Solventless mechanical extraction avoids chemical solvent exposure.',
                ),
            ),
            'VOL1-ELT-01' => array(
                'id'            => 'VOL1-ELT-01',
                'category'      => 'education',
                'tier'          => 'elite',
                'title'         => 'Masterclass: Terpene Preservation & Solventless Curation',
                'summary'       => 'Elite VIP masterclass on trichome head maturity, cold curing kinetics, and hash rosin terroir.',
                'read_time'     => '14 min read',
                'body_html'     => '<p>Welcome to the Elite VIP masterclass. Solventless hash rosin represents the pinnacle of botanical artisanal curation, relying strictly on ice water, agitation, micron sieving, and gentle pneumatic heat and pressure.</p><h3>Cold Curing Kinetics</h3><p>Sealed cold-curing allows volatile monoterpenes to separate into a terpene-rich fraction while cannabinoids nucleate into delicate microcrystalline structures, preserving aromatic intensity that would otherwise vaporize at room temperature.</p>',
                'key_takeaways' => array(
                    '73u to 120u micron sieves isolate the cleanest mature glandular heads.',
                    'Cold curing prevents oxidative degradation of delicate monoterpenes like ocimene and terpinolene.',
                    'Terroir, soil biology, and curing humidity directly influence solventless yield and aroma.',
                ),
            ),
            'VOL1-CUL-01' => array(
                'id'            => 'VOL1-CUL-01',
                'category'      => 'culinary',
                'tier'          => 'pass',
                'title'         => 'Infused Basics: Precision Decarboxylation Guide',
                'summary'       => 'The foundational thermal science of converting inactive cannabinoid acids into bioavailable forms.',
                'read_time'     => '7 min read',
                'body_html'     => '<p>In raw cannabis, cannabinoids exist in carboxylated acidic forms (THCA, CBDA). Ingestion of unheated flower does not produce intoxicating effects because THCA has low affinity for CB1 receptors. Heat removes the carboxyl group (COOH) as carbon dioxide.</p><h3>Time & Temperature Curves</h3><p>Optimal decarboxylation for THCA occurs between 240&deg;F and 245&deg;F (115&deg;C - 118&deg;C) for 35 to 45 minutes in a sealed oven bag or mason jar to prevent aromatic terpene loss.</p>',
                'key_takeaways' => array(
                    'Decarboxylation is a time-and-temperature dependent chemical reaction.',
                    'Sealed baking vessels trap evaporating terpenes and recondense them onto flower material.',
                    'Excessive heat or duration degrades active THC into sedative CBN.',
                ),
            ),
            'VOL1-MBR-02' => array(
                'id'            => 'VOL1-MBR-02',
                'category'      => 'culinary',
                'tier'          => 'member',
                'title'         => 'Culinary Craft: Low-Temperature Botanical Olive Oil Infusion',
                'summary'       => 'Member-exclusive master recipe for infusing premium extra virgin olive oil with delicate monoterpene preservation.',
                'read_time'     => '9 min read',
                'body_html'     => '<p>Cannabinoids are lipophilic (fat-soluble) molecules requiring a lipid carrier for efficient systemic absorption. Extra virgin olive oil provides rich monounsaturated fats and polyphenols that complement earthy cannabis profiles.</p><h3>The Gentle Double-Boiler Method</h3><p>Maintain infusion temperature strictly between 160&deg;F and 175&deg;F (70&deg;C - 80&deg;C) for 3 to 4 hours. Stir periodically and filter through unbleached cheesecloth without squeezing to prevent bitter chlorophyll extraction.</p>',
                'key_takeaways' => array(
                    'Medium-chain and monounsaturated lipids optimize cannabinoid bioavailability.',
                    'Gentle heat below 180&deg;F prevents thermal oxidation of olive oil polyphenols.',
                    'Never squeeze the straining cloth to avoid extracting vegetal tannins.',
                ),
            ),
        );
    }

    /**
     * Botanical Strains Catalog (Volume I).
     * In release builds (default), returns an empty array to ensure unapproved cultivar descriptions
     * do not leak before editorial ratification.
     */
    public static function get_botanical_strains(): array {
        if ( ! self::is_fixture_mode_enabled() ) {
            return array();
        }
        return self::get_dev_fixture_botanical_strains();
    }

    /**
     * Development-only botanical fixtures.
     */
    public static function get_dev_fixture_botanical_strains(): array {
        return array(
            'VOL1-S01' => array(
                'number'       => 1,
                'name'         => 'Blue Dream',
                'lineage'      => 'Blueberry &times; Haze',
                'lineage_note' => 'A legendary Northern California cultivar known for balanced resin production and sweet berry aromatics.',
                'overview'     => 'A market staple with high visual appeal, featuring long tapered floral clusters with warm orange pistils.',
                'aroma'        => array( 'Berry', 'Sweet', 'Herbal', 'Pine', 'Citrus' ),
                'chemistry'    => 'Predominantly THC-dominant chemovar with abundant myrcene, alpha-pinene, and beta-caryophyllene.',
            ),
            'VOL1-S09' => array(
                'number'       => 9,
                'name'         => 'Granddaddy Purple',
                'lineage'      => 'Big Bud &times; Purple Urkle',
                'lineage_note' => 'Originating in the California Bay Area, renowned for deep anthocyanin pigmentation and grape-berry notes.',
                'overview'     => 'Dense, frosty purple bracts with sweet wine-like and berry aromatics.',
                'aroma'        => array( 'Grape', 'Berry', 'Earth', 'Floral' ),
                'chemistry'    => 'THC-dominant chemovar with prominent myrcene and caryophyllene terpenes.',
            ),
            'VOL1-S13' => array(
                'number'       => 13,
                'name'         => 'Jack Herer',
                'lineage'      => 'Haze &times; Northern Lights #5 &times; Shiva Skunk',
                'lineage_note' => 'Named in tribute to the renowned cannabis activist and author of The Emperor Wears No Clothes.',
                'overview'     => 'Distinctive terpinolene-forward sensory profile with clean pine, spice, and herbal clarity.',
                'aroma'        => array( 'Pine', 'Spice', 'Wood', 'Herbal' ),
                'chemistry'    => 'Terpinolene-dominant chemovar with supporting pinene and caryophyllene.',
            ),
            'VOL1-S18' => array(
                'number'       => 18,
                'name'         => 'Sour Diesel',
                'lineage'      => 'Chemdawg &times; Super Skunk',
                'lineage_note' => 'Iconic East Coast cultivar tracing its heritage to the early 1990s underground scene.',
                'overview'     => 'Pungent, fuel-like, and sharp citrus aromatics with high trichome stalk density.',
                'aroma'        => array( 'Diesel', 'Pungent', 'Citrus', 'Earthy' ),
                'chemistry'    => 'Limonene, myrcene, and beta-caryophyllene blend resulting in an intense gasoline-like aroma.',
            ),
        );
    }

    /**
     * What's New Chronological Announcements.
     * In release builds (default), returns an empty array to avoid unapproved claims or promises.
     */
    public static function get_whats_new_items(): array {
        if ( ! self::is_fixture_mode_enabled() ) {
            return array();
        }
        return self::get_dev_fixture_whats_new_items();
    }

    /**
     * Development-only What's New fixtures.
     */
    public static function get_dev_fixture_whats_new_items(): array {
        return array(
            array(
                'date'    => 'October 10, 2026',
                'title'   => 'Wake&#8217;n&#8217;Bake Lounge Entitlements &amp; Account Experience v0.4.0',
                'summary' => 'Unified member account dashboard cards, post-order welcome routing, and mobile-responsive botanical presentation verified across Pass, Member, and Elite tiers.',
            ),
            array(
                'date'    => 'October 8, 2026',
                'title'   => 'Botanical Discovery Volume I Founding Cultivar Preview',
                'summary' => 'Initial cultivar profiles (Blue Dream, Granddaddy Purple, Jack Herer, Sour Diesel) and foundational plant anatomy concepts aligned with Botanical Collection Volume I.',
            ),
            array(
                'date'    => 'September 20, 2026',
                'title'   => 'Three-Tier Commercial Synchronization Established',
                'summary' => 'Pass, Member, and Elite tier architecture harmonized across store checkout, subscription management, and deterministic server-side entitlement rules.',
            ),
        );
    }

    /**
     * URL Helpers.
     */
    public static function get_lounge_url( string $view = 'home', string $item = '' ): string {
        $base = function_exists( 'home_url' ) ? home_url( '/wakenbake-lounge-community/' ) : 'https://cccultivate.com/wakenbake-lounge-community/';
        $params = array();
        if ( 'home' !== $view ) {
            $params['view'] = $view;
        }
        if ( ! empty( $item ) ) {
            $params['item'] = $item;
        }
        return empty( $params ) ? $base : self::add_query_arg( $params, $base );
    }

    public static function get_budly_url( string $view = 'home' ): string {
        $base = function_exists( 'home_url' ) ? home_url( '/ask-budly/' ) : 'https://cccultivate.com/ask-budly/';
        $params = array(
            'page_context' => 'wakenbake_lounge_home',
            'view'         => self::sanitize_key( $view ),
        );
        return self::add_query_arg( $params, $base );
    }

    public static function get_account_url(): string {
        return function_exists( 'wc_get_page_permalink' ) ? wc_get_page_permalink( 'myaccount' ) : 'https://cccultivate.com/my-account/';
    }

    public static function get_subscriptions_url(): string {
        if ( function_exists( 'wc_get_endpoint_url' ) && function_exists( 'wc_get_page_permalink' ) ) {
            return wc_get_endpoint_url( 'subscriptions', '', wc_get_page_permalink( 'myaccount' ) );
        }
        return 'https://cccultivate.com/my-account/subscriptions/';
    }

    public static function get_pass_product_url(): string {
        return function_exists( 'home_url' ) ? home_url( '/product/lounge-pass/' ) : 'https://cccultivate.com/product/lounge-pass/';
    }

    public static function get_product_url( string $slug ): string {
        return function_exists( 'home_url' ) ? home_url( '/product/' . $slug . '/' ) : 'https://cccultivate.com/product/' . $slug . '/';
    }

    /**
     * Interactive Client-side Script for Instant View Switching.
     */
    private static function render_interactive_script(): string {
        return '<script>
(function() {
    function initLoungeInteractions() {
        var app = document.getElementById("wnb-lounge-root");
        if (!app) return;

        // Content filtering pills
        var filterPills = app.querySelectorAll(".wnb-filter-pill");
        var contentCards = app.querySelectorAll(".wnb-content-card");

        filterPills.forEach(function(pill) {
            pill.addEventListener("click", function() {
                filterPills.forEach(function(p) { p.classList.remove("is-active"); });
                pill.classList.add("is-active");
                var category = pill.getAttribute("data-filter");

                contentCards.forEach(function(card) {
                    if (category === "all") {
                        card.style.display = "";
                    } else if (category === "exclusive") {
                        var tier = card.getAttribute("data-tier");
                        card.style.display = (tier === "member" || tier === "elite") ? "" : "none";
                    } else {
                        var cat = card.getAttribute("data-category");
                        card.style.display = (cat === category) ? "" : "none";
                    }
                });
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initLoungeInteractions);
    } else {
        initLoungeInteractions();
    }
})();
</script>';
    }

    /**
     * Returns the comprehensive botanical emerald-and-gold styling CSS.
     */
    public static function get_css(): string {
        return '
/* ==========================================================================
   Wake\'n\'Bake Lounge UI: Emerald & Gold Botanical Design System (MX-4A)
   ========================================================================== */
.wnb-lounge-app {
    --wnb-bg-dark: #0d1711;
    --wnb-panel: #17261d;
    --wnb-surface: #213629;
    --wnb-gold: #dfbd6a;
    --wnb-gold-hover: #f1cf7c;
    --wnb-leaf: #9acb6b;
    --wnb-emerald: #2d5a27;
    --wnb-emerald-dark: #1b3817;
    --wnb-ink: #f5f0df;
    --wnb-muted: #bcc4b9;
    --wnb-line: rgba(245, 240, 223, 0.12);
    --wnb-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
    background-color: var(--wnb-bg-dark);
    color: var(--wnb-ink);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif;
    border-radius: 12px;
    padding: 0 0 70px;
    position: relative;
    box-sizing: border-box;
    overflow: hidden;
}
.wnb-lounge-app * { box-sizing: border-box; }
.wnb-lounge-app a { color: inherit; text-decoration: none; }
.wnb-lounge-app h1,
.wnb-lounge-app h2,
.wnb-lounge-app h3,
.wnb-lounge-app h4,
.wnb-lounge-app h5,
.wnb-lounge-app h6 {
    color: var(--wnb-ink);
    font-family: Georgia, serif;
    letter-spacing: -0.01em;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
    margin-top: 0;
}

/* Header */
.wnb-header {
    background: rgba(13, 23, 17, 0.95);
    border-bottom: 1px solid var(--wnb-line);
    padding: 16px 24px;
    backdrop-filter: blur(12px);
}
.wnb-header-inner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1200px;
    margin: 0 auto;
    flex-wrap: wrap;
    gap: 16px;
}
.wnb-brand { display: flex; align-items: center; gap: 12px; }
.wnb-brand-emblem {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border: 1px solid var(--wnb-gold);
    border-radius: 50%;
    color: var(--wnb-gold);
    font-size: 1.4rem;
}
.wnb-brand-title { display: block; font-family: Georgia, serif; font-size: 1.25rem; font-weight: 700; color: var(--wnb-ink); }
.wnb-brand-subtitle { display: block; font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--wnb-gold); }
.wnb-header-actions { display: flex; align-items: center; gap: 14px; }
.wnb-header-link { font-size: 0.9rem; color: var(--wnb-muted); font-weight: 600; }
.wnb-header-link:hover { color: var(--wnb-gold); }
.wnb-header-budly { color: var(--wnb-leaf); }
.wnb-guest-tag { font-size: 0.8rem; color: var(--wnb-muted); padding: 4px 10px; border-radius: 14px; background: rgba(255,255,255,0.06); }

/* Desktop Navigation */
.wnb-desktop-nav {
    background: var(--wnb-panel);
    border-bottom: 1px solid var(--wnb-line);
    padding: 0 24px;
}
.wnb-nav-list {
    display: flex;
    list-style: none;
    margin: 0 auto;
    padding: 0;
    max-width: 1200px;
    overflow-x: auto;
    gap: 4px;
}
.wnb-nav-link {
    display: inline-block;
    padding: 14px 18px;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--wnb-muted);
    border-bottom: 2px solid transparent;
    transition: color 0.2s, border-color 0.2s;
    white-space: nowrap;
}
.wnb-nav-link:hover { color: var(--wnb-ink); }
.wnb-nav-link.is-active {
    color: var(--wnb-gold);
    border-bottom-color: var(--wnb-gold);
}

/* Main Content Wrapper */
.wnb-lounge-main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 24px;
    min-height: 60vh;
}

/* Cards & Layout */
.wnb-card {
    background: var(--wnb-panel);
    border: 1px solid var(--wnb-line);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: var(--wnb-shadow);
}
.wnb-card-grid {
    display: grid;
    gap: 20px;
    margin-bottom: 30px;
}
.wnb-grid-2 { grid-template-columns: repeat(2, 1fr); }
.wnb-grid-3 { grid-template-columns: repeat(3, 1fr); }
.wnb-grid-4 { grid-template-columns: repeat(4, 1fr); }

/* Welcome Hero */
.wnb-welcome-hero {
    background: linear-gradient(135deg, rgba(33, 54, 41, 0.92), rgba(13, 23, 17, 0.98));
    border: 1px solid rgba(223, 189, 106, 0.35);
    text-align: center;
    padding: 44px 24px;
    position: relative;
}
.wnb-welcome-hero::before {
    content: "";
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 84px;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--wnb-gold), transparent);
}
.wnb-welcome-kicker {
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--wnb-gold);
    margin-bottom: 12px;
    text-shadow: 0 1px 1px rgba(0, 0, 0, 0.5);
}
.wnb-hero-title {
    font-family: Georgia, serif;
    font-size: 2.6rem;
    line-height: 1.15;
    margin: 0 0 16px;
    color: var(--wnb-ink);
    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
}
.wnb-hero-lede {
    font-size: 1.15rem;
    max-width: 720px;
    margin: 0 auto 28px;
    color: var(--wnb-muted);
    line-height: 1.6;
}
.wnb-welcome-cta-group { display: flex; justify-content: center; gap: 14px; flex-wrap: wrap; }
.wnb-tier-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 16px;
    border-radius: 20px;
    background: rgba(45, 90, 39, 0.4);
    border: 1px solid var(--wnb-emerald);
    font-size: 0.9rem;
    color: var(--wnb-ink);
}

/* Featured Section */
.wnb-section-title {
    font-family: Georgia, serif;
    font-size: 1.6rem;
    color: var(--wnb-ink);
    margin: 32px 0 20px;
    padding-bottom: 12px;
    position: relative;
    letter-spacing: -0.01em;
}
.wnb-section-title::after {
    content: "";
    position: absolute;
    bottom: 0;
    left: 0;
    width: 48px;
    height: 2px;
    background: linear-gradient(90deg, var(--wnb-gold), rgba(223, 189, 106, 0.15));
    border-radius: 2px;
}
.wnb-featured-card {
    background: linear-gradient(135deg, var(--wnb-surface), var(--wnb-panel));
    border: 1px solid rgba(154, 203, 107, 0.3);
}
.wnb-card-badge {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--wnb-leaf);
    margin-bottom: 8px;
}
.wnb-card-title {
    font-family: Georgia, serif;
    font-size: 1.45rem;
    margin: 0 0 12px;
    color: var(--wnb-ink);
}
.wnb-card-title a:hover { color: var(--wnb-gold); }
.wnb-card-summary, .wnb-card-excerpt {
    color: var(--wnb-muted);
    font-size: 0.95rem;
    line-height: 1.55;
    margin: 0 0 18px;
}
.wnb-card-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    border-top: 1px solid var(--wnb-line);
    padding-top: 14px;
}

/* Topic Cards in Grid */
.wnb-topic-card {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    text-align: left;
}
.wnb-topic-icon { font-size: 2rem; margin-bottom: 12px; display: inline-block; }
.wnb-topic-card h3 { font-family: Georgia, serif; font-size: 1.2rem; margin: 0 0 8px; color: var(--wnb-ink); }
.wnb-topic-card p { font-size: 0.9rem; color: var(--wnb-muted); line-height: 1.45; margin: 0 0 16px; flex-grow: 1; }
.wnb-card-action { font-weight: 600; font-size: 0.9rem; color: var(--wnb-gold); }
.wnb-card-action:hover { color: var(--wnb-gold-hover); }

/* Buttons */
.wnb-btn {
    display: inline-block;
    padding: 12px 24px;
    border-radius: 6px;
    font-weight: 600;
    font-size: 0.95rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    min-height: 44px;
    line-height: 20px;
}
.wnb-btn-sm { padding: 8px 16px; font-size: 0.85rem; min-height: 38px; }
.wnb-btn-gold {
    background: var(--wnb-gold);
    color: #0d1711 !important;
    border: 1px solid var(--wnb-gold);
}
.wnb-btn-gold:hover { background: var(--wnb-gold-hover); }
.wnb-btn-primary {
    background: var(--wnb-emerald);
    color: #ffffff !important;
    border: 1px solid var(--wnb-emerald);
}
.wnb-btn-primary:hover { background: var(--wnb-emerald-dark); }
.wnb-btn-outline {
    background: transparent;
    color: var(--wnb-ink) !important;
    border: 1px solid var(--wnb-line);
}
.wnb-btn-outline:hover { border-color: var(--wnb-gold); color: var(--wnb-gold) !important; }

/* Access Tags */
.wnb-access-tag {
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 3px 8px;
    border-radius: 4px;
}
.wnb-access-pass { background: rgba(188, 196, 185, 0.15); color: var(--wnb-muted); }
.wnb-access-member { background: rgba(154, 203, 107, 0.2); color: var(--wnb-leaf); border: 1px solid rgba(154, 203, 107, 0.3); }
.wnb-access-elite { background: rgba(223, 189, 106, 0.2); color: var(--wnb-gold); border: 1px solid rgba(223, 189, 106, 0.4); }

/* Filter Bar */
.wnb-filter-bar-wrapper {
    position: relative;
    width: 100%;
}
.wnb-filter-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 6px;
    overflow-x: auto;
    padding-bottom: 6px;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
}
.wnb-filter-pill {
    background: var(--wnb-panel);
    border: 1px solid var(--wnb-line);
    color: var(--wnb-muted);
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 0.85rem;
    cursor: pointer;
    font-weight: 600;
    white-space: nowrap;
    flex-shrink: 0;
}
.wnb-filter-pill:hover { color: var(--wnb-ink); border-color: var(--wnb-muted); }
.wnb-filter-pill.is-active {
    background: var(--wnb-surface);
    color: var(--wnb-gold);
    border-color: var(--wnb-gold);
}
.wnb-filter-fade-cue {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 6px;
    width: 36px;
    pointer-events: none;
    background: linear-gradient(to right, transparent, var(--wnb-bg-dark));
    border-radius: 0 4px 4px 0;
}
.wnb-filter-helper-cue {
    display: none;
    font-size: 0.74rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--wnb-gold);
    text-align: right;
    margin-bottom: 20px;
    padding-right: 4px;
}
@media (max-width: 600px) {
    .wnb-filter-helper-cue { display: block; }
}

/* Botanical Exhibits */
.wnb-botanical-card { border-left: 3px solid var(--wnb-leaf); }
.wnb-strain-number { font-size: 0.78rem; color: var(--wnb-muted); letter-spacing: 0.1em; text-transform: uppercase; }
.wnb-strain-title { font-family: Georgia, serif; font-size: 1.5rem; margin: 8px 0; color: var(--wnb-ink); }
.wnb-lineage-text { font-size: 0.95rem; color: var(--wnb-gold); margin: 0 0 10px; }
.wnb-aroma-chips { display: flex; gap: 6px; flex-wrap: wrap; margin: 12px 0 16px; }
.wnb-chip {
    font-size: 0.75rem;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--wnb-line);
    padding: 3px 9px;
    border-radius: 12px;
    color: var(--wnb-muted);
}

/* Content Detail View */
.wnb-breadcrumbs { font-size: 0.85rem; color: var(--wnb-muted); margin-bottom: 20px; }
.wnb-breadcrumbs a { color: var(--wnb-gold); }
.wnb-article { background: var(--wnb-panel); border: 1px solid var(--wnb-line); border-radius: 12px; padding: 36px; box-shadow: var(--wnb-shadow); }
.wnb-article-header { margin-bottom: 28px; border-bottom: 1px solid var(--wnb-line); padding-bottom: 24px; }
.wnb-article-meta { display: flex; gap: 12px; margin-bottom: 12px; font-size: 0.82rem; color: var(--wnb-muted); }
.wnb-article-title { font-family: Georgia, serif; font-size: 2.2rem; color: var(--wnb-ink); margin: 0 0 16px; }
.wnb-article-lede { font-size: 1.15rem; color: var(--wnb-muted); line-height: 1.6; margin: 0; }
.wnb-article-body { font-size: 1.05rem; line-height: 1.7; color: #d9dfd5; margin-bottom: 32px; }
.wnb-article-body h3 { font-family: Georgia, serif; font-size: 1.4rem; color: var(--wnb-gold); margin: 28px 0 12px; }
.wnb-takeaways-card {
    background: rgba(223, 189, 106, 0.06);
    border: 1px solid rgba(223, 189, 106, 0.3);
    border-radius: 8px;
    padding: 20px;
    margin: 32px 0;
}
.wnb-takeaways-card h3 { margin: 0 0 12px; font-size: 1.1rem; color: var(--wnb-gold); }
.wnb-takeaways-card ul { margin: 0; padding-left: 20px; }
.wnb-takeaways-card li { margin-bottom: 8px; line-height: 1.5; color: var(--wnb-ink); }
.wnb-article-footer { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--wnb-line); padding-top: 24px; flex-wrap: wrap; gap: 14px; }
.wnb-compliance-notice {
    margin: 20px 0 16px;
    padding: 12px 16px;
    background: rgba(245, 240, 223, 0.03);
    border-left: 2px solid var(--wnb-muted);
    border-radius: 4px;
    color: var(--wnb-muted);
    font-size: 0.82rem;
    line-height: 1.5;
}

/* Restricted State */
.wnb-restricted-card {
    text-align: center;
    padding: 48px 24px;
    border: 2px solid var(--wnb-gold);
    background: linear-gradient(135deg, rgba(33, 54, 41, 0.95), var(--wnb-panel));
    max-width: 640px;
    margin: 40px auto;
}
.wnb-restricted-icon { font-size: 3rem; display: block; margin-bottom: 16px; }
.wnb-restricted-card h1 { font-family: Georgia, serif; font-size: 1.8rem; margin: 0 0 12px; color: var(--wnb-gold); }
.wnb-restricted-intro { font-size: 1.05rem; color: var(--wnb-ink); margin-bottom: 16px; }
.wnb-restricted-explanation { color: var(--wnb-muted); font-size: 0.95rem; line-height: 1.55; margin-bottom: 28px; }
.wnb-restricted-actions { display: flex; justify-content: center; gap: 14px; flex-wrap: wrap; }

/* Benefits Tier Cards */
.wnb-tier-matrix { margin-top: 24px; }
.wnb-tier-card { display: flex; flex-direction: column; text-align: left; }
.wnb-tier-card.is-current { border: 2px solid var(--wnb-gold); background: rgba(223, 189, 106, 0.04); }
.wnb-tier-price { font-size: 1.5rem; font-weight: 700; color: var(--wnb-gold); margin: 8px 0 16px; }
.wnb-benefits-checklist { list-style: none; padding: 0; margin: 0 0 24px; flex-grow: 1; }
.wnb-benefits-checklist li { margin-bottom: 10px; font-size: 0.92rem; color: var(--wnb-muted); line-height: 1.4; }
.wnb-exclusions-card {
    background: transparent;
    border: 1px solid var(--wnb-line);
    padding: 14px 18px;
    margin-top: 18px;
    border-radius: 8px;
}
.wnb-discount-exclusions-note {
    margin: 0;
    font-size: 0.82rem;
    color: var(--wnb-muted);
    line-height: 1.5;
}

/* Timeline for What\'s New */
.wnb-timeline-card { border-left: 3px solid var(--wnb-gold); margin-bottom: 16px; }
.wnb-timeline-date { display: block; font-size: 0.8rem; font-weight: 700; color: var(--wnb-gold); letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 8px; }
.wnb-timeline-card h2 { font-family: Georgia, serif; font-size: 1.3rem; margin: 0 0 8px; color: var(--wnb-ink); }

/* Mobile Bottom Navigation Bar */
.wnb-mobile-bottom-bar {
    display: none;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(13, 23, 17, 0.98);
    border-top: 1px solid var(--wnb-line);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    z-index: 1000;
    padding: 6px 12px max(8px, env(safe-area-inset-bottom, 8px));
    justify-content: space-around;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.45);
}
.wnb-mobile-tab {
    display: flex;
    flex-direction: column;
    align-items: center;
    color: var(--wnb-muted);
    font-size: 0.72rem;
    font-weight: 600;
    min-width: 0;
    flex: 1;
    padding: 4px 0;
    min-height: 48px;
    justify-content: center;
}
.wnb-mobile-tab:hover { color: var(--wnb-ink); }
.wnb-mobile-tab.is-active { color: var(--wnb-gold); }
.wnb-tab-icon { font-size: 1.25rem; line-height: 1; margin-bottom: 3px; }

/* Full-page screenshot capture mode support */
.wnb-fullpage-capture .wnb-mobile-bottom-bar {
    position: static;
    margin-top: 24px;
}

/* Responsive Breakpoints (1440px, 820px, 430px, 390px, 375px, 320px) */
@media (max-width: 1024px) {
    .wnb-grid-4 { grid-template-columns: repeat(2, 1fr); }
    .wnb-grid-3 { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 820px) {
    .wnb-grid-2 { grid-template-columns: 1fr; }
    .wnb-hero-title { font-size: 2.1rem; line-height: 1.16; }
    .wnb-article { padding: 24px; }
    .wnb-article-title { font-size: 1.8rem; }
}
@media (max-width: 600px) {
    .wnb-lounge-app { padding-bottom: 95px; }
    .wnb-lounge-main { padding: 20px 14px; }
    .wnb-desktop-nav { display: none; }
    .wnb-mobile-bottom-bar { display: flex; }
    .wnb-grid-4, .wnb-grid-3, .wnb-grid-2 { grid-template-columns: 1fr; gap: 16px; }
    .wnb-hero-title { font-size: 1.85rem; line-height: 1.18; margin: 0 0 14px; }
    .wnb-hero-lede { font-size: 1rem; margin: 0 auto 20px; }
    .wnb-section-title { font-size: 1.35rem; margin: 24px 0 16px; padding-bottom: 10px; }
    .wnb-section-title::after { width: 36px; }
    .wnb-article { padding: 20px 16px; }
    .wnb-article-title { font-size: 1.5rem; line-height: 1.22; }
    .wnb-welcome-cta-group, .wnb-restricted-actions, .wnb-status-actions { flex-direction: column; width: 100%; gap: 12px; }
    .wnb-welcome-cta-group .wnb-btn, .wnb-restricted-actions .wnb-btn, .wnb-status-actions .wnb-btn { width: 100%; }
    .wnb-card-footer { flex-direction: column; align-items: flex-start; }
    .wnb-card-footer .wnb-btn { width: 100%; }

    /* Prevent floating Ask Budly button from overlapping the mobile bottom bar */
    .budly-floating-button,
    #budly-floating-button,
    [data-budly-floating] {
        bottom: calc(76px + env(safe-area-inset-bottom, 0px)) !important;
        right: 16px !important;
        z-index: 998 !important;
    }
}
@media (max-width: 400px) {
    .wnb-header { padding: 12px 10px; }
    .wnb-header-inner { gap: 10px; }
    .wnb-brand { gap: 8px; }
    .wnb-brand-emblem { width: 34px; height: 34px; font-size: 1.2rem; }
    .wnb-brand-title { font-size: 1.05rem; }
    .wnb-brand-subtitle { font-size: 0.65rem; }
    .wnb-lounge-main { padding: 14px 10px; }
    .wnb-card { padding: 16px 12px; margin-bottom: 18px; }
    .wnb-welcome-hero { padding: 28px 12px; }
    .wnb-welcome-kicker { font-size: 0.72rem; letter-spacing: 0.12em; margin-bottom: 8px; }
    .wnb-hero-title { font-size: 1.55rem; line-height: 1.2; margin: 0 0 12px; }
    .wnb-hero-lede { font-size: 0.92rem; line-height: 1.5; margin: 0 auto 18px; }
    .wnb-section-title { font-size: 1.25rem; margin: 20px 0 14px; }
    .wnb-mobile-bottom-bar { padding: 4px 6px max(6px, env(safe-area-inset-bottom, 6px)); }
    .wnb-mobile-tab { font-size: 0.68rem; min-height: 44px; }
    .wnb-tab-icon { font-size: 1.15rem; }
}
@media (max-width: 340px) {
    .wnb-brand-title { font-size: 0.95rem; }
    .wnb-brand-emblem { width: 30px; height: 30px; font-size: 1.1rem; }
    .wnb-header-actions { gap: 8px; }
    .wnb-header-link { font-size: 0.8rem; }
    .wnb-guest-tag { display: none; }
    .wnb-hero-title { font-size: 1.4rem; }
    .wnb-btn { padding: 10px 16px; font-size: 0.9rem; }
}
';
    }
}
