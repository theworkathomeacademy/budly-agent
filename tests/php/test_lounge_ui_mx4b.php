<?php
/**
 * Phase MX-4B: Lounge UI & Navigation Test Suite
 *
 * Verifies the ratified MX-1 through MX-4A Lounge UI presentation:
 * - Release-mode content suppression: unapproved educational articles, lessons,
 *   botanical cultivar profiles, and announcements are disabled by default.
 * - Honest pending-content states for Featured Learning, Explore Directory,
 *   Botanical Discovery, and What's New.
 * - Absence of unsupported scientific authority claims.
 * - Zero-leak security across direct URLs and restricted states.
 * - Development fixture mode verification: tier gating and entitlement enforcement.
 * - Commercial integrity: $0, $9.99, $24.99 and 0%, 10%, 25% discount rules.
 * - Responsive navigation and input sanitization.
 */

define( 'ABSPATH', __DIR__ );

// Load test harness
require_once __DIR__ . '/wnb_membership_integration.php';

echo "\n=======================================================\n";
echo "STARTING PHASE MX-4B LOUNGE UI VERIFICATION\n";
echo "=======================================================\n\n";

$pass_count = 0;
function assert_lounge( $condition, $message ) {
    global $pass_count;
    if ( ! $condition ) {
        throw new RuntimeException( "ASSERTION FAILED: " . $message );
    }
    $pass_count++;
    echo "  [PASS] " . $message . "\n";
}

// -------------------------------------------------------------
// SECTION 1: REGISTRATION & INITIALIZATION
// -------------------------------------------------------------
echo "--- 1. SHORTCODE & CLASS INITIALIZATION ---\n";

assert_lounge( isset( $shortcodes['ccc_wnb_lounge'] ), "Shortcode [ccc_wnb_lounge] is registered" );
assert_lounge( class_exists( 'CCC\WNB\Lounge_UI' ), "Lounge_UI class exists" );

$css = CCC\WNB\Lounge_UI::get_css();
assert_lounge( false !== strpos( $css, '--wnb-emerald' ), "Lounge CSS contains emerald palette variable" );
assert_lounge( false !== strpos( $css, '--wnb-gold' ), "Lounge CSS contains warm gold accent variable" );
assert_lounge( false !== strpos( $css, '@media (max-width: 820px)' ), "Lounge CSS contains tablet 820px breakpoint" );
assert_lounge( false !== strpos( $css, '@media (max-width: 600px)' ), "Lounge CSS contains mobile breakpoint" );
assert_lounge( false !== strpos( $css, '.wnb-mobile-bottom-bar' ), "Lounge CSS contains mobile bottom nav styling" );

// =============================================================
// PART A: DEFAULT RELEASE MODE SUPPRESSION (FIXTURES OFF)
// =============================================================
echo "\n=======================================================\n";
echo "PART A: DEFAULT RELEASE-MODE SUPPRESSION VERIFICATION\n";
echo "=======================================================\n\n";

assert_lounge( false === CCC\WNB\Lounge_UI::is_fixture_mode_enabled(), "Release Mode: Fixture mode is disabled by default" );
assert_lounge( empty( CCC\WNB\Lounge_UI::get_content_items() ), "Release Mode: Content items catalog returns empty array" );
assert_lounge( empty( CCC\WNB\Lounge_UI::get_botanical_strains() ), "Release Mode: Botanical strains catalog returns empty array" );
assert_lounge( empty( CCC\WNB\Lounge_UI::get_whats_new_items() ), "Release Mode: What's New items catalog returns empty array" );

// -------------------------------------------------------------
// SECTION 2: SCREEN 01 - LOUNGE HOME (RELEASE MODE)
// -------------------------------------------------------------
echo "\n--- 2. SCREEN 01: LOUNGE HOME (RELEASE MODE) ---\n";

// Guest (User 10)
$current_user_id = 10;
$_GET = array();
$html_guest_home = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_guest_home, 'Public Orientation' ) || false !== strpos( $html_guest_home, 'data-user-tier="none"' ), "Home (Guest): Displays Public/Guest orientation status" );
assert_lounge( false !== strpos( $html_guest_home, 'Claim Free Lounge Pass' ), "Home (Guest): Displays Claim Free Lounge Pass CTA" );
assert_lounge( false !== strpos( $html_guest_home, 'https://cccultivate.com/product/lounge-pass/' ), "Home (Guest): Links to product/lounge-pass/" );
assert_lounge( false !== strpos( $html_guest_home, 'Ask Budly' ), "Home (Guest): Displays Ask Budly entry" );
assert_lounge( false !== strpos( $html_guest_home, 'Botanical Discovery' ), "Home (Guest): Displays Botanical Discovery entry" );

