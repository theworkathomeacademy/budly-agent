# Budly v1.4 Traceability Matrix

| Requirement | Authority | Implementation | Evidence |
|---|---|---|---|
| CI on pull requests and main | v1.4 design | `.github/workflows/ci.yml` | Clean GitHub job |
| Release artifact workflow | v1.4 design | `.github/workflows/release.yml` | Tag/release job |
| Deterministic plugin ZIP | v1.4 design | `scripts/build_plugin.py` | Two hashes equal |
| Version and tag consistency | v1.4 design | `scripts/validate_versions.py` | Automated positive/negative tests |
| Repository and secret boundary | v1.4 design; Source of Truth | `scripts/validate_repository.py` | Automated positive/negative tests |
| PHP and JavaScript validation | v1.4 design | CI PHP 8.2 and Node 20 checks | CI report |
| Plugin structure and mascot | v1.4 design | repository validator and tests | Automated tests |
| Manifest and checksum | v1.4 design | builder and release workflow | Embedded JSON and `.sha256` |
| Migration safety | Build Authorization; Acceptance Suite | inherited migration contracts; no v1.4 schema delta | 123-test suite |
| Rollback safety | Release Plan | restore prior Git tag and package; no down-migration | rollback guide |
| Human-controlled release | Build Authorization; Release Plan | PR review and no automatic production deploy | workflow permissions and checklist |
| Documentation integrity | v1.4 design | required root and release documents | repository validator |
| No customer-facing expansion | v1.4 handoff | application behavior preserved | inherited regression suite |
| Runtime activation and staging | Acceptance Suite | exact ZIP installed in LocalWP | 15/15 staging matrix |
| Durable reconciliation | Build Authorization | before/after table counts | customers, consent, history, configurations and schema unchanged |
| Immutable rollback | Release Plan; ISR-001 | accepted R1 GitHub release asset | published hash and 44/44 file match |
| Restoration | Release Plan | exact v1.4 candidate reinstalled | 44/44 file match and critical smoke pass |

No v1.5, v1.6, or v1.7 functionality is included.
