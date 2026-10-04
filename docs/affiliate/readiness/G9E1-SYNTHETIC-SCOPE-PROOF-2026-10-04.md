# G9E.1 Synthetic Scope Proof — 2026-10-04

## Outcome

Synthetic-only server authorization is implemented and proven in the isolated G9D database/runtime. It has not been deployed to production. All production Affiliate gates remain OFF.

## Trusted identity source

`bros_affiliate.synthetic_test_scopes` is the authoritative server-side mapping. It requires the fixed classification `TEST_SYNTHETIC_NON_PRODUCTION_PERSON`, an exact WordPress user ID, Affiliate UUID/code, canonical referral token, non-commercial destination, synthetic campaign, synthetic event, synthetic order, active state, and expiry.

The table is unavailable to `anon` and `authenticated`; `service_role` has read-only access. Client query parameters, cookies, request roles, display names, emails, and request-body synthetic flags cannot create or widen a scope.

Isolated proof identity:

- WordPress test user ID: `990001`
- Affiliate UUID: `50000000-0000-0000-0000-000000000001`
- AFF ID: `AFF-900001`
- Referral token: `G9ESYNTH900001`
- Destination: `SYNTH-WELLNESS`
- Campaign: `G9E-SYNTH-CAMPAIGN-001`
- Event: `G9E-SYNTH-EVENT-001`
- Order: `G9E-SYNTH-ORDER-001`
- Maximum isolated scope duration: 30 minutes

These identifiers are test fixtures, not production identities or entitlements.

## Authorization formula

For portal, referral, attribution, and commission operations:

`GLOBAL GATE ON AND ACTIVE UNEXPIRED TRUSTED SCOPE AND EXACT IDENTITY/EVENT MATCH = ALLOW`

Every missing, expired, inactive, ambiguous, or mismatched value returns DENY. The payout gate cannot be enabled through the guard and `payout_allowed()` always returns false.

## Durable audit

Both ALLOW and DENY decisions persist actor, synthetic identity, event/order where applicable, gate name/state, scope match, decision, reason, timestamp, and an allowlisted evidence object. Audit rows are immutable. Raw invitation tokens, cookies, credentials, and secrets are excluded.

PostgreSQL proof:

```text
G9E1_SYNTHETIC_SCOPE_PROOF_PASS
scopes=1
audit_events=2
enabled_production_flags=0
anon_scope=false
authenticated_scope=false
service_scope=true
```

## Tests

- Python synthetic-scope, G9D, G9C, and Phase E Affiliate regression: `92 passed`.
- WordPress portal harness: PASS.
- PHP syntax checks: PASS.
- Patch whitespace validation: PASS.

The deterministic suite covers all 16 requested cases plus owner impersonation denial, synthetic Affiliate B denial, audit secret exclusion, expiration, and immutable audit behavior.

## Production status and blocker

No production deployment was attempted because the WordPress plugin directory contains substantial pre-existing unrelated dirty work. Building and uploading that tree would mix G9E.1 with changes outside this authorization and would not provide a trustworthy rollback artifact.

Before any gate activation request can be executable, the G9E.1 files must be isolated into a reviewed release artifact, deployed inertly with gates OFF, and an exact production synthetic WordPress user plus BROS/Supabase scope row must be created and verified. The isolated fixture IDs above must not be assumed to exist in production.
