# Budly v1.6 Migration Guide

Activation advances schema `1.3.0` to `1.4.0` additively through `dbDelta`, creates the four prefixed commerce tables, records the migration checksum, registers `commerce-attribution-1.6.0.0`, and retains `bros-rules-1.5.0.0`. Before activation, back up the database, plugin, and configuration and record durable counts. Run activation, verify all tables/indexes/configuration, rerun migration to prove idempotency, and reconcile counts. No customer, consent, session, memory, decision, audit, or existing configuration table is destructively altered.
