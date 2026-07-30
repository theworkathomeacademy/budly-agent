# Budly v1.4 Rollback Guide

Rollback target is the immutable `budly-v1.3.4-r1` tag at `776f4018da7e0b01a05dad4682751a4d40e85a7d` and its checksum-verified package.

In an authorized non-production environment:

1. Preserve the failing plugin and logs as evidence.
2. Deactivate v1.4.
3. Restore the backed-up v1.3.4-R1 plugin directory or verified release ZIP.
4. Reactivate and verify application 1.3.4, schema 1.2.0, and rules `bros-rules-1.3.4.1`.
5. Verify customer, consent, memory, audit, and configuration records remain intact.
6. Run inherited staging smoke tests.

No database down-migration is needed because v1.4 adds no schema. Restore the database backup only if independent corruption is detected. Production rollback is not authorized by this release.
