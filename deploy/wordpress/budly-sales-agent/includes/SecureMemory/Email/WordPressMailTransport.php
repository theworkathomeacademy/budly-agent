<?php
namespace Budly\SecureMemory\Email;

if (!defined('ABSPATH')) { exit; }

final class WordPressMailTransport implements EmailTransport {
    public function send_verification_code($email, $code, $expires_minutes) {
        $subject = 'Your Budly verification code';
        $body = "Your Budly verification code is {$code}.\n\nIt expires in {$expires_minutes} minutes and can be used once.\n\nIf you did not request this code, you can ignore this email.";
        return (bool) wp_mail($email, $subject, $body, array('Reply-To: Budly Support <budlysupport@gmail.com>'));
    }

    public function send_test($email) {
        return (bool) wp_mail($email, 'Budly secure-memory email test', 'This is a transactional email-delivery test. No customer memory is included.');
    }
}
