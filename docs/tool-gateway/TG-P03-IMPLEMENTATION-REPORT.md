# TG-P03 — BROS Tool Gateway `activity.record`

Status: controlled local non-production T2 prototype. Production deployment is prohibited.

## A. Baseline

- Repository: `C:\Users\19196\Documents\Codex\2026-08-24\codex-handoff-budly-conversational-runtime-phase`
- Branch: `main`
- Starting HEAD: `87093bd33db344281d998aaa2c6e1f0b1f89ea85`
- Ending HEAD: `87093bd33db344281d998aaa2c6e1f0b1f89ea85`
- Commit created: none.
- Initial state: accepted Phase 1, TG-P01, and TG-P02 files were untracked and uncommitted. They were preserved.
- Final state: TG-P03 files are also untracked and uncommitted for MATT-003 review.

## B. Reuse

TG-P03 reuses the accepted canonical gateway for:

- request/result envelopes and correlation IDs;
- actor recognition and capability-specific permission evaluation;
- Level/T authority reconciliation;
- production environment blocking;
- purpose and channel enforcement;
- Registry-controlled adapter routing;
- health and unavailable handling;
- context minimization;
- normalized errors and failures;
- audit sink, evidence IDs, and UTC timestamps.

The T2 grant uses the existing `reconcile_authority` rule: Level 1/T2 remains denied unless the registered capability explicitly marks a specifically authorized bounded write. Only `activity.record` carries that grant.

Duplicated Gateway logic: none. Write-specific idempotency, append, postcondition, and rollback behavior is a capability execution branch inside the accepted Gateway.

No parallel write gateway or second actor/authority/audit system was created.

## C. Files

Created:

- `tests/test_tg_p03_activity_record.py` — exactly TG-P03-T01 through TG-P03-T20.
- `docs/tool-gateway/TG-P03-IMPLEMENTATION-REPORT.md` — this report.

Modified:

- `src/budly_runtime/tool_gateway.py` — typed activity contracts, bounded T2 registration support, explicit activity grants, append-only store/adapter, idempotency, postconditions, activity audit fields, and transaction rollback.

Deliberately untouched:

- TG-P01/TG-P02 tests and synthetic fixtures;
- conversational orchestrator;
- all WordPress/PHP code;
- secure memory, consent, lifecycle, commerce, attribution, products, pricing, and policies;
- database schema and migrations;
- endpoints, deployment, DNS, Cloudflare, n8n, Supabase, WooCommerce, credentials, and production configuration.

## D. Capability registration

```text
capability_id: activity.record
capability_version: 1.0
bros_level: 1
tool_class: T2
specifically_authorized_bounded_write: true
operation: append-only
idempotency: required
environments: automated_test, development, prototype
purposes: relationship_history, interaction_recording, support_history, recommendation_evidence, internal_test
channels: website_chat, internal_test, admin_console, system_internal
adapter: local_activity_store 1.0
fallback: none
```

Allowed activity types are exactly:

```text
conversation_started
conversation_completed
education_provided
recommendation_presented
customer_response_recorded
human_escalation_requested
support_interaction
approved_journey_interaction
```

## E. Write semantics

- Append-only: the public store surface provides `append`, `get`, `get_by_idempotency_key`, and `count`; no update, patch, replace, or delete operation exists.
- Immutable record: server-generated activity ID and recorded time are stored with the validated source fact, subject, correlation, idempotency key, properties, and classification.
- First use: prepares and appends one record, validates count/key/content postconditions, persists separate audit evidence, and returns `recorded=true`.
- Exact retry: semantic fingerprint excludes volatile server fields; it returns the same activity ID with `recorded=false`, `duplicate=true`, and creates no second activity.
- Conflict: the same key with materially different client-authoritative content returns `IDEMPOTENCY_CONFLICT`; count remains unchanged.
- Atomicity: write failure commits zero records. Postcondition failure privately rolls back the staged append. Required-audit failure privately rolls back the staged append and returns `AUDIT_FAILURE`; success is never reported.
- Protected state: activity type and property allowlists deny consent, lifecycle, purchase, membership, subscription, identity, product, price, and policy mutation attempts. The capability only records an approved fact; it cannot cause the underlying event.
- Activity and audit remain separate records. Audit stores a hashed idempotency reference, decision, activity ID, authority, actor, capability, and correlation—not properties or PII.

## F. Acceptance matrix

