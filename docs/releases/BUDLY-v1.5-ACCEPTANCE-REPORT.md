# Budly v1.5 Acceptance Report

Status: Candidate evidence; staging runtime acceptance and Project Owner review pending

## Static and automated evidence

| Check | Result |
|---|---|
| Automated tests | 149 passed, 0 failed, 0 skipped |
| Inherited tests | 123 passed |
| New v1.5 tests | 26 passed |
| Repository validation | Passed; 163 tracked files checked |
| Version consistency | Passed in automated suite |
| Deterministic build | Passed in automated suite; final accepted-commit hash pending |
| Migration contract | Additive/idempotent source contract passed; WordPress staging rehearsal pending |
| Rollback contract | Non-destructive contract passed; staging rehearsal pending |
| JavaScript validation | Passed in GitHub Actions run 31034548881 |
| PHP syntax validation | Passed for all plugin PHP files on PHP 8.2 in GitHub Actions run 31034548881 |
| CI | Passed, run 31034548881 |

## Security acceptance

The candidate enforces server-derived customer identity, separate storage/use consent, bounded allowlists, CSRF nonces, WordPress administrator capability, rate limits, idempotency, cross-customer ownership, audit references, sensitive-content rejection, and value-minimized decision evidence. No chain-of-thought storage or free-form AI memory exists.

## Gates

Gates A-E remain candidate Pass subject to final CI and staging migration/rollback acceptance. Gate F remains Blocked. Production deployment did not occur and is not authorized.

## Remaining acceptance work

- Rehearse schema 1.2.0 to 1.3.0 migration, negative authorization tests, rollback to v1.4, and restoration to v1.5 in authorized staging.
- Record final commit, ZIP checksum, CI run, PR, durable counts, and staging evidence.
