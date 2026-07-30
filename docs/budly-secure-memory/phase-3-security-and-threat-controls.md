# Phase 3 security controls and residual risks

Implemented controls include hashed one-time codes, transactional one-use consumption, rate and attempt limits, enumeration-neutral responses, HMAC-only session-token persistence, Secure/HttpOnly/SameSite cookies, idle/absolute expiry, session and administrator revocation, session-derived ownership, CSRF protection, agent scope/namespace authorization, independent fail-closed consent, customer-visible allowlists, structured memory validation, sensitive-data rejection, idempotency, bounded payloads, recursive audit scrubbing, HTTPS/same-origin enforcement, non-cacheable responses, and deidentified/throttled analytics.

The high-severity client-forged consent/customer-memory poisoning path is contained in source. Public analytics cannot write identity, consent, or memory. Legacy AJAX recall actions are not registered. Production remains at risk until the new release is validated and deployed.

Residual or externally controlled risks:

- Email eligibility may retain a measurable timing difference because WordPress mail delivery is synchronous for eligible addresses. Public copy remains neutral and rate limited; runtime timing measurement is required.
- SMTP delivery, DNS reputation, hosting logs, TLS termination, database least-privilege, backups, encryption at rest, key custody, WAF/proxy rules, and infrastructure monitoring are hosting responsibilities requiring operational validation.
- A restrictive site-wide Content Security Policy was not injected because compatibility with Wix/WordPress/WooCommerce assets must be tested first. Stored memory is rendered with text nodes and REST responses receive defensive headers.
- Legacy recall function bodies remain as unreachable compatibility code in `tracking.php`; their WordPress actions are deliberately absent. Removal after data-migration review is recommended to prevent accidental re-registration.
- Source-contract tests execute locally, but PHP/WordPress/MySQL integration, concurrent database behavior, accessibility tools, browsers, and real email delivery are not available in this workspace.
- Backup confidentiality cannot be declared without inspecting the actual hosting backup and key-management configuration.

No critical or high-severity issue is accepted as production-ready. Any failed cross-customer, consent-bypass, replay, CSRF, deletion, or administrator test blocks Gate F.

## Runtime security disposition: 2026-07-28

Gates C-E adversarial tests passed in LocalWP/MySQL with two isolated customers and multiple WordPress authorization states. Session-derived ownership, CSRF/origin enforcement, namespace/scope authorization, consent-aware writes/retrieval, transactional deletion, session revocation, administrator capability/nonces, audit scrubbing, and SMTP/cleanup controls behaved as specified.

Four medium defects were corrected and retested: duplicate-insert race response handling, dotted audit event taxonomy, missing input accessible names, and mobile composer stretching. No unresolved critical or high-severity source vulnerability was found.

Remaining Gate F risks are externally controlled or require independent evidence: production version/plugin/theme parity; screen-reader and peer security review; production-wide CSP compatibility; hosting database-outage recovery, alerting, logging, least privilege, backup confidentiality, and monitoring. Production deployment remains prohibited.
