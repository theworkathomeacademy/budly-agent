# Budly v1.5 Acceptance Report

Status: Staging accepted; Project Owner review and merge pending

## Static and automated evidence

| Check | Result |
|---|---|
| Automated tests | 149 passed, 0 failed, 0 skipped |
| Inherited tests | 123 passed |
| New v1.5 tests | 26 passed |
| Repository validation | Passed; 163 tracked files checked |
| Version consistency | Passed in automated suite |
| Deterministic build | Passed in automated suite; final accepted-commit hash pending |
| Migration contract | Passed in LocalWP: 1.2.0 to 1.3.0; explicit rerun was idempotent |
| Rollback contract | Passed: exact v1.4 files activated with additive tables dormant; exact v1.5 candidate restored |
| JavaScript validation | Passed in GitHub Actions run 31034548881 |
| PHP syntax validation | Passed for all plugin PHP files on PHP 8.2 in GitHub Actions run 31034548881 |
| CI | Passed, run 31034548881 |
| Authenticated v1.5 runtime | 28 passed, 0 failed using isolated synthetic customers |
| Live HTTPS negative paths | Passed: customer routes returned 401; administrator routes returned 403 without authorization |
| Local PHP validation | 41 files passed on LocalWP PHP 8.2.29 |
| Local JavaScript validation | 4 files passed |

## Staging environment and preservation

Acceptance ran on the non-production LocalWP site `budly-phase-3-runtime.local`: WordPress 7.0.2, PHP 8.2.29, MySQL 8.4.0, nginx 1.26.1, Twenty Twenty-Five, HTTPS trusted, database prefix `wp_`, and WP-Cron enabled. No production credentials, accounts, data, or deployment were used.

Before administrator recovery or migration, readable backups were created:

- Database: `pre-recovery-database.sql`, SHA-256 `7A954962E8942BFC4FF15DC7E00482BC697B3EDB7DD334529CBB52A4DDD3D9CD`.
- Installed v1.4 plugin: `pre-recovery-budly-plugin.zip`, SHA-256 `A26048085541E6B7CBD648A3C38FF13232179AA222523AE23E4E2755F8FA3609`.
- Local configuration: `wp-config.php.backup`, SHA-256 `7F007DAC9AC991CDB0006FB453875C332413D5BC978914046457B9584100DDA3`.

Native one-click administration did not establish a reusable secure cookie after the site URL was corrected from HTTP to HTTPS. A local-only temporary administrator was therefore created, used only in the connected HTTPS staging context, then had all sessions revoked and was deleted. The original administrator inventory was restored to `budly_runtime_admin`. No credential or password hash is retained in Git, release records, or the audit workspace.

## Migration and durable reconciliation

The exact candidate from source head `1a222afd1bf10b2bf235329c05246327a1f7938c` was built twice with identical SHA-256 `B93EF89D30EFCA0AC45448C2E6E6BBE0D6CA66C0D11023BE4A0040DAC0755E0C`, installed, and activated. The migration created the two additive v1.5 tables, recorded schema 1.3.0 once, and registered exactly one active commercial-memory configuration. Re-running the migrator produced no duplicate migration or configuration.

Inherited durable counts remained: customers 2, consent 3, consent history 30, sessions 111, conversation memory 13, decision evidence 23. The audit table increased from 1292 to 1294 only through expected fail-closed administrator-access evidence. Synthetic v1.5 acceptance records were removed after the suite.

## Runtime, rollback, and restoration

The authenticated runtime suite verified governed creation, bounded fields, invalid and sensitive-value rejection, read, cross-customer denial, versioned supersession, correction, structured conversation summaries, chain-of-thought rejection, deterministic context, export, administrator search/filtering, consent withdrawal, explicit reauthorization, confirmed deletion, and audit linkage: 28 passed, 0 failed.

Rollback restored and activated the preserved v1.4 application. Schema reported 1.2.0 while both additive v1.5 tables remained dormant and empty; inherited durable counts, Ask Budly, and the administrator page remained available. Restoration reinstalled the exact v1.5 files, returned schema to 1.3.0, created no duplicates, preserved durable counts, and restored the Ask Budly and commercial-memory administration interfaces without browser errors.

## Security acceptance

The candidate enforces server-derived customer identity, separate storage/use consent, bounded allowlists, CSRF nonces, WordPress administrator capability, rate limits, idempotency, cross-customer ownership, audit references, sensitive-content rejection, and value-minimized decision evidence. No chain-of-thought storage or free-form AI memory exists.

## Gates

Gates A-E: Pass. Gate F: Blocked. Production deployment did not occur and is not authorized.

## Remaining release work

- Run CI for the evidence-only closure commit and record the final candidate commit and reproducible ZIP hash in PR #6.
- Project Owner review, merge, annotated tag, and GitHub release remain pending.
