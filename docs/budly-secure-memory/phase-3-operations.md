# Phase 3 installation, configuration, administration, and operations

## Installation and configuration

Install version 1.3.0 only in staging first. WordPress must serve HTTPS. Confirm outbound `wp_mail`, database backups, cron, and a consenting test mailbox. Operational defaults are: 10-minute verification expiry, five attempts, 3 requests/email/hour, 10 requests/IP/hour, 30-minute session idle expiry, two-hour absolute expiry, 7-day verification-artifact retention, 30-day expired/revoked session retention, 365-day memory metadata expiry, 500-row cleanup batches, and 32 KiB JSON requests. Supported values can be changed through the documented `budly_memory_*` options; changes require security review.

## Administration

WordPress Tools → Budly Secure Memory provides health, aggregate metrics, recent audit events, session revocation, revoke-all, transactional email testing, and bounded cleanup. Access requires `manage_options`; mutations require a REST nonce and are audited. Never share screenshots containing customer/session identifiers casually.

## Routine operations

- Review degraded health, delivery failures, rate-limit events, locked verification requests, administrator actions, cleanup failures, and unusual revocation volume.
- Confirm scheduled cleanup runs daily and that `last_cleanup` advances.
- Test transactional email after SMTP/hosting changes.
- Restore-test database backups periodically; security records and memory require the same protection as production data.
- Rotate WordPress salts only under a planned sign-out event because existing session/code hashes will become invalid.
- Never connect Google Sheets analytics to secure-memory tables or payloads.

## Incident response

For suspected session or memory exposure: disable the plugin/customer entry if necessary, revoke affected/all sessions, preserve audit and hosting logs, stop exports, assess backup/log exposure, correct the control, rerun security acceptance, and notify affected parties according to applicable policy and counsel. Do not delete audit evidence as ordinary memory cleanup.
