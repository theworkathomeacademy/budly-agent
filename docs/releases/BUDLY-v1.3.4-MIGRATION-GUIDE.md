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

This workspace does not include a live WordPress/MySQL runtime. Source-level migration and idempotency contracts are automated; live staging reconciliation remains required before release acceptance can be upgraded from partial.
