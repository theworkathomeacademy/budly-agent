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

## Rehearsal result

The GitHub release asset `budly-sales-agent-1.3.4-R1.zip` was verified as SHA-256 `DED5F0B89470B98AA696160C1C6F334CF224080A9EAC30B8402B1E336BDCF951`. Deactivation, installation, and activation completed in 4.460 seconds. The installed tree matched all 44 release files exactly. Application 1.3.4 loaded, schema 1.2.0 and all durable counts remained readable, Ask Budly returned HTTP 200, Secure Memory and decision evidence remained available, and admin authorization returned 200/403 for administrator/nonadministrator as designed.

The exact v1.4 candidate was then restored in 5.012 seconds. Its installed tree matched all 44 candidate files exactly and critical browser/runtime smoke tests passed.
