<?php
/**
 * Phase MX-4B: Lounge UI & Navigation Test Suite
 *
 * Verifies the ratified MX-1 through MX-4A Lounge UI presentation:
 * - 7 ratified screens (Home, Explore, Detail, Botanical, Benefits, What's New, Account)
 * - Strict server-side content access control & zero-leak isolation
 * - Guest, Pass, Member, and Elite tier state rendering
 * - Responsive navigation and mobile bar components
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
// SECTION 1: REGISTRATION & SHORTCODES
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

// -------------------------------------------------------------
// SECTION 2: SCREEN 01 - LOUNGE HOME
// -------------------------------------------------------------
echo "\n--- 2. SCREEN 01: LOUNGE HOME ---\n";

// Guest (User 10)
$current_user_id = 10;
$_GET = array();
$html_guest_home = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_guest_home, 'Public Orientation' ) || false !== strpos( $html_guest_home, 'data-user-tier="none"' ), "Home (Guest): Displays Public/Guest orientation status" );
assert_lounge( false !== strpos( $html_guest_home, 'Claim Free Lounge Pass' ), "Home (Guest): Displays Claim Free Lounge Pass CTA" );
assert_lounge( false !== strpos( $html_guest_home, 'https://cccultivate.com/product/lounge-pass/' ), "Home (Guest): Links to product/lounge-pass/" );
assert_lounge( false !== strpos( $html_guest_home, 'Ask Budly' ), "Home (Guest): Displays Ask Budly entry" );
assert_lounge( false !== strpos( $html_guest_home, 'Botanical Discovery' ), "Home (Guest): Displays Botanical Discovery entry" );

// Pass Member (User 9)
$current_user_id = 9;
$orders[1]->status = 'cancelled';
$orders[0]->status = 'cancelled';
$html_pass_home = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_pass_home, 'Lounge Pass' ), "Home (Pass): Displays Lounge Pass tier pill" );
assert_lounge( false !== strpos( $html_pass_home, 'Read Lesson' ), "Home (Pass): Displays Read Lesson CTA" );
assert_lounge( false !== strpos( $html_pass_home, 'Botanical Discovery' ), "Home (Pass): Displays Botanical Discovery entry" );

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
// SECTION 3: SCREEN 02 - EXPLORE DIRECTORY
// -------------------------------------------------------------
echo "\n--- 3. SCREEN 02: EXPLORE DIRECTORY ---\n";

$_GET = array( 'view' => 'explore' );
$html_explore = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_explore, 'Explore Educational Resources' ), "Explore: Renders library heading" );
assert_lounge( false !== strpos( $html_explore, 'All Content' ) && false !== strpos( $html_explore, 'Culinary' ), "Explore: Renders category filter pills" );
assert_lounge( false !== strpos( $html_explore, 'Anatomy of a Cannabis Flower' ), "Explore: Contains Pass lesson 'Anatomy of a Cannabis Flower'" );
assert_lounge( false !== strpos( $html_explore, 'Advanced Extraction' ), "Explore: Contains Member lesson 'Advanced Extraction'" );
assert_lounge( false !== strpos( $html_explore, 'Masterclass: Terpene Preservation' ), "Explore: Contains Elite lesson 'Masterclass'" );
assert_lounge( false !== strpos( $html_explore, 'Precision Decarboxylation Guide' ), "Explore: Contains culinary lesson" );

// -------------------------------------------------------------
// SECTION 4: SCREEN 03 - CONTENT DETAIL & ACCESS GATE
// -------------------------------------------------------------
echo "\n--- 4. SCREEN 03: CONTENT DETAIL & ACCESS GATE ---\n";

// Case A: Pass user views Pass item -> UNLOCKED
$current_user_id = 9;
$orders[0]->status = 'cancelled';
$orders[1]->status = 'cancelled';
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-EDU-01' );
$html_detail_unlocked = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_detail_unlocked, 'Anatomy of a Cannabis Flower' ), "Detail (Unlocked): Displays title" );
assert_lounge( false !== strpos( $html_detail_unlocked, 'Glandular Trichomes' ), "Detail (Unlocked): Displays full lesson body" );
assert_lounge( false !== strpos( $html_detail_unlocked, 'Key Takeaways' ), "Detail (Unlocked): Displays Key Takeaways section" );
assert_lounge( false !== strpos( $html_detail_unlocked, 'Discuss with Budly' ), "Detail (Unlocked): Displays Discuss with Budly CTA" );
assert_lounge( false === strpos( $html_detail_unlocked, 'Exclusive Member Resource' ), "Detail (Unlocked): Does NOT display locked gate" );

// Case B: Pass user views Member item -> RESTRICTED (Zero-leak verification)
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-MBR-01' );
$html_detail_restricted = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_detail_restricted, 'Exclusive Member Resource' ), "Detail (Restricted): Displays Exclusive Member Resource banner" );
assert_lounge( false !== strpos( $html_detail_restricted, 'Lounge Member' ), "Detail (Restricted): Explains required tier" );
assert_lounge( false !== strpos( $html_detail_restricted, 'Upgrade to Lounge Member' ), "Detail (Restricted): Displays upgrade CTA" );
// ZERO-LEAK VERIFICATION
assert_lounge( false === strpos( $html_detail_restricted, 'Full-Spectrum vs. Distillate' ), "Detail (Restricted): ZERO-LEAK: Protected body text is NOT rendered" );
assert_lounge( false === strpos( $html_detail_restricted, 'Key Takeaways' ), "Detail (Restricted): ZERO-LEAK: Key takeaways NOT rendered" );

// Case C: Member user views Member item -> UNLOCKED
$current_user_id = 7;
$orders[0]->status = 'active';
$orders[1]->status = 'cancelled';
$html_member_unlocked = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_member_unlocked, 'Advanced Extraction' ), "Detail (Member): Displays title" );
assert_lounge( false !== strpos( $html_member_unlocked, 'Full-Spectrum vs. Distillate' ), "Detail (Member): Displays protected body text" );
assert_lounge( false !== strpos( $html_member_unlocked, 'Key Takeaways' ), "Detail (Member): Displays Key Takeaways" );

// Case D: Member user views Elite item -> RESTRICTED
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-ELT-01' );
$html_member_elite_restricted = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_member_elite_restricted, 'Exclusive Member Resource' ), "Detail (Member on Elite): Displays Exclusive banner" );
assert_lounge( false !== strpos( $html_member_elite_restricted, 'Upgrade to Lounge Elite VIP' ), "Detail (Member on Elite): Displays Upgrade to Elite CTA" );
assert_lounge( false === strpos( $html_member_elite_restricted, 'Cold Curing Kinetics' ), "Detail (Member on Elite): ZERO-LEAK: Elite content NOT rendered" );

// Case E: Elite user views Elite item -> UNLOCKED
$orders[1]->status = 'active';
$html_elite_unlocked = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_elite_unlocked, 'Masterclass: Terpene Preservation' ), "Detail (Elite): Displays title" );
assert_lounge( false !== strpos( $html_elite_unlocked, 'Cold Curing Kinetics' ), "Detail (Elite): Displays elite body text" );

// Case F: Non-existent item slug -> ERROR/EMPTY STATE
$_GET = array( 'view' => 'detail', 'item' => 'NON-EXISTENT-XYZ' );
$html_detail_error = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_detail_error, 'Resource Not Found' ), "Detail (Error): Displays not found notice" );
assert_lounge( false !== strpos( $html_detail_error, 'Return to Lounge Home' ), "Detail (Error): Displays return link" );

// -------------------------------------------------------------
// SECTION 5: SCREEN 04 - BOTANICAL DISCOVERY
// -------------------------------------------------------------
echo "\n--- 5. SCREEN 04: BOTANICAL DISCOVERY ---\n";

// Volume I Gallery View
$_GET = array( 'view' => 'botanical' );
$html_botanical_gallery = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_botanical_gallery, 'Botanical Discovery Gallery' ), "Botanical: Displays Volume I title" );
assert_lounge( false !== strpos( $html_botanical_gallery, 'Blue Dream' ), "Botanical: Displays Blue Dream" );
assert_lounge( false !== strpos( $html_botanical_gallery, 'Granddaddy Purple' ), "Botanical: Displays Granddaddy Purple" );
assert_lounge( false !== strpos( $html_botanical_gallery, 'Jack Herer' ), "Botanical: Displays Jack Herer" );
assert_lounge( false !== strpos( $html_botanical_gallery, 'Sour Diesel' ), "Botanical: Displays Sour Diesel" );
assert_lounge( false !== strpos( $html_botanical_gallery, 'Berry' ), "Botanical: Displays aroma chip" );

// Single Strain Exhibit View: Blue Dream
$_GET = array( 'view' => 'botanical', 'strain' => 'blue-dream' );
$html_strain_blue_dream = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_strain_blue_dream, 'Blue Dream' ), "Strain Exhibit: Displays Blue Dream header" );
assert_lounge( false !== strpos( $html_strain_blue_dream, 'Blueberry' ), "Strain Exhibit: Displays Lineage" );
assert_lounge( false !== strpos( $html_strain_blue_dream, 'Genetic Lineage' ), "Strain Exhibit: Displays Genetic Lineage section" );
assert_lounge( false !== strpos( $html_strain_blue_dream, 'Chemistry &amp; Laboratory Lens' ), "Strain Exhibit: Displays Chemistry section" );
assert_lounge( false !== strpos( $html_strain_blue_dream, 'Ask Budly About This Strain' ), "Strain Exhibit: Displays Ask Budly CTA" );

// Single Strain Exhibit View: Granddaddy Purple
$_GET = array( 'view' => 'botanical', 'strain' => 'granddaddy-purple' );
$html_strain_gdp = CCC\WNB\Lounge_UI::render();
assert_lounge( false !== strpos( $html_strain_gdp, 'Purple Urkle' ), "Strain Exhibit (GDP): Displays correct lineage" );

// -------------------------------------------------------------
// SECTION 6: SCREEN 05 - MEMBER BENEFITS MATRIX
// -------------------------------------------------------------
echo "\n--- 6. SCREEN 05: MEMBER BENEFITS MATRIX ---\n";

$_GET = array( 'view' => 'benefits' );
$html_benefits = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_benefits, 'Lounge Membership Benefits' ), "Benefits: Displays title" );
assert_lounge( false !== strpos( $html_benefits, 'Lounge Pass' ) && false !== strpos( $html_benefits, 'Free' ), "Benefits: Displays Lounge Pass Free" );
assert_lounge( false !== strpos( $html_benefits, 'Lounge Member' ) && false !== strpos( $html_benefits, '$9.99' ), "Benefits: Displays Member $9.99/mo" );
assert_lounge( false !== strpos( $html_benefits, 'Lounge Elite' ) && false !== strpos( $html_benefits, '$24.99' ), "Benefits: Displays Elite $24.99/mo" );
assert_lounge( false !== strpos( $html_benefits, '10% eligible store discount' ), "Benefits: Details 10% discount for Member" );
assert_lounge( false !== strpos( $html_benefits, '25% eligible store discount' ), "Benefits: Details 25% discount for Elite" );

// -------------------------------------------------------------
// SECTION 7: SCREEN 06 - WHAT'S NEW LOG
// -------------------------------------------------------------
echo "\n--- 7. SCREEN 06: WHAT'S NEW LOG ---\n";

$_GET = array( 'view' => 'whats-new' );
$html_whats_new = CCC\WNB\Lounge_UI::render();

assert_lounge( false !== strpos( $html_whats_new, 'What&#8217;s New in The Lounge' ), "What's New: Displays title" );
assert_lounge( false !== strpos( $html_whats_new, 'Lounge Entitlements v0.4.0 &amp; Unified Member UX Released' ), "What's New: Displays v0.4.0 entry" );
assert_lounge( false !== strpos( $html_whats_new, 'October 10, 2026' ), "What's New: Displays October 10, 2026 date" );
assert_lounge( false !== strpos( $html_whats_new, 'Botanical Discovery Collection Volume I Curriculum Integrated' ), "What's New: Displays Volume I entry" );

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
// SECTION 9: RESPONSIVE NAV & SECURITY
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

echo "\n=======================================================\n";
echo "MX-4B LOUNGE UI VERIFICATION COMPLETE: ALL {$pass_count} CHECKS PASSED\n";
echo "=======================================================\n\n";
