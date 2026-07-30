# Phase 3 WordPress/MySQL runtime acceptance plan

Gate F remains failed until this plan is executed in a disposable staging environment representative of production.

## Required environment

- Supported WordPress/PHP/MySQL versions, HTTPS, WP-Cron, SMTP/test mailbox, administrator and nonadministrator users, two independent test customers, browser developer tools, backup/restore access, and accessibility tooling.

## Required execution

1. Activate from a copy of the current production schema; verify migration 1.1.0, indexes, agent seed, repeatability, and rollback recovery.
2. Exercise every API endpoint for success, invalid JSON/content type, oversized input, anonymous access, expired/revoked session, wrong capability, missing/bad CSRF/nonce, stable envelope/status, SQL/XSS payloads, and safe logs.
3. Prove code expiry, five-attempt lock, replay rejection, per-email/IP throttling, neutral copy and measured eligible/ineligible timing.
4. Prove session cookie flags, token hashing, fixation resistance, idle and absolute expiry, logout, administrator revoke, and inability to regain validity.
5. Run cross-customer isolation attacks with customers A and B against every profile/memory/export/correction/deletion identifier. No A operation may read or alter B.
6. Withdraw storage/use consent during active work and prove immediate write/read denial. Prove marketing remains independent.
7. Prove preview allowlisting, context approval, Start Fresh, agent namespace isolation, sensitive-content rejection, summary limits, concurrent idempotency and duplicate handling.
8. Prove selective deletion and delete-all success, rollback on injected component failure, audit event, and all-session revocation.
9. Run scheduled/manual cleanup on eligible/ineligible fixtures; prove preservation of consent, history, audit and unexpired customer memory.
10. Complete customer E2E on desktop/mobile: verify, resend/errors, preview, use, Start Fresh, privacy, correction, export, deletion, session expiry and recovery.
11. Run automated accessibility scan plus manual keyboard, screen-reader, focus-order, live-region, contrast, touch-target and reduced-motion review.
12. Test SMTP failure/recovery, cron failure, database outage graceful denial, backup confidentiality, restore, monitoring/alerts and rollback.

Record environment versions, timestamps, tester, evidence links, actual results, defects and retests. Gates A–E may change from Partial to Pass only with this evidence. Gate F requires all critical/high tests, E2E, accessibility, operations, recovery, documentation, peer review and deployment checklist to pass.

## Runtime acceptance attempt: 2026-07-22

### Candidate and scope

- Candidate application version: `1.3.0`
- Candidate schema version: `1.1.0`
- Branch supplied for acceptance: `main`
- Production deployment: prohibited and not attempted
- WooCommerce Purchase Attribution: prohibited and not started

### Step 1 environment verification result

Status: **Blocked before installation**.

The acceptance host was inspected read-only for an existing disposable staging environment. No usable local or remote target was available:

- No configured staging URL or staging credentials are present in the repository documentation.
- No existing signed-in staging tab was available in the connected browser.
- `docker`, `podman`, `php`, `mysql`, `mariadb`, `wp`, `composer`, `node`, and `npm` were not available on `PATH`.
- No Local, XAMPP, Laragon, Docker, or Podman installation was found in the conventional Windows installation locations checked.
- No matching MySQL, MariaDB, Apache, Nginx, Docker, or WordPress service was found by the read-only service inspection.
- No sanitized production environment inventory was supplied, so a production-to-staging comparison cannot be completed.

Consequently, the required WordPress version, PHP version, database version, web server, HTTPS state, WP-Cron configuration, SMTP configuration, active plugins, active theme, multisite state, object cache, table prefix, and operating-system environment cannot yet be recorded for a staging target.

### Acceptance actions not executed

Because Step 1 did not identify a disposable target, no candidate files or customer data were transmitted and no external state was changed. The following were intentionally not attempted:

