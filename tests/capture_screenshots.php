<?php
/**
 * Captures desktop (1440px) and full-page mobile (390px) screenshots for all rendered Lounge UI fixtures
 * using Playwright (Chromium/Chrome channel).
 */

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
    $url = 'http://127.0.0.1:8888/html_fixtures/' . basename( $file );

    // 1. Desktop: 1440 x 1080
    $out_desktop = $output_dir . '/' . $base . '_desktop_1440.png';
    $cmd_desktop = sprintf(
        'playwright screenshot --viewport-size="1440,1080" --channel="chrome" "%s" "%s" 2>&1',
        $url,
        $out_desktop
    );
    exec( $cmd_desktop, $out1, $ret1 );
    $d_ok = file_exists( $out_desktop );
    $d_sz = $d_ok ? filesize( $out_desktop ) : 0;
    $d_dims = $d_ok ? getimagesize( $out_desktop ) : [ 0, 0 ];
    echo "  [DESKTOP 1440px] {$base} -> " . ( $d_ok ? "OK ({$d_dims[0]}x{$d_dims[1]}, {$d_sz} bytes)" : "FAILED" ) . "\n";

    // 2. Mobile: 390 x 844 (Full-Page capture)
    $out_mobile = $output_dir . '/' . $base . '_mobile_390.png';
    $cmd_mobile = sprintf(
        'playwright screenshot --full-page --viewport-size="390,844" --channel="chrome" "%s" "%s" 2>&1',
        $url,
        $out_mobile
    );
    exec( $cmd_mobile, $out2, $ret2 );
    $m_ok = file_exists( $out_mobile );
    $m_sz = $m_ok ? filesize( $out_mobile ) : 0;
    $m_dims = $m_ok ? getimagesize( $out_mobile ) : [ 0, 0 ];
    echo "  [MOBILE  390px] {$base} -> " . ( $m_ok ? "OK ({$m_dims[0]}x{$m_dims[1]}, {$m_sz} bytes)" : "FAILED" ) . "\n";
}

echo "\nScreenshot capture complete. All files written to evidence/screenshots/\n";
