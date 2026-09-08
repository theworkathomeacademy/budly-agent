# Changelog

## 1.8.1

- Added read-only administrator visibility for decoded audit metadata and conversation identifiers returned by the existing protected audit API.
- Added a local conversation-ID filter over the bounded administrator audit result set.
- Application 1.8.1; schema remains 1.5.0; rules and commerce configuration are unchanged.

## 1.8.0

- Added the governed conversational WordPress-to-Python/BROS integration with approved knowledge, GPT-5.6 Luna configuration, structured validation, and deterministic fallback.
- Conversational activation defaults OFF; durable customer memory defaults OFF and is unavailable to production conversational requests in this release.
- Application 1.8.0; schema remains 1.5.0; rules and commerce configuration are unchanged.

## 1.7.1

- Production stabilization patch for fail-closed session identity, truthful administrator aggregates, canonical lifecycle transitions, PHP adaptive-question parity, and Bootstrap loader regression coverage.
- Application 1.7.1; schema remains 1.5.0; rules remain `bros-rules-1.5.0.0`; commerce configuration remains `commerce-attribution-1.6.0.0`.
- Passed 179 automated tests, 67/67 reconstructed LocalWP runtime checks before rollback and after restoration, rollback to the `ae9ed566` production-source baseline, and deterministic dual-build verification.

## 1.7.0

- Added Conversation Intelligence, Adaptive Question Engine, Conversation State Machine, and Pattern Library.
- Added Customer Lifecycle Engine with canonical states (Visitor, Explorer, Member, Returning Member, Community Member, Advocate, Leader).
- Added Relationship Intelligence, Explainable Recommendations, and Secure Memory & Commerce Attribution integration.
- Added additive Schema 1.5.0 database tables (`conversation_state`, `conversation_pattern_history`, `relationship_health`, `member_journey`).
- Added WordPress Admin health and lifecycle reporting endpoints.

## 1.3.4

- Added governed, versioned qualification and recommendation configuration.
- Added decision evidence for qualification, recommendations, no-match, and escalation.
- Added product eligibility/exclusion provenance and confidence classification.
- Added additive schema 1.2.0 decision/configuration tables.
- Added protected administrator version, configuration, and decision visibility.
- Preserved the accepted v1.3.0 secure-memory, consent, session, and administration behavior.
- Production remains prohibited; Gate F remains blocked.
# Budly 1.3.4 acceptance completion

- Added the server-authoritative WordPress decision writer with nonce, origin, session, consent-context, rate-limit, idempotency, allowlist, no-match, escalation, evidence, and audit enforcement.
- Added bounded, filterable, consistently ordered administrator decision review with audited access.
- Passed ten governed LocalWP scenarios, HTTPS-aware administrator acceptance, security negatives, and 110 automated tests plus 15 subtests.
# Budly v1.6.0 acceptance closure

- Completed LocalWP schema migration, synthetic WooCommerce reconciliation, security/abuse checks, v1.5 rollback, and v1.6 restoration.
- Added governed aggregate CSV export with administrator capability, nonce, rate limit, audit, and data minimization.
- Made schema 1.4.0 reruns verified no-ops and isolated upgrades from legacy `dbDelta` definitions.
- Enforced WooCommerce status eligibility and cancellation/failed-payment revenue reversals.
