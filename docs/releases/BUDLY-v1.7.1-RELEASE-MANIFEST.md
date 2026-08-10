# BUDLY v1.7.1 RELEASE MANIFEST

**Release:** Production Stabilization Patch  
**Application:** 1.7.1  
**Schema:** 1.5.0 (unchanged; no migration)  
**Rules:** `bros-rules-1.5.0.0` (unchanged)  
**Commerce configuration:** `commerce-attribution-1.6.0.0` (unchanged)  
**Starting source:** `ae9ed56650adc50d6b22d11d643fc5631d80cb71`  
**Branch:** `release/budly-v1.7.1`  
**Candidate source:** `9c5a21fe3229ff338d45e169792ee1d66458eb26`
**Candidate ZIP:** `budly-sales-agent-1.7.1.zip`
**Candidate SHA-256:** `509C09E5E5FCD5C6A98C22E502D35BB7C7A561402D27837A28B16B7EEB629248`
**Status:** Implementation, deterministic packaging, reconstructed LocalWP acceptance, rollback, and restoration passed; Project Owner review required.

## Patch scope

- Fail-closed verified-customer resolution for v1.7 conversation and lifecycle routes.
- Database-derived privacy-minimized conversation and lifecycle aggregates.
- Canonical forward lifecycle transition enforcement.
- Bounded PHP adaptive-question journey and confidence parity.
- Formal preservation and executable verification of the v1.7 Bootstrap loaders.
- No database, rules, commerce-configuration, visual, journey, recommendation, or checkout redesign.

The deterministic build manifest embedded in the candidate ZIP is the authoritative file inventory and source-commit record.

## Acceptance summary

- Automated: 179 passed, 0 failed, 0 skipped.
- Runtime: 67/67 passed before rollback and 67/67 passed after restoration.
- PHP: 47 files linted; JavaScript: 4 files syntax-validated.
- Repository: 200 tracked files validated.
- Rollback baseline: deterministic `ae9ed566` package SHA-256 `02C319EE2925661AE3744370247D1744EDD0AEC9B514FB4B9AE2445EBB5E06CD`.
- No schema migration, production access, merge, tag, release, or deployment occurred.