- Baseline database backup or restore proof
- Candidate installation, activation, or schema migration
- Gates A–E runtime and adversarial tests
- Browser, mobile, keyboard, screen-reader, zoom, contrast, or reduced-motion tests
- SMTP, WP-Cron, cleanup, outage, backup, restore, or rollback tests
- Runtime security and dependency scans requiring the target stack
- Gate F approval or production-package creation

### Gate disposition after this attempt

| Gate | Status | Runtime disposition |
|---|---|---|
| A | Partial | Source tests exist; production-like runtime evidence is absent. |
| B | Partial | Source tests exist; SMTP, timing, cookie, expiration, rotation, and multi-device runtime evidence is absent. |
| C | Partial | Source authorization tests exist; staging adversarial and cross-origin evidence is absent. |
| D | Partial | Source consent/memory tests exist; MySQL concurrency and complete lifecycle runtime evidence is absent. |
| E | Partial | Source administration tests exist; WordPress role, nonce, cron, mail-health, and admin UI runtime evidence is absent. |
| F | Fail | Mandatory staging, E2E, accessibility, operations, recovery, security, and peer-review evidence is absent. |

No defect in candidate source was confirmed during this attempt because the application could not be installed. The confirmed issue is an **environmental blocker**, not a waived product defect.

### Required unblock

Provide one of the following:

1. A disposable production-like WordPress/PHP/MySQL staging URL with administrator access, database/backup access, a test mailbox/SMTP path, and authorization to create two synthetic customers and role-test users; or
2. Authorization and prerequisites to install a local disposable stack on this Windows host.

Also provide a sanitized production environment inventory for the Step 1 comparison. Do not provide passwords, tokens, private keys, or other secrets in repository files or chat; credentials should be entered through the staging platform's secure login flow.

## Runtime acceptance continuation: 2026-07-22

### Disposable environment provisioned

- LocalWP: `10.1.1` (official WPEngine-signed Windows installer; published SHA-1 verified before installation)
- Site: `budly-phase-3-runtime`
- Exposure: local only; Windows Firewall access for nginx was denied and Local Live Link remains disabled
- HTTPS: enabled and trusted; local HTTPS request succeeds without bypassing certificate validation
- WordPress: `7.0.2`
- PHP: `8.2.29`
- Web server: nginx `1.26.1`
- Database: MySQL `8.4.0`
- Multisite: disabled
- Theme: Twenty Twenty-Five
- Database prefix: `wp_`
- WP-Cron: enabled (`DISABLE_WP_CRON=false`); scheduled execution remains to be proven
- Debugging: `WP_DEBUG=true`, `WP_DEBUG_LOG=true`, `WP_DEBUG_DISPLAY=false`
- SMTP: LocalWP mail-catching/runtime delivery test remains pending
- Object cache: runtime verification pending
- Operating system: Windows host

Production comparison remains pending because a sanitized production inventory has not been supplied. No claim of version parity is made.

### Candidate package and baseline

- Branch: `main`
- Application: `1.3.0`
- Schema: `1.1.0`
- Pre-install automated tests: `96` passed, `0` failed, `0` skipped
- Staging package: `Budly-1.3.0-STAGING-ONLY-NOT-PRODUCTION-APPROVED.zip`
- Package files: `38`
- Package SHA-256: `ad201ecace6086244f8f79358dde0052f4a88429b91e7c575792a0f8df0d2723`
- Baseline database backup: stored outside the repository under the disposable site
- Baseline backup size: `102278` bytes; `12` table definitions
- Baseline backup SHA-256: `ec1c6dd17051efb7464677b48db700165e7179b8b8318744375496934b8d036d`
- Baseline restore: passed

An initial backup command produced an empty file because standalone PHP lacked the site runtime configuration and the database port was incorrect. The file was rejected by size/table checks; its import could not connect and did not alter the database. Backup was repeated with LocalWP's bundled MySQL tools, explicit loopback port, non-output credentials, minimum-size/table validation, and a successful restore.

### Installation, migration, and initial Gate A evidence

