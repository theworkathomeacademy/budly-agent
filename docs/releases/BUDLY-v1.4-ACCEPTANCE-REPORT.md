# Budly v1.4 Acceptance Report

## Verdict

Complete and ready for Project Owner review. Production deployment remains prohibited.

| Domain | Evidence | Status |
|---|---|---|
| Inherited regression | 123 total tests, including 113 inherited and 10 v1.4 tests | Pass |
| Repository/version policy | Validators and negative tests | Pass |
| JavaScript | 4 files parsed by Node | Pass |
| PHP | GitHub Actions and final local PHP 8.2.29 lint; all 36 packaged PHP files | Pass |
| Packaging | Two byte-identical builds | Pass |
| Migration | No schema delta; inherited idempotency contracts | Pass |
| Rollback | Exact accepted R1 ZIP; 44/44 file match; 4.460 seconds | Pass |
| Restoration | Exact v1.4 ZIP; 44/44 file match; 5.012 seconds | Pass |
| Staging | Inherited set expanded to the command’s required functional domains | Pass: 15/15 |
| Gates A-E | Automated, runtime, authorization, data, rollback and restore evidence | Pass |
| Gate F | Production readiness and deployment | Blocked |

No test is waived. No production deployment occurred.

## Staging environment

| Property | Value |
|---|---|
| Site | `budly-phase-3-runtime.local` (local, non-production) |
| WordPress | 7.0.2 |
| PHP | 8.2.29 |
| Database | MySQL 8.4.0 |
| Web server | nginx 1.26.1 |
| Theme | Twenty Twenty-Five |
| Prefix | `wp_` |
| WP-Cron | Enabled; cleanup scheduled |
| SMTP | LocalWP Mailpit; synthetic verification delivered |
| HTTPS | Trusted certificate; explicit HTTPS page/API requests passed |
| Debug | `WP_DEBUG` and log enabled; display disabled |

Backups were created before activation and verified readable:

| Backup | Size | SHA-256 |
|---|---:|---|
| Database SQL | 738,742 | `7C36FB7A2FBDD728BE48E851485C57BD9E61D50240952DCA10EF5F2F8A3B0B2A` |
| Plugin ZIP | 472,913 | `32BB517C50CCE84877F7C5680EF703796CA60EA498D38560049B82BA2DF80A25` |
| Configuration ZIP | 10,135 | `D65F2B7B02DFCC261D621AB31C425685C414786FDC578EF4626F4C182BA84114` |

## Fifteen staging subtests

| # | Subtest | Expected | Actual | Result | Evidence |
|---:|---|---|---|---|---|
| 1 | Plugin activation | v1.4 activates without fatal error | Active, version 1.4.0 | Pass | WP-CLI and clean debug checkpoint |
| 2 | Customer-facing page | Ask Budly loads | HTTPS page and HTTP probe returned content/200 | Pass | Browser DOM and HTTP |
| 3 | Production template | Dedicated experience renders | `budly-dedicated-page`, ASK BUDLY hero and chat present | Pass | Browser DOM |
| 4 | Visual assets | Production images load | Cutout 370x615; avatar 102x105 | Pass | Browser natural dimensions |
| 5 | Passwordless verification | Eligible synthetic customer receives and uses code | Neutral request, Mailpit delivery, verify success | Pass | HTTPS REST and Mailpit |
| 6 | Secure session | Verification creates valid session | Verified server session and CSRF issued | Pass | Auth/session REST |
| 7 | Consent enforcement | Authenticated consent readable; anonymous mutation denied | Granted synthetic consent; anonymous 401 | Pass | Consent REST |
| 8 | Memory read/write | Authorized synthetic memory persists and previews | Write and preview success; one labeled row | Pass | Memory REST and DB |
| 9 | Returning customer | Existing synthetic identity verifies | `known-a@budly-runtime.test` verified | Pass | Mailpit and verification REST |
| 10 | Decision evaluation | Server records governed decision | Configuration-bound evaluation persisted | Pass | Decision REST and DB |
| 11 | Safe no-match | Unknown request selects nothing | `no_match`, null product, clarification action | Pass | Decision REST |
| 12 | Human escalation | Sensitive request routes to human | `human_review` with escalation reference | Pass | Decision REST |
| 13 | Evidence/audit correlation | Both decisions have correlated audit records | Two decisions; two correlations | Pass | DB reconciliation |
| 14 | Authorized administration | Administrator health access succeeds | HTTP 200 | Pass | Internal REST with WordPress role |
| 15 | Unauthorized access | Anonymous/subscriber admin and logged-out customer denied | Admin 403/403; consent mutation 401 | Pass | REST authorization |

## Durable reconciliation

| Record | Before | After | Explanation |
|---|---:|---:|---|
| Customers | 2 | 2 | Unchanged |
| Verification requests | 463 | 464 | One synthetic acceptance request |
| Sessions | 110 | 111 | One synthetic verified session |
| Consent / history | 3 / 30 | 3 / 30 | Unchanged |
| Conversation memory | 12 | 13 | One labeled synthetic acceptance memory |
| Audit | 1280 | 1289 | Expected verification/session/memory/decision/admin evidence |
| Idempotency | 20 | 24 | Controlled decision/memory request keys |
| Decision evidence | 20 | 23 | One initial fixture plus accepted no-match and escalation |
| Governed configurations | 7 | 7 | Exact versions unchanged |
| Schema migrations | 2 | 2 | No migration |

Rollback and v1.4 restoration preserved every post-test count exactly. No customer, consent, history, configuration, migration, memory, decision, or audit record was lost.
