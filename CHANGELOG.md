# Changelog

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