- WordPress upload, installation, and activation: passed
- Plugin version shown by WordPress: `1.3.0`
- Schema option: `1.1.0`
- Budly tables present: `15` including legacy sales tables
- Schema migration rows: `1`
- Default agent rows: `1`
- Required Phase 5 provenance and content-hash fields: present and nullable for legacy rows
- Required unique indexes for consent, sessions, replay/idempotency, customer/content duplicate prevention, and memory contexts: present
- Registered secure-memory REST paths: `24` under `/budly-identity/v1`
- Anonymous administrator health request: denied `403` with `ADMIN_PERMISSION_REQUIRED`
- Anonymous customer session request: denied `401` with `AUTHENTICATION_REQUIRED`
- Error envelope: passed for these probes; includes request correlation identifier and API timestamp/version
- Sensitive response headers: `Cache-Control: no-store, private, max-age=0`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, and `X-Frame-Options: DENY`
- Authenticated WordPress health view: `healthy`, schema `1.1.0`, active sessions `0`, active memory `0`
- Browser-visible fatal error: none
- WordPress debug log after activation: no log created, indicating no logged activation error at this checkpoint

A first route probe incorrectly used `/budly/v1/health`; the authoritative namespace is `/budly-identity/v1` and health is `/admin/health`. This was a harness-path error, not a candidate defect. Corrected route enumeration and endpoint tests passed.

### Current gate checkpoint

| Gate | Status | Runtime disposition |
|---|---|---|
| A | Pass | Two repeat activations, persistence, audit, clean baseline recovery, remigration, routes, headers and health passed. |
| B | Pass | Passwordless verification, enumeration resistance, throttling, protected cookies, CSRF, session lifecycle, revocation and cross-customer isolation passed after two source fixes. |
| C | Partial | Source tests only; adversarial multi-customer/multi-role runtime tests remain. |
| D | Partial | Schema evidence exists; consent/memory lifecycle and MySQL concurrency tests remain. |
| E | Partial | Authenticated health view and anonymous denial passed; remaining administration operations and nonadministrator tests remain. |
| F | Fail | Mandatory Gates A-E completion, E2E, accessibility, operations, security scans, rollback, and production comparison remain. |

### Gate A completion and Gate B start

