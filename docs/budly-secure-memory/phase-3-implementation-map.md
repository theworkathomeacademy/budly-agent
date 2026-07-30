# Phase 3 Implementation Map

Status: Phase 0 repository reconnaissance complete  
Authoritative baseline: Assets 1–5, version 1.0  
Existing deployed implementation: Budly Sales Agent 1.2.0 (incomplete MVP)

Current implementation checkpoint: Phases 1–9 and Phase 10 documentation complete in source; 96 automated tests pass. WordPress/MySQL/browser/accessibility/operations runtime validation remains.

## Repository assessment

The repository contains a small WordPress plugin under
`deploy/wordpress/budly-sales-agent`, a separate Python sales-agent prototype,
configuration files, and Python `unittest` tests. The secure-memory work belongs
inside the WordPress plugin. The Python sales and affiliate prototypes are outside
Phase 3 and must remain untouched.

The deployed 1.2.0 plugin uses two public `admin-ajax.php` handlers for code
request and verification, WordPress transients for verification state, and three
legacy tracking tables. It returns profile and conversation data immediately from
the verification response. It does not implement the approved REST trust layer,
server-side verified sessions, independent consent types, agent authorization,
memory-use approval, deletion, append-only security auditing, cleanup, or the
approved administration surface.

## Detected application structure

- Plugin bootstrap: `deploy/wordpress/budly-sales-agent/budly-sales-agent.php`
- Legacy tracking and recall: `deploy/wordpress/budly-sales-agent/includes/tracking.php`
- Customer application: `deploy/wordpress/budly-sales-agent/assets/budly-sales.js`
- Customer styling: `deploy/wordpress/budly-sales-agent/assets/budly-sales.css`
- Floating entry control: `deploy/wordpress/budly-sales-agent/assets/budly-entry.js`
- Existing static/package tests: `tests/test_wordpress_package.py`
- Existing installation guide: `deploy/wordpress/INSTALL.md`
- No Composer, PHPUnit, WordPress test harness, or CI workflow is currently present.

## Reusable components

- WordPress plugin activation and asset-loading integration.
- Existing Ask Budly shortcode and responsive chat shell.
- WooCommerce-independent customer page.
- Existing WordPress capability and nonce patterns for administration.
- Existing support-email configuration and `wp_mail()` integration point.
- HMAC identity helper, prepared-query conventions, and output escaping patterns.
- Existing tracking dashboard may remain as a separate sales-events view.

Reuse does not imply approval of the current security design. Legacy customer and
conversation records require an explicit migration/import policy before they may
become authoritative Phase 3 memory.

## Confirmed conflicts and risks

1. Public tracking trusts browser-provided consent, identity, and summaries. This
   permits forged consent and customer-memory poisoning.
2. Verification returns memory without creating a server-side verified session.
3. Public AJAX actions replace the required versioned JSON REST API.
4. Verification requests are stored in transients, not the required database-backed
   verification model with immutable expiry and auditability.
5. Failed verification attempts refresh the transient lifetime.
6. Customer ownership is selected using the submitted email rather than resolved
   exclusively from a validated session.
7. Consent is one Boolean rather than independent storage, use, and marketing
   decisions with history, version, timestamp, and source.
8. Memory is an unrestricted text summary without namespaces, classification,
   schema version, consent reference, agent registration, scope, or purpose checks.
9. No customer preview/approve/start-fresh/privacy/profile/delete/logout journey
   exists as specified.
10. No append-only security audit, health API, session administration, SMTP test,
    cleanup scheduler, migration framework, or operational documentation exists.
11. Existing tests primarily assert that source strings exist and do not exercise
    WordPress authorization boundaries.

## File-level implementation plan

The existing plugin package will remain the deployable unit, but Phase 3 will be
implemented as focused modules under `includes/SecureMemory/`:

