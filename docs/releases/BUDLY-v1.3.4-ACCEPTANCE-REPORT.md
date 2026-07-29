# Budly v1.3.4 acceptance report

Release result: Partial  
Application: `1.3.4`  
Schema: `1.2.0`  
Baseline: `493bedb`  
Environment: Windows, Python 3.12, SQLite source tests; WordPress/PHP/MySQL runtime unavailable

## Applicable tests

- Version and configuration validation
- Qualification and recommendation evidence
- Allowlist exclusions and no-match
- Escalation and audit linkage
- Configuration/migration idempotency
- Protected admin evidence contract
- All accepted identity, session, consent, memory, CSRF, authorization, audit, cleanup, and administration regressions

## Results

Final automated result is populated from the release run: 106 tests passed, 0 failed, 0 skipped, 0 blocked in the executable suite. The accepted baseline contained 96 tests, not the 100 stated in the handoff; 10 v1.3.4 tests were added.

## Gates

| Gate | Status | Evidence |
|---|---|---|
| A Foundation | Pass retained by regression; runtime recheck pending | Migration/audit contracts |
| B Authentication | Pass retained | Existing verification/session tests |
| C Authorization | Pass retained | Existing isolation/role tests |
| D Consent and Memory | Pass retained | Existing fail-closed consent/memory tests |
| E Administration | Pass retained by regression; new live endpoint check pending | Protected admin contract |
| F Production Readiness | Blocked | Production authorization and external evidence absent |

## Defects and residual risks

- Repository baseline evidence reports 96 tests while the handoff states 100.
- Live staging MySQL forward migration, reconciliation, and restore rehearsal remain blocked by the absent runtime.
- The new WordPress decision tables/admin feed are foundational interfaces; the accepted WordPress customer journey does not yet invoke a server-side recommendation evidence writer. The active governed evidence writer is the Python deterministic application core.
- No production deployment occurred.

## Deferred acceptance

Full BROS v1.7 CRM/lifecycle/workflow/intelligence/dashboard acceptance and Gate F are deferred. This report does not claim full v1.7 acceptance.
