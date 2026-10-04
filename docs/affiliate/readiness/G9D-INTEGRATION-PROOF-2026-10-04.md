# G9D Affiliate Integration Proof — 2026-10-04

## Boundary

- Environment: isolated local PostgreSQL 16 container plus ephemeral n8n 2.32.7 data volume and local browser acceptance server.
- Classification: `TEST_SYNTHETIC_NON_PRODUCTION_PERSON`.
- Production Affiliate feature gates touched: **0**.
- Real Affiliates, creator outreach, Woo orders, payments, and payouts: **0**.
- This artifact does not authorize production deployment or recruitment.

## Provenance

- Branch: `g9d-affiliate-integration-proof`
- Preserved G9C commit: `a8badca` (`feat(affiliate): preserve G9C readiness proof`)
- The four required G9C artifacts were committed without staging or rewriting the pre-existing dirty worktree.

## Test failure classification

The two `test_web_knowledge_001` behavioral failures were Affiliate-relevant test defects, not Affiliate-engine regressions. Both tests constructed `ProductionConversationRuntime` without their deterministic repository adapter, so an external/current product lookup failed closed before their model doubles ran. Both now inject the existing deterministic adapter and pass.

The previously reported 82 errors are separately classified as environment/dependency failures (restricted temporary/output paths, unavailable `psycopg`, and blocked PHP subprocess execution). They are not counted as behavioral failures and are not claimed fixed by this proof.

## Writable integration environment

The existing Affiliate foundation migration was applied to the isolated `g9d_affiliate` database. G9D adds Supabase-compatible local JWT helpers/roles, invitation hash storage, an idempotent `bros.revenue_event.v1` ingestion function, owner/self RLS policies, service-only ingestion, and durable event/audit records. All production flags were asserted false.

Synthetic round trip result:

```text
G9D_ROUND_TRIP_PASS
AFF-900001
commission_status=PAYABLE
payout_ready=60.000000 USD
durable_revenue_events=1
durable_audit_events=10
```

The raw invitation token was not stored. Replaying the same revenue event returned `inserted=false` and left one durable event.

## RLS and durable audit

```text
anon_table_privilege=false
authenticated_ingest_rpc=false
service_ingest_rpc=true
affiliate_a_profiles=1
affiliate_a_commissions=1
affiliate_a_applications=0
affiliate_a_audit=0
affiliate_b_profiles=1
affiliate_b_commissions=0
owner_profiles=2
owner_applications=1
owner_commissions=1
owner_audit=10
owner_payout_batches=1
G9D_RLS_ROLE_PROOF_PASS
```

Anonymous direct selection was denied. Attempts to update an audit event or delete a commission-ledger row were rejected by the immutable-row trigger.

## n8n and commerce event

`integration/g9d/G9D-Woo-Compatible-Synthetic-Event.json` is disabled, manual-only, credential-free, and has no webhook or production network call. It executed successfully from an ephemeral n8n volume and normalized `G9D-ORDER-001` into `bros.revenue_event.v1`, including referral event `90000000-0000-0000-0000-000000000001`, the wellness line item, and `synthetic_classification`.

Production `AFF-WF-001..010` were not enabled or edited by this proof.

## Browser acceptance

Human-visible acceptance was performed in the in-app browser at the isolated route shapes:

- `http://127.0.0.1:18765/ask-budly/`: free-form “How much can affiliates earn?” returned governed category rates and stated that Budly cannot invent/change rates.
- `http://127.0.0.1:18765/affiliate-registration/`: showed the consumed private invitation and application lifecycle without exposing the raw token.
- `http://127.0.0.1:18765/affiliate-account/`: showed only AFF-900001 identity, referral asset, eligible offer, attributed order, and $60 payable commission.
- `http://127.0.0.1:18765/owner-affiliate/`: showed the owner decision, attribution, commission, payout-readiness proposal, and durable audit count.

The live `https://cccultivate.com/ask-budly/` route loaded and was interactive, but its visible entry UX offered products, budgets, comparisons, memberships, wholesale, and support. It did not visibly communicate `PRIVATE PILOT`, `PUBLIC APPLICATIONS CLOSED`, or an Affiliate-program entry point. No live chat message was sent and no production page was changed.

## Tests

`py -m unittest tests.test_g9c_readiness_proof tests.test_g9d_integration_contracts tests.test_web_knowledge_001 -q`

Result: **41 tests passed**.

## Readiness matrix

| Gate | Result | Evidence / limitation |
|---|---|---|
| R1 Public Budly Affiliate UX | FAIL | Isolated UX passed; actual public route does not expose the required Affiliate state/entry point. |
| R2 Private invitation / application | PASS (isolated) | Hashed, expiring, single-use invitation and persisted synthetic application. |
| R3 Owner application review UX | PASS (isolated) | Browser-visible owner decision and database record. |
| R4 Affiliate authenticated UX | PASS (isolated) | Browser-visible own account plus RLS tenant proof. |
| R5 Referral asset creation | PASS | Canonical route, vanity representation, and QR record. |
| R6 CCSS product/rate retrieval | PASS (synthetic contract) | Governed synthetic wellness offer/rule; production CCSS was not mutated. |
| R7 Referral event | PASS | Durable qualified synthetic referral. |
| R8 Attribution | PASS | Durable deterministic decision correlated to revenue event. |
| R9 Commission creation | PASS | $200 eligible revenue × 30% = $60. |
| R10 Hold / maturity | PASS | PENDING transitioned to PAYABLE only after hold condition. |
| R11 Owner commission visibility | PASS (isolated) | Owner RLS and browser surface. |
| R12 Payout-readiness visibility | PASS (isolated) | $60 proposed; no provider submission. |
| R13 Role / privacy isolation | PASS | Database-backed anonymous/A/B/owner/service proof. |
| R14 Durable audit | PASS | Ten queryable immutable material events. |
| R15 Complete integrated synthetic round trip | FAIL | Backend/n8n/database and isolated UX passed, but the actual WordPress/Budly route is not wired to this slice. |

## Recommendation

**NOT READY** for G9C real recruitment. The isolated data, RLS, audit, n8n, and browser surfaces prove the core vertical-slice mechanics. Recruitment should remain paused until the approved WordPress/Budly deployment path is wired to the integrated services and browser-accepted on the actual public, Affiliate-authenticated, and owner routes without enabling production financial behavior.
