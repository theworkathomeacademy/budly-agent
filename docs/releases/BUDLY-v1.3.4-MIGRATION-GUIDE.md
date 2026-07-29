# Budly v1.3.4 migration guide

## Preconditions

1. Confirm application `1.3.0`, schema `1.1.0`, and baseline commit `493bedb`.
2. Verify the accepted v1.3.0 plugin artifact checksum and database backup.
3. Take a fresh staging database backup and record row counts for all existing `budly_*` tables.
4. Do not run this migration in production.

## Forward migration

Activate v1.3.4 in staging. `Bootstrap::activate()` invokes the idempotent `dbDelta` migration. Migration `1.2.0` adds:

- `budly_rule_configurations`
- `budly_decision_evidence`

Existing tables, identifiers, consent, memory, sessions, and audit rows are not transformed or deleted. The SQLite core similarly creates `decision_evidence` and `active_configurations` with `IF NOT EXISTS`.

## Verification and reconciliation

1. Confirm option `budly_secure_memory_schema_version=1.2.0`.
2. Confirm the `1.2.0` migration record and checksum.
3. Confirm both new tables and their indexes.
4. Compare every preexisting table count with its pre-migration count; expected delta is zero unless normal staging traffic occurred.
5. Repeat activation and confirm no duplicate migration/configuration rows.
6. Exercise qualification, recommendation, no-match, and escalation; confirm evidence and correlated audit rows.
7. Confirm health reports application `1.3.4`, schema `1.2.0`, and active rule versions.

## Known exceptions

LocalWP staging migrated successfully on 2026-07-29 using WordPress 7.0.2, PHP 8.2.29, MySQL 8.4.0, nginx 1.26.1, and prefix `wp_`. Both new tables were inspected and two repeat migrations produced no duplicates. Seven governed configurations were seeded exactly once.

Durable counts were unchanged: customers 2, consent 3, consent history 30, conversation memory 12, sessions 107, and verification requests 463. Audit increased from 1239 to 1240 for cleanup evidence. Cleanup expired 57 transient idempotency rows. The external database dump (707,983 bytes) and v1.3.0 plugin archive (60,537 bytes) were readable and checksummed. An isolated restore recovered schema 1.1.0 and 27 tables.
