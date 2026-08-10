<?php
declare(strict_types=1);

define('ABSPATH', __DIR__ . '/');
$plugin = dirname(__DIR__, 2) . '/deploy/wordpress/budly-sales-agent/';
require_once $plugin . 'includes/SecureMemory/Bootstrap.php';
\Budly\SecureMemory\Bootstrap::load();

if (!class_exists('Budly\\Conversation\\ConversationManager', false)) {
    throw new RuntimeException('ConversationManager was not loaded by Bootstrap.');
}
if (!class_exists('Budly\\Lifecycle\\LifecycleEngine', false)) {
    throw new RuntimeException('LifecycleEngine was not loaded by Bootstrap.');
}

echo "v1.7.1 Bootstrap executable load: PASS\n";
