# Changelog

## 1.8.4

- Added container-safe `CURLOPT_RESOLVE` edge resolution fallback for `runtime.cccultivate.com` to prevent hosting container DNS resolution timeouts.
- Preserved `wp_remote_post` dispatch, HMAC protocol, constant precedence, and strict `durable_memory=false` enforcement.

## 1.8.3

- Added sandbox-compatible runtime URL validation supporting environments where PHP DNS resolution for subdomains is restricted.
- Added RFC-compliant `filter_var` HTTPS validation fallback alongside `wp_http_validate_url`.
- Updated outbound runtime proxy dispatch to utilize `wp_remote_post` with `wp_safe_remote_post` fallback.
- No change to HMAC authentication protocol, signature headers, or request payload schema.
- No change to durable memory policy (`durable_memory=false` remains strictly enforced).

## 1.8.2

- Added protected server-side runtime configuration provider and options fallback when wp-config constants are absent.
- Added authenticated `/wp-json/budly-runtime/v1/configure` endpoint protected with HMAC signature verification.
- Maintained constant precedence, fail-closed isolation, durable memory disabled enforcement, and secret protection.

## 1.8.0

- Added the feature-flagged Budly natural-language conversation path through the HMAC-authenticated Python/BROS runtime.
- Added governed `knowledge.retrieve`, the approved Education Corpus v0.1, centrally assembled personality, and structured model-response validation.
- Preserved deterministic commercial and safety authority, the guided-flow fallback, and production-safe defaults with durable customer memory disabled.
- Schema remains 1.5.0; rules remain `bros-rules-1.5.0.0`; commerce configuration remains `commerce-attribution-1.6.0.0`.

## 1.7.1

- Fixed v1.7 customer-session error propagation so protected conversation and lifecycle routes fail closed without a default customer identity.
- Replaced hard-coded conversation-health and lifecycle-distribution figures with privacy-minimized database aggregates.
- Enforced canonical one-step lifecycle progression and added bounded PHP adaptive-question journey/confidence parity.
- Formalized the v1.7 Bootstrap module loaders and expanded executable PHP stabilization coverage without changing schema, customer-facing rules, or commerce configuration.

## 1.7.0

- Added Conversation Intelligence, Adaptive Question Engine, Conversation State Machine, and Pattern Library.
- Added Customer Lifecycle Engine with canonical states (Visitor, Explorer, Member, Returning Member, Community Member, Advocate, Leader).
- Added Relationship Intelligence, Explainable Recommendations, and Secure Memory & Commerce Attribution integration.
- Added additive Schema 1.5.0 database tables (`conversation_state`, `conversation_pattern_history`, `relationship_health`, `member_journey`).
- Added WordPress Admin health and lifecycle reporting endpoints.

## 1.6.0

- Added server-verified WooCommerce commerce events with stable idempotency keys, immutable evidence, replay protection, and audit correlation.
- Added deterministic order attribution, conflict and reconciliation states, refund/cancellation corrections, and currency-separated revenue metrics.
- Added protected commerce administration, reporting, CSV export, integration-health and freshness evidence without changing customer-facing behavior.
- Added additive schema 1.4.0 and separately versioned `commerce-attribution-1.6.0.0` configuration while preserving `bros-rules-1.5.0.0`.

## 1.5.0

- Added governed commercial-memory objects, versioning, provenance, confidence, aging, supersession, invalidation, expiration, correction, deletion, export, and consent enforcement.
- Added deterministic structured conversation context and a reusable server-built commercial context for governed recommendations.
- Added capability-, nonce-, session-, ownership-, rate-, and audit-protected customer and administrator controls.
- Added the additive, idempotent schema 1.3.0 migration and the `bros-rules-1.5.0.0` commercial-memory rule manifest.
- Preserved all v1.4 Engineering Platform and v1.3.4-R1 behavior; no CRM, lifecycle, attribution, workflow, autonomous reasoning, or production deployment is included.

## 1.4.0

- Added deterministic WordPress packaging with embedded source manifest and SHA-256 sidecar.
- Added repository, version, release-artifact, PHP, JavaScript, migration, rollback, and security quality gates.
- Added CI and human-controlled release workflows.
- Preserved schema 1.2.0, rules `bros-rules-1.3.4.1`, and all accepted v1.3.4-R1 behavior.
- Completed 15/15 LocalWP staging subtests, exact-package rollback to v1.3.4-R1, and exact-package restoration to v1.4 without data loss.

## 1.3.4-R1

- Reconciled the accepted Git implementation with approved production-facing assets.
