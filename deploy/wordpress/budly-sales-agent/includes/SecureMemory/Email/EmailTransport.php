<?php
namespace Budly\SecureMemory\Email;

if (!defined('ABSPATH')) { exit; }

interface EmailTransport {
    public function send_verification_code($email, $code, $expires_minutes);
    public function send_test($email);
}
