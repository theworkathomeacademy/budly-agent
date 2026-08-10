# BUDLY v1.7.1 ROLLBACK AND RESTORATION GUIDE

The original `budly-v1.7` artifact lacks the required Bootstrap loaders and must not be treated as a safe operational rollback by itself. The minimum operational rollback reference is current main `ae9ed56650adc50d6b22d11d643fc5631d80cb71`, represented by a verified package that includes the loader correction.

Before any environment change:

1. Record application/schema/rules/configuration versions and active package hash.
2. Back up and verify database, plugin tree, and relevant configuration.
3. Preserve additive schema 1.5.0 data; this patch has no migration or destructive rollback step.

The LocalWP rehearsal used a deterministic current-main package built from `ae9ed56650adc50d6b22d11d643fc5631d80cb71` (SHA-256 `02C319EE2925661AE3744370247D1744EDD0AEC9B514FB4B9AE2445EBB5E06CD`). Rollback completed in 17.71 seconds with application 1.7.0, schema 1.5.0, Ask Budly HTTP 200, Bootstrap module loading, and durable data intact.

Restoration reinstalled the exact v1.7.1 candidate SHA-256 `509C09E5E5FCD5C6A98C22E502D35BB7C7A561402D27837A28B16B7EEB629248` in 11.79 seconds. Application 1.7.1/schema 1.5.0, Ask Budly HTTP 200, and 67/67 executable WordPress/MySQL checks passed after restoration. Production use requires separate authorization.