| ID | Test function | Expected | Actual evidence | Result |
|---|---|---|---|---|
| T01 | `test_t01_authorized_activity_creates_exactly_one_record` | One record and audit | `SUCCESS`; count 1; audit references returned activity | PASS |
| T02 | `test_t02_unknown_actor` | `UNKNOWN_ACTOR`; zero writes | Exact denial; adapter untouched; count 0 | PASS |
| T03 | `test_t03_production_environment` | `ENVIRONMENT_DENIED`; zero writes | Production blocked before adapter; count 0 | PASS |
| T04 | `test_t04_unknown_capability` | `UNKNOWN_CAPABILITY` | Exact denial; count 0 | PASS |
| T05 | `test_t05_unauthorized_activity_type` | Protected type denied | `ACTIVITY_TYPE_NOT_AUTHORIZED`; count 0 | PASS |
| T06 | `test_t06_malformed_input` | `INPUT_VALIDATION_FAILED` | Missing subject denied; adapter untouched; count 0 | PASS |
| T07 | `test_t07_missing_idempotency_key` | Specific denial | `IDEMPOTENCY_KEY_REQUIRED`; count 0 | PASS |
| T08 | `test_t08_exact_duplicate` | Same activity, no duplicate write | Same ID; second result duplicate; count 1; audit `DUPLICATE` | PASS |
| T09 | `test_t09_idempotency_conflict` | Conflict; no second write | `IDEMPOTENCY_CONFLICT`; count remains 1 | PASS |
| T10 | `test_t10_correlation_preservation` | Request/result/activity/audit match | All correlation IDs equal | PASS |
| T11 | `test_t11_caller_cannot_select_storage_provider` | Caller cannot route storage | Extra `provider=supabase` rejected; local adapter remains selected; count 0 | PASS |
| T12 | `test_t12_context_pii_injection` | PII rejected/minimized | Denied before adapter; no PII in response or store | PASS |
| T13 | `test_t13_inference_cannot_become_verified_fact` | Inference cannot be verified fact | `FACT_CLASSIFICATION_INVALID`; count 0 | PASS |
| T14 | `test_t14_consent_cannot_be_changed` | Consent unchanged | `consent_granted` denied; sentinel unchanged; count 0 | PASS |
| T15 | `test_t15_lifecycle_cannot_be_changed` | Lifecycle unchanged | Mutation property denied; sentinel unchanged; count 0 | PASS |
| T16 | `test_t16_purchase_truth_cannot_be_changed` | Purchase truth unchanged | `purchase_completed` denied; sentinel unchanged; count 0 | PASS |
| T17 | `test_t17_existing_activity_cannot_be_mutated` | Existing activity immutable | Mutation target property denied; original semantically identical; count 1 | PASS |
| T18 | `test_t18_simulated_write_failure` | Failure, zero partial write | `FAILED/WRITE_FAILED`; count 0 | PASS |
| T19 | `test_t19_audit_failure_rolls_back` | No success without audit | `FAILED/AUDIT_FAILURE`; append rolled back; count 0 | PASS |
| T20 | `test_t20_tg_p01_and_tg_p02_regression_preservation` | Both predecessors 20/20 | Nested TG-P01 and TG-P02 suites each ran 20 and succeeded | PASS |

Dedicated TG-P03 result: `Ran 20 tests in 0.011s — OK`.

## G. Regression

```text
python -m unittest tests.test_tg_p01_tool_gateway -v
Ran 20 tests in 0.003s — OK

python -m unittest tests.test_tg_p02_operational_metrics -v
Ran 20 tests in 0.007s — OK

python -m unittest tests.test_tg_p03_activity_record -v
Ran 20 tests in 0.011s — OK

python -m unittest discover -s tests -v
Ran 264 tests in 5.570s — OK
```

The full suite used the installed PHP 8.2.33 CLI for existing PHP-backed wrapper tests. No PHP file changed.

## H. Security

- No production system, data, credential, or API accessed.
- No PII or real customer subject used.
- No network call or public endpoint created.
- No database migration, Supabase, CRM, PostgreSQL, or external persistence used.
- No production WordPress, WooCommerce, Cloudflare, n8n, Gmail, Wix, or payment processor contacted.
- No update/delete/correction capability added.
- No protected neighboring state mutation occurred.
- No subsequent capability was implemented.
- No commit or deployment occurred.

## I. Deviations

No deviations.

## J. Known limitations

- Process-local store and audit sink only; restart clears all prototype evidence.
- Single-process idempotency; no concurrency or distributed transaction proof.
- Private rollback exists solely for a just-staged local append after postcondition/audit failure; it is not exposed as activity deletion authority.
- Explicit synthetic subjects/sources and bounded scalar properties only.
- No correction, update, delete, persistence, production identity, external source verification, fallback provider, or production integration.

## K. Final classification

**TG-P03 PASS — READY FOR MATT-003 ACCEPTANCE**

This report does not authorize TG-P04, a commit, deployment, or production action.