// Featured card: Honest pending state in release builds
assert_lounge( false !== strpos( $html_guest_home, 'Foundations Curriculum In Preparation' ), "Home Featured: Shows honest pending-curriculum title" );
assert_lounge( false !== strpos( $html_guest_home, 'Curriculum Status &bull; In Editorial Review' ), "Home Featured: Shows In Editorial Review status badge" );
assert_lounge( false !== strpos( $html_guest_home, 'Release Pending' ), "Home Featured: Shows Release Pending tag" );
assert_lounge( false === strpos( $html_guest_home, 'Anatomy of a Cannabis Flower: Resins, Trichomes &amp; Chemovars' ), "Home Featured (Zero-Leak): Unapproved featured lesson title is NOT rendered" );
assert_lounge( false === strpos( $html_guest_home, 'Glandular Trichomes' ), "Home Featured (Zero-Leak): Unapproved lesson text is NOT rendered" );

// Pass Member (User 9)
$current_user_id = 9;
$orders[1]->status = 'cancelled';
$orders[0]->status = 'cancelled';
$html_pass_home = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_pass_home, 'Lounge Pass' ), "Home (Pass): Displays Lounge Pass tier pill" );

// Member (User 7 with active membership order)
$current_user_id = 7;
$orders[0]->status = 'active';
$orders[1]->status = 'cancelled';
$html_member_home = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_member_home, 'Member' ), "Home (Member): Displays Member tier pill" );

// Elite (User 7 with active elite order)
$orders[1]->status = 'active';
$html_elite_home = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_elite_home, 'Elite' ), "Home (Elite): Displays Elite tier pill" );

// -------------------------------------------------------------
// SECTION 3: SCREEN 02 - EXPLORE DIRECTORY (RELEASE MODE)
// -------------------------------------------------------------
echo "\n--- 3. SCREEN 02: EXPLORE DIRECTORY (RELEASE MODE) ---\n";

$_GET = array( 'view' => 'explore' );
$html_explore_release = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_explore_release, 'Explore Educational Resources' ), "Explore: Renders library heading" );
assert_lounge( false !== strpos( $html_explore_release, 'Educational Guides In Preparation' ), "Explore (Release): Renders honest empty-state heading" );
assert_lounge( false !== strpos( $html_explore_release, 'in editorial production' ), "Explore (Release): Informs user content is in editorial production" );

// Authority claim removals:
assert_lounge( false === strpos( $html_explore_release, 'peer-reviewed plant science' ), "Explore (Authority): Unsupported 'peer-reviewed plant science' claim removed" );
assert_lounge( false === strpos( $html_explore_release, 'verified curriculum' ), "Explore (Authority): Unsupported 'verified curriculum' claim removed" );

// Content suppression (Zero-Leak):
assert_lounge( false === strpos( $html_explore_release, 'Anatomy of a Cannabis Flower' ), "Explore (Zero-Leak): Pass lesson 1 NOT rendered" );
assert_lounge( false === strpos( $html_explore_release, 'Advanced Extraction' ), "Explore (Zero-Leak): Member lesson NOT rendered" );
assert_lounge( false === strpos( $html_explore_release, 'Masterclass: Terpene Preservation' ), "Explore (Zero-Leak): Elite lesson NOT rendered" );
assert_lounge( false === strpos( $html_explore_release, 'Precision Decarboxylation Guide' ), "Explore (Zero-Leak): Culinary guide NOT rendered" );

// -------------------------------------------------------------
// SECTION 4: SCREEN 03 - CONTENT DETAIL (RELEASE MODE DIRECT URLS)
// -------------------------------------------------------------
echo "\n--- 4. SCREEN 03: CONTENT DETAIL (RELEASE MODE DIRECT URLS) ---\n";

// Direct URL to Pass item
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-EDU-01' );
$html_detail_rel_01 = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_detail_rel_01, 'Resource In Editorial Review' ), "Detail (Direct URL): Renders honest Resource In Editorial Review notice" );
assert_lounge( false !== strpos( $html_detail_rel_01, 'final editorial verification' ), "Detail (Direct URL): Explains verification status" );
assert_lounge( false === strpos( $html_detail_rel_01, 'Glandular Trichomes' ), "Detail (Direct URL, Zero-Leak): Lesson body is NOT rendered" );
assert_lounge( false === strpos( $html_detail_rel_01, 'Capitate-stalked' ), "Detail (Direct URL, Zero-Leak): Botanical lesson text is NOT rendered" );

