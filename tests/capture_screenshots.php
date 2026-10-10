<?php
/**
 * Captures desktop (1440px) and mobile (390px) screenshots for all rendered Lounge UI fixtures
 * using headless Chrome.
 */

$chrome_path = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
$fixtures_dir = __DIR__ . '/html_fixtures';
$output_dir = dirname( __DIR__ ) . '/evidence/screenshots';

if ( ! is_dir( $output_dir ) ) {
    mkdir( $output_dir, 0777, true );
}

$files = glob( $fixtures_dir . '/*.html' );
sort( $files );

echo "Found " . count( $files ) . " fixtures to screenshot.\n";

foreach ( $files as $file ) {
    $base = basename( $file, '.html' );
    $file_url = 'file:///' . str_replace( '\\', '/', realpath( $file ) );

    // 1. Desktop: 1440 x 1080
    $out_desktop = $output_dir . '/' . $base . '_desktop_1440.png';
    $cmd_desktop = sprintf(
        '"%s" --headless --disable-gpu --hide-scrollbars --window-size=1440,1080 --screenshot="%s" "%s" 2>&1',
        $chrome_path,
        $out_desktop,
        $file_url
    );
    exec( $cmd_desktop, $out1, $ret1 );
    echo "  [DESKTOP 1440px] {$base} -> " . ( file_exists( $out_desktop ) ? "OK (" . filesize( $out_desktop ) . " bytes)" : "FAILED" ) . "\n";

    // 2. Mobile: 390 x 844
    $out_mobile = $output_dir . '/' . $base . '_mobile_390.png';
    $cmd_mobile = sprintf(
        '"%s" --headless --disable-gpu --hide-scrollbars --window-size=390,844 --screenshot="%s" "%s" 2>&1',
        $chrome_path,
        $out_mobile,
        $file_url
    );
    exec( $cmd_mobile, $out2, $ret2 );
    echo "  [MOBILE  390px] {$base} -> " . ( file_exists( $out_mobile ) ? "OK (" . filesize( $out_mobile ) . " bytes)" : "FAILED" ) . "\n";
}

echo "\nScreenshot capture complete. Files written to evidence/screenshots/\n";
