# Budly v1.5 Migration Guide

## Scope

This additive, idempotent migration advances schema 1.2.0 to 1.3.0. It does not alter or delete customer, consent, session, legacy memory, decision-evidence, audit, or configuration records.

## Preconditions

1. Confirm the installed source is the accepted `budly-v1.4` baseline.
2. Back up the database, plugin directory, and applicable configuration; verify checksums and readability.
3. Record durable counts for customers, consent, consent history, conversation memory, decision evidence, and audit.
4. Confirm no production deployment authorization is implied by this guide.

## Migration

Activation or `plugins_loaded` invokes `Migrator::migrate()`. WordPress `dbDelta` creates `budly_commercial_memory` and `budly_conversation_contexts`, preserves existing tables, records migration 1.3.0 with a schema checksum, registers `commercial-memory-1.5.0.0`, updates the governed agent scopes, then updates the schema option.

Re-running the migration is safe: table creation is idempotent, configuration identity is version-keyed, and migration version 1.3.0 is unique.

## Verification

- Application 1.5.0, schema 1.3.0, rules bros-rules-1.5.0.0.
- Both new tables and all inherited tables exist.
- Inherited durable counts are unchanged.
- Exactly one active commercial-memory configuration exists for version 1.5.0.0.
- A consented test customer can create, supersede, correct, export, expire, and delete a governed object; a non-consented or other customer cannot read it.

Any failed table creation, configuration insertion, durable-count mismatch, consent regression, or audit failure blocks acceptance and requires restoration from backup.
