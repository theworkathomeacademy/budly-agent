# Development Workflow

1. Fetch `origin/main` and accepted tags.
2. Create the approved version-bounded branch from the accepted baseline.
3. Implement only the authorized release scope in focused commits.
4. Run repository and version validators, the full test suite, PHP and JavaScript checks, migration and rollback tests, and two deterministic builds.
5. Record architecture traceability, packaging, acceptance, and rollback evidence.
6. Push the branch and open a reviewable pull request.
7. Merge only after acceptance and required human authorization.
8. Create and verify the annotated release tag, then publish the reproducible Git-built package if authorized.

Historical branches, tags, packages, and commits remain immutable. Production deployment is never part of this workflow unless separately authorized.
