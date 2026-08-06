# Budly v1.6 Rollback Guide

Deactivate v1.6, restore the exact `budly-v1.5` package, and activate it. Leave additive v1.6 tables dormant to avoid financial-evidence loss; restore the pre-migration database backup only when exact database rollback is required and approved. Verify application `1.5.0`, schema behavior documented for v1.5, customer/consent/session/memory/decision records, Ask Budly, administration, and checksums. Restoration reinstalls the exact v1.6 candidate, reruns the idempotent migration, and verifies no duplicate events/configurations or durable-data loss.
