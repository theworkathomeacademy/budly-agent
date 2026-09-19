# Budly v1.8.0 Release Candidate Rollback

Production execution is not authorized by this document.

## Feature rollback

Set `BUDLY_CONVERSATIONAL_RUNTIME_ENABLED` to `false`. The existing deterministic guided Budly remains available. Durable memory stays disabled. No database rollback is required.

## Package rollback

Before installation, capture the installed plugin archive/tree, application version, and SHA-256 according to the existing Budly release process. If rollback criteria are met, disable the conversational feature, restore the captured known-good v1.7.1 plugin package, verify the Ask Budly page and guided flow, and re-run the bounded smoke checks. The Python runtime may remain stopped; it owns no Slice 1 customer database state.

Rollback triggers include invalid response validation, deterministic-authority conflict, repeated runtime failure, unacceptable latency, cross-session context leakage, secret exposure, or loss of the guided fallback.
