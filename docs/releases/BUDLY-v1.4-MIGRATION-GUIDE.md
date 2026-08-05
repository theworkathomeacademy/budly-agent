# Budly v1.4 Migration Guide

v1.4 changes application metadata from 1.3.4 to 1.4.0 and introduces no database or rules migration. Schema remains 1.2.0 and rules remain `bros-rules-1.3.4.1`.

For an authorized non-production environment:

1. Back up the plugin directory and database.
2. Verify the installed source identity.
3. Install the Git-built v1.4 ZIP and activate it.
4. Confirm WordPress reports application 1.4.0.
5. Confirm schema remains 1.2.0 and existing migration/configuration counts do not change.
6. Repeat activation and confirm idempotency.
7. Run the inherited staging smoke suite.

No destructive migration or production execution is authorized.

## Staging result

Activation preserved schema 1.2.0, both schema-migration rows, seven governed configurations, two customers, three consent rows, thirty consent-history rows, and all preexisting memory, decision, and audit evidence. No v1.4 migration ran. Acceptance added only labeled synthetic verification/session/memory/decision/idempotency/audit records; these were retained as test evidence.
