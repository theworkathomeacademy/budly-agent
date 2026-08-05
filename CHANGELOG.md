# Changelog

## 1.4.0

- Added deterministic WordPress packaging with embedded source manifest and SHA-256 sidecar.
- Added repository, version, release-artifact, PHP, JavaScript, migration, rollback, and security quality gates.
- Added CI and human-controlled release workflows.
- Preserved schema 1.2.0, rules `bros-rules-1.3.4.1`, and all accepted v1.3.4-R1 behavior.
- Completed 15/15 LocalWP staging subtests, exact-package rollback to v1.3.4-R1, and exact-package restoration to v1.4 without data loss.

## 1.3.4-R1

- Reconciled the accepted Git implementation with approved production-facing assets.
