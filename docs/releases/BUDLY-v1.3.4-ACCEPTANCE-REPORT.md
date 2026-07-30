# Budly v1.3.4 acceptance report

Release result: Complete
Application: `1.3.4`  
Schema: `1.2.0`  
Baseline: `493bedb`  
Environment: LocalWP staging; WordPress 7.0.2, PHP 8.2.29, MySQL 8.4.0, nginx 1.26.1

## Applicable tests

- Version and configuration validation
- Qualification and recommendation evidence
- Allowlist exclusions and no-match
- Escalation and audit linkage
- Configuration/migration idempotency
- Protected admin evidence contract
- All accepted identity, session, consent, memory, CSRF, authorization, audit, cleanup, and administration regressions

## Results

Final automated result: 110 tests passed with 15 passing subtests, 0 failed, 0 skipped, and 0 blocked. The accepted baseline contained 96 tests; 14 v1.3.4 tests were added.

## Gates

| Gate | Status | Evidence |
|---|---|---|
| A Foundation | Pass | Staging migration, idempotent initialization, evidence/audit persistence |
| B Authentication | Pass retained | Existing verification/session tests |
| C Authorization | Pass retained | Existing isolation/role tests |
| D Consent and Memory | Pass retained | Existing fail-closed consent/memory tests |
| E Administration | Pass | HTTPS-aware REST acceptance: anonymous 403, subscriber 403, administrator 200, invalid filter 422 |
| F Production Readiness | Blocked | Production authorization and external evidence absent |

## Defects and residual risks

- Repository baseline evidence reports 96 tests while the handoff states 100.
- Staging migration 1.1.0 to 1.2.0 passed. Table structure and indexes were inspected; two repeat runs preserved counts and exactly seven active configurations.
- Reconciliation preserved customers (2), consent (3), consent history (30), memory (12), sessions (107), verification requests (463), and audit history. Normal cleanup expired 57 transient idempotency rows.
- Verified backups exist outside Git. An isolated restore recovered schema 1.1.0 and all 27 backed-up tables.
- The active browser journey uses server-authoritative `POST /budly-identity/v1/decisions/evaluate`. All ten governed scenarios created exactly ten decisions and correlated audits; replays created no duplicates.
- Admin acceptance passed for roles, pagination, filters, ordering, empty results, invalid input, and the 100-record bound.
- Security negatives passed: missing nonce 403, hostile origin 403, invalid idempotency 422, invalid session 401, fabricated product excluded, and sensitive objective withheld.
- No production deployment occurred.

## Deferred acceptance

Full BROS v1.7 CRM/lifecycle/workflow/intelligence/dashboard acceptance and Gate F are deferred. This report does not claim full v1.7 acceptance.
