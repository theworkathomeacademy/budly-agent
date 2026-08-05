# Contributing

Create work from current `origin/main` on `feature/*`, `fix/*`, `hotfix/*`, or `release/*`. Never develop directly on `main`.

Before requesting review, run:

```text
python scripts/validate_repository.py
python scripts/validate_versions.py
python -m unittest discover -s tests -v
```

Also lint every plugin PHP file with PHP 8.2+, check every JavaScript file with Node 20+, build twice with `scripts/build_plugin.py`, and verify byte-identical ZIPs. A release requires traceability, migration and rollback evidence, acceptance results, and human approval. Production deployment is outside this workflow.