// Direct URL to Member item
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-MBR-01' );
$html_detail_rel_mbr = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_detail_rel_mbr, 'Resource In Editorial Review' ), "Detail (Member Item Direct URL): Returns editorial review notice" );
assert_lounge( false === strpos( $html_detail_rel_mbr, 'Full-Spectrum vs. Distillate' ), "Detail (Member Item Direct URL, Zero-Leak): Protected body text NOT rendered" );

// Direct URL to Elite item
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-ELT-01' );
$html_detail_rel_elt = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_detail_rel_elt, 'Resource In Editorial Review' ), "Detail (Elite Item Direct URL): Returns editorial review notice" );
assert_lounge( false === strpos( $html_detail_rel_elt, 'Cold Curing Kinetics' ), "Detail (Elite Item Direct URL, Zero-Leak): Elite body text NOT rendered" );

// -------------------------------------------------------------
// SECTION 5: SCREEN 04 - BOTANICAL DISCOVERY (RELEASE MODE)
// -------------------------------------------------------------
echo "\n--- 5. SCREEN 04: BOTANICAL DISCOVERY (RELEASE MODE) ---\n";

// Gallery View
$_GET = array( 'view' => 'botanical' );
$html_botanical_rel = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_botanical_rel, 'Botanical Discovery Gallery' ), "Botanical (Release): Displays section heading" );
assert_lounge( false !== strpos( $html_botanical_rel, 'Botanical Gallery In Preparation' ), "Botanical (Release): Displays honest pending-gallery state" );
assert_lounge( false !== strpos( $html_botanical_rel, 'Cultivar exhibits and botanical profiles for Volume I are currently in preparation' ), "Botanical (Release): Explains exhibit preparation" );

// Authority claim removals:
assert_lounge( false === strpos( $html_botanical_rel, 'laboratory chemistry analysis' ), "Botanical (Authority): 'laboratory chemistry analysis' claim removed" );
assert_lounge( false === strpos( $html_botanical_rel, 'verified plant genetics' ), "Botanical (Authority): 'verified plant genetics' claim removed" );

// Cultivar suppression (Zero-Leak):
assert_lounge( false === strpos( $html_botanical_rel, 'Blue Dream' ), "Botanical (Zero-Leak): Blue Dream cultivar NOT rendered" );
assert_lounge( false === strpos( $html_botanical_rel, 'Granddaddy Purple' ), "Botanical (Zero-Leak): Granddaddy Purple NOT rendered" );
assert_lounge( false === strpos( $html_botanical_rel, 'Jack Herer' ), "Botanical (Zero-Leak): Jack Herer NOT rendered" );
assert_lounge( false === strpos( $html_botanical_rel, 'Sour Diesel' ), "Botanical (Zero-Leak): Sour Diesel NOT rendered" );

// Direct URL to Strain Exhibit
$_GET = array( 'view' => 'botanical', 'strain' => 'blue-dream' );
$html_strain_rel_bd = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_strain_rel_bd, 'Botanical Exhibit In Preparation' ), "Botanical Direct URL: Returns honest Botanical Exhibit In Preparation notice" );
assert_lounge( false === strpos( $html_strain_rel_bd, 'Blueberry &times; Haze' ), "Botanical Direct URL (Zero-Leak): Strain lineage NOT rendered" );
assert_lounge( false === strpos( $html_strain_rel_bd, 'sweet berry aromatics' ), "Botanical Direct URL (Zero-Leak): Strain notes NOT rendered" );

// -------------------------------------------------------------
// SECTION 6: SCREEN 05 - MEMBER BENEFITS MATRIX (COMMERCIAL INTEGRITY)
// -------------------------------------------------------------
echo "\n--- 6. SCREEN 05: MEMBER BENEFITS MATRIX (COMMERCIAL INTEGRITY) ---\n";

$_GET = array( 'view' => 'benefits' );
$html_benefits = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_benefits, 'Lounge Membership Benefits' ), "Benefits: Displays title" );
assert_lounge( false !== strpos( $html_benefits, 'Lounge Pass' ) && false !== strpos( $html_benefits, 'Free' ), "Benefits: Displays Lounge Pass Free ($0)" );
assert_lounge( false !== strpos( $html_benefits, 'Lounge Member' ) && false !== strpos( $html_benefits, '$9.99' ), "Benefits: Displays Member $9.99/mo" );
assert_lounge( false !== strpos( $html_benefits, 'Lounge Elite' ) && false !== strpos( $html_benefits, '$24.99' ), "Benefits: Displays Elite $24.99/mo" );
assert_lounge( false !== strpos( $html_benefits, '10% eligible store discount' ), "Benefits: Details 10% discount for Member" );
assert_lounge( false !== strpos( $html_benefits, '25% eligible store discount' ), "Benefits: Details 25% discount for Elite" );
assert_lounge( false !== strpos( $html_benefits, 'Discount Exclusions' ), "Benefits: Renders approved discount exclusions notice" );

