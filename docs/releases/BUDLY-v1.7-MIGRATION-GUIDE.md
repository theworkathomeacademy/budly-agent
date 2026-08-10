# BUDLY v1.7 MIGRATION GUIDE

## Overview
Budly v1.7 introduces Schema 1.5.0, adding four additive tables for Conversation State Machine, Pattern Execution History, Relationship Health, and Member Journey tracking.

## Applied Migration Sequence
1. Standard WordPress plugin activation invokes `Budly\SecureMemory\Database\Migrator::migrate()`.
2. Schema version is checked against `Config::SCHEMA_VERSION` (`1.5.0`).
3. If upgrading from Schema 1.4.0, `dbDelta()` applies the 4 new additive tables (`budly_conversation_state`, `budly_conversation_pattern_history`, `budly_relationship_health`, `budly_member_journey`).
4. Table verification confirms presence of all 24 prefixed tables.
5. Migration record is inserted into `budly_schema_migrations`.
6. `budly_secure_memory_schema_version` option is updated to `1.5.0`.

## Backward Compatibility & Idempotency
- All schema additions are strictly additive.
- Re-running the migration on an already upgraded instance is a verified no-op.
- Existing v1.6 commerce events and v1.5 secure memory records remain untouched and fully accessible.