- Two deactivate/reactivate cycles preserved 15 Budly tables, one 1.1.0 migration row, one agent row, 24 REST paths, scopes/namespaces, two synthetic customers, a synthetic preference, and readable audit rows without duplicates or fatal errors.
- Manual and scheduled cleanup created administrator/system audit rows with bounded deletion counts and duration only; tested metadata contained no raw credentials, codes, tokens, or personal data.
- Reproducible clean recovery requires dropping only the validated `wp_` tables in the exact disposable `local` database before importing the checksum-verified baseline. Recovery returned 12 baseline tables and zero Budly tables; activation then restored schema 1.1.0, 15 Budly tables, one agent, one migration row, 24 routes, and healthy authorization behavior.
- Gate B uses only `known-a@budly-runtime.test`, `known-b@budly-runtime.test`, and `unknown@budly-runtime.test` with LocalWP Mailpit 1.24.1 on loopback.
- Three initial labelled-known and three unknown requests all returned HTTP 200, identical neutral copy, 600-second expiry, and no-store controls. They were all ineligible because the first fixture used plain SHA-256 instead of the required WordPress HMAC, so those timings do not compare eligible and ineligible identities.
- Initial total timings in milliseconds were `284.9`, `155.2`, `169.3` and `179.2`, `178.5`, `226.1`. Database inspection found no raw six-digit code hashes and no raw unknown emails.
- After correcting the synthetic hashes to `HMAC-SHA256(normalized_email, wp_salt('auth'))`, a known-customer request retained the neutral HTTP 200 response and produced exactly one captured Mailpit message.
- Mailpit captured eligible verification mail locally with the correct synthetic recipient and neutral subject/template. Codes were consumed only as ephemeral variables and were absent from database values, audit metadata, WordPress/PHP/nginx logs, repository files, and client persistence. The client retains CSRF material only in in-memory JavaScript state; it does not use localStorage, sessionStorage, or IndexedDB.
- Correct, incorrect, expired, replayed, replaced, exhausted and whitespace-wrapped code cases passed. Codes are password-hashed, successful use is atomic and single-use, five failed attempts lock the request, and a newer request invalidates the older code.
- Five eligible and five ineligible timing samples per final run retained equivalent HTTP status, neutral body, relevant headers and visible behavior. Final eligible range was `162.3-223.5 ms` (median `181.2 ms`); ineligible range was `142.6-177.5 ms` (median `154.0 ms`); median separation was `27.2 ms`. Across repeated runs median separation ranged `5.6-27.2 ms`, with overlapping ranges and no practical enumeration signal. These small local samples are operational evidence, not a statistical guarantee; synchronous Mailpit delivery is included in total eligible time.
- Resend cooldown passed for known and unknown identities with identical `429 RATE_LIMITED` messaging. Isolated per-email testing observed `200,200,200,429`; per-IP testing observed ten accepted requests and the eleventh denied. Cooldown and one-hour-window recovery passed. Unknown identities consumed equivalent controls and audit metadata remained hashed/scrubbed.
- Session rows used unique opaque identifiers and 64-character HMAC token hashes. Cookies were `Secure`, `HttpOnly`, `SameSite=Strict`, path `/`, host-only, with 30-minute idle and two-hour absolute expiration. Reload, tabs represented by shared cookie state, independent browser/session state, two simultaneous sessions and two-customer isolation passed.
- Missing, invalid, other-session and other-customer CSRF material failed with `403 CSRF_VALIDATION_FAILED`; valid session-bound material succeeded. Missing, altered/random, expired, revoked and logged-out sessions failed with `401`. Idle and absolute expiration, individual revocation, customer-wide revocation isolation, logout/use-after-logout, multiple sessions and fresh post-verification token/session issuance passed.
- Defect `GB-01` (medium): immediate resend had no cooldown. Added configurable 60-second server-side cooldown applied before eligibility lookup to both known and unknown hashes; regression coverage and runtime retest passed.
- Defect `GB-02` (medium): same-second session touches could return zero changed rows and be misclassified as revocation. Session touch now distinguishes database failure from an unchanged active row and rechecks active/revoked state; regression coverage and rapid CSRF/logout retest passed.
- Procedure corrections, not product defects: clean SQL restoration must drop only validated disposable `wp_` tables; synthetic email hashes require WordPress HMAC; Mailpit recipient metadata is an array; exact request IDs are used when aging throttle fixtures.
- Gate B final disposition: **Pass**. No unresolved high- or critical-severity Gate B finding remains.

## Gates C-E and production-readiness checkpoint: 2026-07-28

### Gate C - Pass

- Two isolated verified customers and administrator, subscriber, anonymous, expired, revoked, and malformed-session cases were exercised against the LocalWP REST runtime.
- Ownership always resolved from the server session. Injected customer identifiers did not select another customer.
- Missing/invalid session, missing/invalid/cross-session CSRF, cross-origin requests, namespace/scope violations, and nonadministrator administration calls were denied.
- Individual and customer-wide revocation remained customer-scoped. No cross-customer profile, memory, correction, deletion, export, consent, or session access succeeded.

### Gate D - Pass

- Independent storage, memory-use, and marketing consent creation/withdrawal passed with version, source, policy version, and timestamps.
- Profile allowlisting, preview, conversation-scoped approval, Start Fresh, shared/agent namespace checks, server provenance, content hashes, retention metadata, correction, selective deletion, JSON export, and transactional delete-all passed.
- Sensitive-content, prompt-injection, payload/list/item limits, replay, idempotency, and cross-customer isolation passed.
- Concurrent equivalent summary submissions initially produced one HTTP 500 despite preserving one row. `MemoryRepository::store_summary()` now recognizes the unique-index race winner and returns the existing record; retest returned `200,200` and one row.
- An injected temporary MySQL trigger forced delete-all failure; the endpoint returned 500 and the transaction preserved the record. The trigger was removed immediately. Successful delete-all revoked only the intended customer's sessions.

