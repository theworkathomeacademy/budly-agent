<?php
/**
 * Generates standalone HTML mockup files for Lounge UI visual review and screenshot capture.
 */

define( 'ABSPATH', __DIR__ );
require_once __DIR__ . '/php/wnb_membership_integration.php';

$output_dir = __DIR__ . '/html_fixtures';
if ( ! is_dir( $output_dir ) ) {
    mkdir( $output_dir, 0777, true );
}

function build_page( string $title, string $inner_html, string $css ): string {
    return '<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>' . htmlspecialchars( $title ) . ' - Wake\'n\'Bake Lounge</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: #090e0b;
            color: #f5f0df;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            -webkit-font-smoothing: antialiased;
        }
        .container {
            max-width: 1440px;
            width: 100%;
            box-sizing: border-box;
            margin: 0 auto;
            padding: 20px;
        }
        @media (max-width: 600px) {
            .container { padding: 4px; }
            .wnb-fullpage-preview .wnb-mobile-bottom-bar {
                position: static !important;
                margin-top: 24px;
            }
        }
    ' . $css . '
    </style>
</head>
<body class="wnb-fullpage-preview">
    <div class="container">
        ' . $inner_html . '
    </div>
</body>
</html>';
}

$css = CCC\WNB\Lounge_UI::get_css();

// 1. Screen 01: Lounge Home - Guest
$current_user_id = 10;
$_GET = array( 'view' => 'home' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/01_home_guest.html', build_page( 'Lounge Home (Guest)', $html, $css ) );

// 2. Screen 01: Lounge Home - Pass Member
$current_user_id = 9;
$orders[0]->status = 'cancelled';
$orders[1]->status = 'cancelled';
$_GET = array( 'view' => 'home' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/01_home_pass.html', build_page( 'Lounge Home (Pass)', $html, $css ) );

// 3. Screen 01: Lounge Home - Member
$current_user_id = 7;
$orders[0]->status = 'active';
$orders[1]->status = 'cancelled';
$_GET = array( 'view' => 'home' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/01_home_member.html', build_page( 'Lounge Home (Member)', $html, $css ) );

// 4. Screen 01: Lounge Home - Elite
$orders[1]->status = 'active';
$_GET = array( 'view' => 'home' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/01_home_elite.html', build_page( 'Lounge Home (Elite)', $html, $css ) );

// 5. Screen 02: Explore Directory
$_GET = array( 'view' => 'explore' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/02_explore_directory.html', build_page( 'Explore Directory', $html, $css ) );

// 6. Screen 03: Content Detail - Unlocked (Pass on Pass lesson)
$current_user_id = 9;
$orders[0]->status = 'cancelled';
$orders[1]->status = 'cancelled';
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-EDU-01' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/03_content_detail_unlocked.html', build_page( 'Content Detail (Unlocked)', $html, $css ) );

// 7. Screen 03: Content Detail - Restricted Gate (Pass on Member lesson)
$_GET = array( 'view' => 'detail', 'item' => 'VOL1-MBR-01' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/03_content_detail_restricted.html', build_page( 'Content Detail (Restricted)', $html, $css ) );

// 8. Screen 04: Botanical Discovery Gallery (Volume I)
$_GET = array( 'view' => 'botanical' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/04_botanical_gallery.html', build_page( 'Botanical Discovery Gallery', $html, $css ) );

// 9. Screen 04: Botanical Single Exhibit - Blue Dream
$_GET = array( 'view' => 'botanical', 'strain' => 'blue-dream' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/04_botanical_exhibit_blue_dream.html', build_page( 'Botanical Exhibit: Blue Dream', $html, $css ) );

// 10. Screen 05: Member Benefits Matrix
$_GET = array( 'view' => 'benefits' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/05_member_benefits.html', build_page( 'Member Benefits Matrix', $html, $css ) );

// 11. Screen 06: What\'s New
$_GET = array( 'view' => 'whats-new' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/06_whats_new.html', build_page( 'What\'s New', $html, $css ) );

// 12. Screen 07: Account Return Hub
$_GET = array( 'view' => 'account' );
$html = CCC\WNB\Lounge_UI::render();
file_put_contents( $output_dir . '/07_account_return.html', build_page( 'Account Return Hub', $html, $css ) );

echo "Generated 12 HTML fixtures in tests/html_fixtures/\n";
