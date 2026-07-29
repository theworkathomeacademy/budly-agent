# Budly v1.3.4 release manifest

Status: staging implementation candidate; production prohibited  
Application version: `1.3.4`  
Schema version: `1.2.0`  
Baseline commit: `493bedb` (`v1.3.0` accepted application baseline)  
Branch: `release/budly-v1.3.4`

## Governing documents

- FL-001 BROS Foundation Library v1.0
- TB-001 BROS Technical Blueprint v1.0
- BA-001 BROS Build Authorization v1.0
- STS-001 Source of Truth Specification v1.0
- CRM-001 Native CRM Architecture v1.0
- DB-001 Database & Record Structures v1.0
- IA-001 Budly Intelligence Architecture v1.0
- KA-001 Knowledge Architecture v1.0
- PRA-001 Prompt, Reasoning & Recommendation Architecture v1.0
- ADS-001 Administration & Dashboard Specification v1.0
- ATS-001 Acceptance Test Suite v1.0
- RP-001 Version 1.0 Release Plan v1.0

The Google Drive Program Index and Technical Blueprint were verified as ratified on 2026-07-29. No separate ratified v1.3.4 requirements document or repository crosswalk was found. This release therefore implements only the non-ambiguous bridge authorized by the implementation handoff and directly supported by the ratified Technical Blueprint.

## Included requirements

- Consistent v1.3.4 application and v1.2.0 schema diagnostics
- Versioned and validated qualification, recommendation, catalog, journey, escalation, consent, and retention configuration
- Governed qualification, recommendation, no-match, and escalation evidence
- Approved-catalog filtering with explicit exclusion reasons
- Concise reasoning inputs and outcomes without model chain-of-thought
- Decision-to-audit correlation
- Additive WordPress decision/configuration tables
- Protected administrator decision/configuration visibility
- Additive SQLite decision/configuration persistence for the deterministic application core

## Deferred

- Full BROS v1.7 CRM, lifecycle, workflow, intelligence, reporting, and dashboard suite
- Commercial rules not yet ratified
- Live staging WordPress/MySQL migration execution and reconciliation
- Production Gate F work and production deployment

## Migration identifiers

- WordPress/MySQL secure-memory schema `1.2.0`
- SQLite application schema `1.2.0`
- Rules package `bros-rules-1.3.4.1`

## Rollback

Disable v1.3.4, restore the accepted v1.3.0 plugin artifact, and retain the additive tables unless an authorized database restore is required. See `BUDLY-v1.3.4-ROLLBACK-GUIDE.md`.

## Tests

Baseline repository evidence: 96 passed, 0 failed, 0 skipped. The handoff stated 100 tests, but neither the accepted baseline manifest nor executable baseline suite supports that count. Final v1.3.4 results are recorded in the acceptance report.

## Known limitations

The new WordPress schema and protected read API are source-tested but not executed against live staging MySQL in this workspace. Gate F remains blocked. No production authorization is implied.
