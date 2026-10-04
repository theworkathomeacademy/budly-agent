# G9C Readiness Proof — 2026-10-03

## Classification

NON-PRODUCTION / SYNTHETIC / READINESS EVIDENCE ONLY

Recruitment remains paused. No creator outreach, real Affiliate creation, production feature-gate activation, or money movement was performed.

## What already existed

- `AffiliateEngine` deterministic policy/state machine for applications, attribution, commissions, maturity, reversals, payout preparation, and audit-supporting ledger events.
- Identity, vanity-route, preference, analytics, and role-isolated Budly reference services.
- WordPress Affiliate invitation/application/portal/admin classes, with the five production feature flags defaulting OFF.
- Additive `bros_affiliate` migration and RLS policy text, not executed against PostgreSQL in this run.
- Prior 50-test Affiliate Phase E acceptance suite.

## What was built

- `PublicAffiliateKnowledge`: governed public Affiliate answers with PRIVATE PILOT / PUBLIC APPLICATIONS CLOSED truth and no private-token disclosure.
- `G9COperatingExperience`: synthetic application queue, owner approve/reject/hold boundary, terms acceptance, identity/assets, affiliate self-service view, owner operations view, audit evidence, and prepared-but-not-executed authority actions.
- `run_synthetic_round_trip`: one identity marked `TEST_SYNTHETIC_NON_PRODUCTION_PERSON`, exercising invitation through payout-readiness calculation, stopping before payout submission.
- R1-R15 deterministic acceptance tests plus production-flag, payout-prohibition, and outreach-package controls.
- Five real-candidate copy packages preserved as `READY_COPY` / `NOT_AUTHORIZED_FOR_SEND`, with verified routing provenance and SHA-256 hashes. The prior fictional fixture manifest was not overwritten.

## Test evidence

- `tests.test_g9c_readiness_proof` plus `tests.test_affiliate_phase_e_acceptance`: 69/69 PASS.
- `git diff --check` for the three G9C artifacts: PASS.
- Full unittest discovery: FAIL — 1,100 tests ran, with 2 behavioral failures and 82 errors. Errors include read-only temporary/output paths, missing `psycopg`, and blocked PHP subprocesses. The two observed behavioral failures are in `test_web_knowledge_001` (`safe_no_match` instead of `continue_conversation`, and zero captured grounding requests).
- PostgreSQL/Supabase migration execution, live RLS tests, WordPress browser UX, n8n orchestration, WooCommerce controlled transaction ingestion, and public `/ask-budly/` behavior were not exercised.

## Acceptance classification

The deterministic reference harness is not sufficient to label the operating ecosystem production-ready. These statuses deliberately distinguish code-path proof from integrated acceptance.

| Gate | Status | Evidence / blocker |
|---|---|---|
| R1 Public Budly Affiliate UX | FAIL | Governed answer service passes locally; public Ask Budly integration and browser acceptance not proven. |
| R2 Private invitation/application | FAIL | Synthetic service path passes; WordPress→authoritative persistence path not exercised. |
| R3 Owner application review UX | FAIL | Owner reference view exists; deployable owner UI and authoritative persistence not proven. |
| R4 Affiliate authenticated UX | FAIL | Role-isolated reference view exists; authenticated production-like UI/data retrieval not proven. |
| R5 Referral asset creation | PASS | Synthetic canonical token, vanity path, and QR reference created deterministically. |
| R6 CCSS product/rate retrieval | FAIL | Governed fixture retrieved; live/current CCSS authority was not queried end-to-end. |
| R7 Referral event | PASS | Synthetic referral event created with a 30-day context. |
| R8 Attribution | PASS | Synthetic last-qualified-referral decision attributed to the canonical Affiliate. |
| R9 Commission creation | PASS | Synthetic $200 eligible line produced an exact $60.000000 commission at the governed 30% class rate. |
| R10 Hold/maturity | PASS | Commission remained PENDING through hold and became PAYABLE only after maturity. |
| R11 Owner commission visibility | PASS | Owner reference view exposed order, amount, status, and hold data. |
| R12 Payout-readiness visibility | PASS | A $60.000000 PREPARED item was visible UNDER_REVIEW; payout submission remained false/disabled. |
| R13 Role/privacy isolation | FAIL | Negative service tests pass; PostgreSQL RLS and deployed endpoint isolation were not executed. |
| R14 Audit trail | FAIL | Ordered hashed in-memory events pass; durable authoritative database audit was not proven. |
| R15 Complete synthetic round trip | FAIL | Deterministic in-memory round trip passes, but WordPress/Budly/Supabase/n8n/WooCommerce integration was not exercised. |

## Required next proof

1. Provide an isolated writable test environment with PostgreSQL/Supabase and the existing migration.
2. Execute migration/RLS tests using synthetic auth identities for anonymous, Affiliate A, Affiliate B, and owner.
3. Wire the additive services into non-production Budly/WordPress surfaces without enabling production gates.
4. Exercise a controlled WooCommerce-compatible synthetic event through n8n and authoritative persistence.
5. Re-run browser acceptance for public, Affiliate, and owner views, then rerun the complete regression suite in a writable dependency-complete environment.

No production feature gate is required or authorized for the next isolated test-environment step.
