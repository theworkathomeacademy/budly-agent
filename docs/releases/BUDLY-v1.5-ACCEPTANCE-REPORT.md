# Budly v1.5 Acceptance Report

Status: Candidate evidence; staging runtime acceptance and Project Owner review pending

## Static and automated evidence

| Check | Result |
|---|---|
| Automated tests | 149 passed, 0 failed, 0 skipped |
| Inherited tests | 123 passed |
| New v1.5 tests | 26 passed |
| Repository validation | Passed before final staging; rerun required on final commit |
| Version consistency | Passed in automated suite |
| Deterministic build | Passed in automated suite; final accepted-commit hash pending |
| Migration contract | Additive/idempotent source contract passed; WordPress staging rehearsal pending |
| Rollback contract | Non-destructive contract passed; staging rehearsal pending |
| JavaScript validation | Pending final validation |
| PHP syntax validation | Pending final validation with an available PHP CLI runtime |

## Security acceptance

The candidate enforces server-derived customer identity, separate storage/use consent, bounded allowlists, CSRF nonces, WordPress administrator capability, rate limits, idempotency, cross-customer ownership, audit references, sensitive-content rejection, and value-minimized decision evidence. No chain-of-thought storage or free-form AI memory exists.

## Gates

Gates A-E remain candidate Pass subject to final CI and staging migration/rollback acceptance. Gate F remains Blocked. Production deployment did not occur and is not authorized.

## Remaining acceptance work

- Run final PHP/JavaScript/repository validation and two independent builds from the committed candidate.
- Rehearse schema 1.2.0 to 1.3.0 migration, negative authorization tests, rollback to v1.4, and restoration to v1.5 in authorized staging.
- Record final commit, ZIP checksum, CI run, PR, durable counts, and staging evidence.
