# Budly v1.5 Rollback Guide

## Target

Rollback target: immutable `budly-v1.4` at `7b8c3afa09ce15fc7b2e10b4f9220bb837e54598`.

## Procedure

1. Record the v1.5 plugin hash, schema option, table inventory, configuration versions, and durable counts.
2. Back up the database and plugin directory and verify both backups.
3. Deactivate v1.5 and restore the reproducible v1.4 package.
4. Activate v1.4. Its idempotent migrator restores the reported schema option to 1.2.0 without dropping additive v1.5 tables.
5. Verify activation, inherited tables, consent, legacy memory, decisions, audit, page rendering, admin routes, and the complete v1.4 regression set.
6. Confirm v1.5 endpoints and code are inactive.

## Data policy

Do not drop the two additive v1.5 tables during application rollback. Retaining them prevents commercial-memory loss and permits a reviewed forward restore. If removal is separately authorized, archive and checksum the tables first; destructive rollback is not part of v1.5.

Rollback fails if v1.4 cannot activate, an inherited durable count changes, consent becomes unreadable, or any accepted v1.4 test fails. Restore the verified backup and stop.

## Staging rehearsal result

On 2026-08-06 the exact preserved v1.4 plugin files were activated successfully. The schema option returned to 1.2.0, the additive v1.5 tables remained dormant and empty, inherited durable data stayed readable, and the customer and administrator pages loaded. Restoring the exact v1.5 candidate returned schema 1.3.0 without duplicate migrations, configurations, or data loss. Result: Pass.
