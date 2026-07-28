# Phase 3 database schema and migration recovery

Schema version: `1.1.0`. WordPress prefixes every logical name with the active site prefix.

| Logical table | Purpose | Important controls |
|---|---|---|
| `budly_customers` | Canonical identity/profile anchor | Unique public ID and email hash |
| `budly_preferences` | Structured profile/preferences | Unique customer/key; classification |
| `budly_conversation_memory` | Structured summaries | Ownership, namespace, classification, consent reference, provenance, content hash, retention metadata, soft deletion |
| `budly_consent` | Current consent | Unique customer/type |
| `budly_consent_history` | Append-only decisions | Version/source/actor/time |
| `budly_verification_requests` | Passwordless requests | Hashed code, attempt/lock/use/expiry and email/IP indexes |
| `budly_sessions` | Server-side sessions | Unique HMAC token hash, idle/absolute expiry, revocation indexes |
| `budly_audit` | Append-only security/admin events | Event/actor/severity indexes; scrubbed metadata |
| `budly_schema_migrations` | Applied migration checksum/status | Unique version |
| `budly_agents` | Registered agents/scopes/namespaces | Unique agent ID; default sales agent seed |
| `budly_memory_contexts` | Current-context use decisions | Unique session/conversation/agent; purpose and expiry |
| `budly_idempotency` | Mutation replay control | Unique customer/endpoint/key; request hash and original response |

Migration is repeatable through `dbDelta`. New Phase 5 metadata columns are nullable for legacy-row upgrade safety; all new records populate them. No legacy tracking row is promoted to authoritative identity, consent, or memory automatically.

Recovery procedure:

1. Back up the WordPress database and current plugin directory before activation.
2. Activate in staging and confirm `budly_secure_memory_schema_version=1.1.0` and the migration record checksum.
3. If migration fails, disable version 1.3.0 without deleting tables, capture the database error, and restore the pre-migration database backup if any partial DDL is unacceptable.
4. Do not manually mark a migration applied.
5. Correct the cause and rerun on staging before production.
