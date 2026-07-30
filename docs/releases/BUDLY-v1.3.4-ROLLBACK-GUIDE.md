# Budly v1.3.4 rollback guide

Rollback is recovery-oriented because MySQL `dbDelta` is forward-only.

1. Disable v1.3.4 in staging.
2. Preserve database and application logs.
3. Restore the immutable v1.3.0 accepted plugin ZIP whose recorded SHA-256 is `569299c79e54e53093d1b172d7f35e7332896804a1e56a550fa4e0679f473b0d`.
4. Leave the additive `budly_rule_configurations` and `budly_decision_evidence` tables in place; v1.3.0 does not reference them.
5. Confirm schema compatibility, all 24 secure-memory REST paths, secure sessions, consent, memory, and admin health.
6. If partial DDL or data integrity is unacceptable, restore the pre-migration staging database backup and verify the `1.1.0` schema plus reconciliation counts.
7. Do not manually edit migration records and do not drop tables before a verified backup.

SQLite recovery: stop the application, preserve the v1.3.4 database for evidence, restore the pre-migration database copy, and run v1.3.0 code. The additive tables do not prevent v1.3.0 reads.

Rollback acceptance requires the original 96-test suite to pass and Gates A-E controls to remain operational. Production rollback is outside this staging-only package.

The final writer is code-only. Plugin rollback disables its write route; appended decision and audit evidence remains dormant and no reverse DDL is required.