// -------------------------------------------------------------
// SECTION 7: SCREEN 06 - WHAT'S NEW (RELEASE MODE EMPTY STATE)
// -------------------------------------------------------------
echo "\n--- 7. SCREEN 06: WHAT'S NEW (RELEASE MODE EMPTY STATE) ---\n";

$_GET = array( 'view' => 'whats-new' );
$html_whats_new_rel = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_whats_new_rel, 'What&#8217;s New in The Lounge' ), "What's New: Displays title" );
assert_lounge( false !== strpos( $html_whats_new_rel, 'No Current Announcements' ), "What's New (Release): Displays useful empty state heading" );
assert_lounge( false !== strpos( $html_whats_new_rel, 'Official announcements and curriculum release logs will be posted here' ), "What's New (Release): Displays helpful empty state description" );
assert_lounge( false !== strpos( $html_whats_new_rel, 'Return to Lounge Home' ), "What's New (Release): Displays return to Home button" );
assert_lounge( false !== strpos( $html_whats_new_rel, 'View Member Benefits' ), "What's New (Release): Displays View Member Benefits button" );

// Zero-leak: Unapproved announcements must NOT be present
assert_lounge( false === strpos( $html_whats_new_rel, 'Botanical Discovery Volume I Founding Cultivar Preview' ), "What's New (Zero-Leak): Unapproved cultivar preview announcement NOT rendered" );
assert_lounge( false === strpos( $html_whats_new_rel, 'Three-Tier Commercial Synchronization Established' ), "What's New (Zero-Leak): Unapproved sync announcement NOT rendered" );

// -------------------------------------------------------------
// SECTION 8: SCREEN 07 - ACCOUNT RETURN HUB
// -------------------------------------------------------------
echo "\n--- 8. SCREEN 07: ACCOUNT RETURN HUB ---\n";

$_GET = array( 'view' => 'account' );
$html_account = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_account, 'Account &amp; Subscriptions Return' ), "Account: Displays title" );
assert_lounge( false !== strpos( $html_account, 'https://cccultivate.com/my-account/' ), "Account: Links to /my-account/" );
assert_lounge( false !== strpos( $html_account, 'https://cccultivate.com/my-account/subscriptions/' ), "Account: Links to /my-account/subscriptions/" );
assert_lounge( false !== strpos( $html_account, 'Return to Lounge Home' ), "Account: Contains return to Lounge Home button" );

// -------------------------------------------------------------
// SECTION 9: NAVIGATION & SECURITY
// -------------------------------------------------------------
echo "\n--- 9. NAVIGATION & SECURITY ---\n";

// Navigation bar present on all views
assert_lounge( false !== strpos( $html_account, 'wnb-desktop-nav' ), "Header nav links present" );
assert_lounge( false !== strpos( $html_account, 'wnb-mobile-bottom-bar' ), "Mobile bottom priority nav present" );

// Input sanitization check: XSS attack in query parameters
$_GET = array(
    'view' => 'explore',
    'category' => '<script>alert("xss")</script>'
);
$html_sanitized = CCC\WNB\Lounge_UI::render();
assert_lounge( false === strpos( $html_sanitized, '<script>alert("xss")</script>' ), "Input sanitization: Script tags safely neutralized" );

// =============================================================
// PART B: DEVELOPMENT FIXTURE MODE & TIER PROTECTION
// =============================================================
echo "\n=======================================================\n";
echo "PART B: DEVELOPMENT FIXTURE MODE & TIER PROTECTION\n";
echo "=======================================================\n\n";

CCC\WNB\Lounge_UI::set_fixture_mode( true );
assert_lounge( true === CCC\WNB\Lounge_UI::is_fixture_mode_enabled(), "Dev Fixture Mode: is_fixture_mode_enabled() is true" );
assert_lounge( count( CCC\WNB\Lounge_UI::get_content_items() ) === 7, "Dev Fixture Mode: 7 content fixtures available" );
assert_lounge( count( CCC\WNB\Lounge_UI::get_botanical_strains() ) === 4, "Dev Fixture Mode: 4 botanical strain fixtures available" );
assert_lounge( count( CCC\WNB\Lounge_UI::get_whats_new_items() ) === 3, "Dev Fixture Mode: 3 What's New fixtures available" );