- `Bootstrap.php`: service wiring, activation, REST and cron registration.
- `Config.php`: centralized operational defaults and stable API version.
- `Errors.php` and `Response.php`: machine-readable errors and response envelopes.
- `Database/Migrator.php` and `migrations/`: repeatable schema migrations.
- `Database/Repository.php`: prepared data access primitives.
- `Audit/AuditService.php`: append-only security and administrative events.
- `Verification/VerificationService.php`: requests, hashing, expiry, attempts,
  resend rules, enumeration resistance, and email delivery.
- `Email/EmailTransport.php` and `WordPressMailTransport.php`: replaceable delivery.
- `Sessions/SessionService.php`: token hashing, cookies, validation, expiry,
  logout, and revocation.
- `Consent/ConsentService.php`: current consent, immutable history, and fail-closed
  decisions.
- `Authorization/AgentRegistry.php`: registered-agent scope and namespace enforcement.
- `Idempotency/IdempotencyService.php`: database-backed replay and concurrent-duplicate control.
- `Profile/ProfileService.php` and `PreferenceService.php`: allowlisted, consent-aware profile and preference access.
- `Memory/MemoryPolicy.php`, `MemoryRepository.php`, and `MemoryService.php`:
  allowlisted preview, context-bound use approval, Start Fresh, structured summaries,
  provenance, correction, export, selective/delete-all behavior, retention and isolation.
- `Api/Routes.php`: `/wp-json/budly-identity/v1` controllers.
- `Admin/AdminPage.php`: health, verification/session metrics, audit, revocation,
  SMTP test, cleanup, configuration, and schema status.
- `Cleanup/CleanupService.php`: bounded scheduled cleanup and run summaries.
- `assets/budly-secure-memory.js` and `.css`: Asset 3 state machine and copy.
- `tests/secure_memory/`: executable unit-style contract tests plus WordPress
  integration/API/security test scaffolding appropriate to the available runtime.
- `docs/budly-secure-memory/`: architecture map, installation, configuration,
  administration, operations, security, testing, deviations, and final report.

## Testing strategy

1. Preserve and run the existing 38 tests after each milestone.
2. Add source-contract tests for every security boundary immediately, because the
   current environment lacks PHPUnit and a WordPress test database.
3. Add pure-PHP service seams so critical algorithms can be tested independently
   when PHP tooling is available.
4. Add WordPress integration/API/security test definitions for verification,
   sessions, consent, memory, administration, migration, and cleanup.
5. Perform live manual E2E only after local gates pass and deployment is explicitly
   authorized.
6. Do not mark a gate passed on static tests alone when Asset 4 requires runtime
   behavior.

## Current environment constraints

- PHP CLI and PHPUnit are not currently available on the normal command path.
- No disposable WordPress integration-test database is configured.
- No CI workflow or coverage tool is configured.
- A real consenting mailbox is required for final email-to-session E2E testing.
- Production deployment is not implied by implementation and requires separate
  authorization after acceptance gates pass.

These constraints do not block modular implementation, migrations, contract tests,
documentation, or correction of the client-forged-consent vulnerability. They do
block truthful completion of runtime WordPress integration and production E2E gates
until the corresponding environment is available.

## Phase 5 migration delta

Schema version 1.1.0 adds `budly_memory_contexts` and `budly_idempotency`. It adds nullable upgrade-safe provenance/content-hash/correction columns and retention policy metadata to `budly_conversation_memory`. New summary records always populate these fields. The migration also registers the default sales agent with explicit scopes and `shared`/`sales` namespaces. No WooCommerce tables or attribution logic were added.

## Implemented Phase 6–10 structure

- `assets/budly-secure-memory.js` and CSS additions implement the Asset 3 journey.
- `Admin/*` and `assets/budly-secure-memory-admin.js` implement protected operations.
- `Cleanup/CleanupService.php` implements daily/manual bounded cleanup.
- `Security/RequestSecurity.php` implements HTTPS, same-origin and defensive headers.
- Phase-specific executable suites under `tests/test_secure_memory_phase5.py` through `phase9.py` provide local boundary evidence.
- API, schema, security, operations, runtime acceptance and final-candidate documents provide the Phase 10 handoff.

The repository is a runtime-validation candidate, not a production-ready or deployed release. Gates must not be upgraded based on source markers alone.
