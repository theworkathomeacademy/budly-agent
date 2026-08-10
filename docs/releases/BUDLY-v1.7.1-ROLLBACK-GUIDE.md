# BUDLY v1.7.1 ROLLBACK AND RESTORATION GUIDE

The original `budly-v1.7` artifact lacks the required Bootstrap loaders and must not be treated as a safe operational rollback by itself. The minimum operational rollback reference is current main `ae9ed56650adc50d6b22d11d643fc5631d80cb71`, represented by a verified package that includes the loader correction.

Before any environment change:

1. Record application/schema/rules/configuration versions and active package hash.
2. Back up and verify database, plugin tree, and relevant configuration.
3. Preserve additive schema 1.5.0 data; this patch has no migration or destructive rollback step.

Rollback rehearsal installs the verified current-main package, confirms module loading, Ask Budly, Secure Memory, commerce integration, schema 1.5.0 readability, and fail-closed protected routes. Restoration reinstalls the exact v1.7.1 candidate and verifies the same durable counts and critical checks. Production use requires separate authorization.
