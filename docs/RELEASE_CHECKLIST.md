# Budly Release Checklist

- [ ] Release branch begins at the accepted prior tag on current `origin/main`.
- [ ] Scope traces to ratified architecture and the version handoff.
- [ ] Application, schema, rules, changelog, and tag versions are consistent.
- [ ] Repository validation, full tests, PHP lint, and JavaScript checks pass.
- [ ] Migrations and rollback are tested without data loss.
- [ ] Two clean builds are byte-identical.
- [ ] ZIP root, manifest, file hashes, source commit, and checksum validate.
- [ ] Release ZIP contains no development files, secrets, data, or nested archives.
- [ ] Acceptance report and architecture audit are complete.
- [ ] Gates A-E pass; Gate F is accurately reported.
- [ ] PR is reviewed and merged by authorized human control.
- [ ] Annotated tag targets the accepted merge commit.
- [ ] Production deployment did not occur without separate authorization.