### Gate E - Pass

- Administrator health/audit, manual cleanup, SMTP test, individual and customer-wide revocation, audit creation, cleanup visibility, and LocalWP Mailpit delivery passed over HTTPS.
- Anonymous, subscriber, missing/invalid nonce, and insufficient-capability administration requests were denied.
- Audit metadata recursive scrubbing and bounds passed. A runtime taxonomy defect caused dotted event types to lose dots; event normalization and audit filtering now preserve approved dots, hyphens, and underscores.
- Customer export is JSON, so spreadsheet formula injection is not applicable to the implemented export surface.

### Customer experience, accessibility, operations, and security

- Desktop and 390x844 mobile rendering had no horizontal overflow. Accessible headings, English document language, polite live region, unique IDs, input names, focus outlines, responsive controls, and reduced-motion CSS are present.
- Browser review found missing programmatic labels on sales-chat inputs and a mobile flex-stretch defect that made the submit button span the composer height. Explicit accessible names and a one-column mobile composer were added and visually retested; the mobile submit control is now 267x48 pixels.
- The DOM/accessibility tree exposed the chat region, headings, named controls, consent labels, support copy, and customer-policy link. Full independent assistive-technology certification remains an external Gate F prerequisite.
- LocalWP Mailpit SMTP, manual/scheduled cleanup visibility, baseline backup/restore, repeat migration, and rollback rehearsal passed. Database-outage recovery and production monitoring remain hosting validation items.
- Full automated suite: `96 passed, 0 failed, 0 skipped`. PHP syntax validation was attempted with the LocalWP CGI process path but the executable was unavailable after the runtime process ended; no PHP fatal or WordPress database error occurred during runtime execution.
- No Composer or npm dependency manifest exists in the plugin; dependency CVE scanning is therefore limited to the WordPress/PHP/MySQL/LocalWP platform inventory. Source security contracts cover REST authorization, CSRF, SQL preparation, output escaping/text rendering, CSV nonapplicability, rate limits, session handling, and embedded-secret patterns.
- A site-wide CSP was evaluated but not injected. The plugin uses external enqueued assets and WordPress-localized configuration; a nonce/hash-based host CSP must be validated against the complete production theme/plugin stack.

### Defects corrected

| ID | Severity | Gate | Resolution |
|---|---|---|---|
| GD-01 | Medium | D | Duplicate-summary race now returns the unique-index winner instead of HTTP 500; regression assertion added. |
| GE-01 | Medium | E | Audit event normalization/filtering preserves the documented event taxonomy; regression assertion added. |
| UX-01 | Medium | F | Sales inputs now have programmatic accessible names; regression assertions added. |
| UX-02 | Medium | F | Mobile composer stacks its submit button below the fields; regression and browser visual retest passed. |

### Current disposition

| Gate | Status | Basis |
|---|---|---|
| A | Pass | Activation, migration, persistence, recovery, health, routes, headers, and audit passed. |
| B | Pass | Passwordless verification, enumeration controls, sessions, CSRF, lifecycle, and isolation passed. |
| C | Pass | Adversarial ownership, authorization, role, origin, scope, and cross-customer runtime tests passed. |
| D | Pass | Complete consent/memory lifecycle, concurrency, rollback, privacy, and isolation tests passed. |
| E | Pass | WordPress administration, capabilities, nonces, audit, SMTP, cleanup, and revocation tests passed. |
| F | Fail | No unresolved high/critical source defect, but production inventory comparison, independent screen-reader/peer review, production-stack CSP compatibility, and hosting outage/monitoring validation remain mandatory. |

Corrected staging-only package SHA-256: `569299c79e54e53093d1b172d7f35e7332896804a1e56a550fa4e0679f473b0d`. This is not a production-approved package.
