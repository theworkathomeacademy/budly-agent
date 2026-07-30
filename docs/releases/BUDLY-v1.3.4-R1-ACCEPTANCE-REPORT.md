# Budly v1.3.4-R1 acceptance report

Status: candidate accepted for pull-request review; merge and tag verification remain pending.

Baseline evidence: 110 inherited automated tests passed before reconciliation. Post-change result: 113 passed, zero failed, zero skipped. All 36 packaged PHP files passed PHP 8.2.29 syntax validation.

The candidate built twice with byte-identical SHA-256 `6F002182E01D93A752B901AD9F44F47264E2F670BE7CB20CD00610A9D1CFA681` using source identifier `CANDIDATE`. This is pre-merge reproducibility evidence, not the final tagged package hash.

LocalWP staging passed 15 of 15 bounded subtests: HTTPS home and Ask Budly rendering, dedicated template, hero, governed endpoint configuration, Secure Memory loading, legacy-recall exclusion, both asset loads and exact sizes, CSS/JS loading, anonymous administration denial, anonymous session denial, application version, and absence of a candidate-time PHP fatal or parse error.

Rollback restored the verified 40-file pre-R1 staging tree exactly and returned HTTP 200. Reinstallation reproduced the 43-file candidate tree exactly and returned HTTP 200.

Gates A–E remain passing based on the inherited acceptance plus R1 regression and staging evidence. Gate F remains blocked. Production deployment is prohibited and did not occur.