// Explore Directory in Fixture Mode
$_GET = array( 'view' => 'explore' );
$html_explore_fix = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_explore_fix, 'Anatomy of a Cannabis Flower' ), "Explore (Fixture Mode): Pass lesson rendered" );
assert_lounge( false !== strpos( $html_explore_fix, 'Advanced Extraction' ), "Explore (Fixture Mode): Member lesson rendered" );
assert_lounge( false !== strpos( $html_explore_fix, 'Masterclass: Terpene Preservation' ), "Explore (Fixture Mode): Elite lesson rendered" );

// Tier Protection Verification:
// Case A: Pass user views Pass item -> UNLOCKED
$current_user_id = 9;
$orders[0]->status = 'cancelled';
$orders[1]->status = 'cancelled';
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-EDU-01' );
$html_detail_unlocked = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_detail_unlocked, 'Anatomy of a Cannabis Flower' ), "Tier Protection: Pass user on Pass item -> Unlocked title" );
assert_lounge( false !== strpos( $html_detail_unlocked, 'Glandular Trichomes' ), "Tier Protection: Pass user on Pass item -> Unlocked body" );
assert_lounge( false === strpos( $html_detail_unlocked, 'Exclusive Member Resource' ), "Tier Protection: Pass user on Pass item -> No gate" );

// Case B: Pass user views Member item -> RESTRICTED (Zero-Leak)
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-MBR-01' );
$html_detail_restricted = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_detail_restricted, 'Exclusive Member Resource' ), "Tier Protection: Pass user on Member item -> Restricted banner" );
assert_lounge( false !== strpos( $html_detail_restricted, 'Upgrade to Lounge Member' ), "Tier Protection: Pass user on Member item -> Upgrade CTA" );
assert_lounge( false === strpos( $html_detail_restricted, 'Full-Spectrum vs. Distillate' ), "Tier Protection (Zero-Leak): Member body NOT rendered to Pass user" );

// Case C: Member user views Member item -> UNLOCKED
$current_user_id = 7;
$orders[0]->status = 'active';
$orders[1]->status = 'cancelled';
$html_member_unlocked = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_member_unlocked, 'Advanced Extraction' ), "Tier Protection: Member user on Member item -> Unlocked title" );
assert_lounge( false !== strpos( $html_member_unlocked, 'Full-Spectrum vs. Distillate' ), "Tier Protection: Member user on Member item -> Unlocked body" );

// Case D: Member user views Elite item -> RESTRICTED (Zero-Leak)
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-ELT-01' );
$html_member_elite_restricted = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_member_elite_restricted, 'Exclusive Member Resource' ), "Tier Protection: Member user on Elite item -> Restricted banner" );
assert_lounge( false !== strpos( $html_member_elite_restricted, 'Upgrade to Lounge Elite VIP' ), "Tier Protection: Member user on Elite item -> Upgrade CTA" );
assert_lounge( false === strpos( $html_member_elite_restricted, 'Cold Curing Kinetics' ), "Tier Protection (Zero-Leak): Elite body NOT rendered to Member user" );

// Case E: Elite user views Elite item -> UNLOCKED
$orders[1]->status = 'active';
$html_elite_unlocked = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_elite_unlocked, 'Masterclass: Terpene Preservation' ), "Tier Protection: Elite user on Elite item -> Unlocked title" );
assert_lounge( false !== strpos( $html_elite_unlocked, 'Cold Curing Kinetics' ), "Tier Protection: Elite user on Elite item -> Unlocked body" );

// Case F: Non-existent item in fixture mode -> Not Found
$_GET = array( 'view' => 'detail', 'item' => 'NON-EXISTENT-XYZ' );
$html_not_found = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_not_found, 'Resource Not Found' ), "Tier Protection: Non-existent item -> Resource Not Found" );

// Botanical gallery in fixture mode
$_GET = array( 'view' => 'botanical' );
$html_bot_fix = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_bot_fix, 'Blue Dream' ), "Botanical (Fixture Mode): Renders Blue Dream" );

// Botanical exhibit detail in fixture mode
$_GET = array( 'view' => 'botanical', 'strain' => 'blue-dream' );
$html_bd_fix = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_bd_fix, 'Blueberry' ), "Botanical Exhibit (Fixture Mode): Renders Blue Dream lineage" );

// Reset Fixture Mode to default release mode
CCC\WNB\Lounge_UI::set_fixture_mode( false );
assert_lounge( false === CCC\WNB\Lounge_UI::is_fixture_mode_enabled(), "Teardown: Fixture mode safely reset to disabled" );

echo "\n=======================================================\n";
echo "MX-4B LOUNGE UI VERIFICATION COMPLETE: ALL {$pass_count} CHECKS PASSED\n";
echo "=======================================================\n\n";
