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
| PHP syntax | Pending GitHub PHP 8.2 job; PHP is not installed on the audit workstation |

The GitHub workflow installs controlled Python 3.11, Node 20, and PHP 8.2 runtimes. CI is blocking: the PR is not acceptance-complete until all remote jobs pass.
