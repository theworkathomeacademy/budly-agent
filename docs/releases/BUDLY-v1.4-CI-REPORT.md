# Budly v1.4 CI Report

## Candidate local results

| Check | Result |
|---|---|
| Python automated tests | Pass: 123 |
| Repository policy | Pass |
| Version consistency | Pass |
| JavaScript syntax | Pass: 4 files |
| Deterministic build | Pass: identical SHA-256 |
| Manifest/checksum validation | Pass |
| PHP syntax | Pass: all 38 PHP files under PHP 8.2 |

GitHub Actions run `30541492617` passed on candidate head `095d144`. It installed controlled Python 3.11, Node 20, and PHP 8.2 runtimes, ran all 123 tests, validated 150 tracked files, parsed all PHP and JavaScript sources, reproduced the package, and verified its checksum.

The CI artifact `first.zip` has SHA-256 `06B9824C25E6D932001103F68E29DCA3FB3E6E575E7A0041D6363C13310E1BB9`. The hash differs from the local candidate solely because the manifest records a different exact source commit; each build is reproducible for its stated source identity.
