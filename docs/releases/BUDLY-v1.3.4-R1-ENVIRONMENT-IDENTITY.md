# Budly v1.3.4-R1 environment identity

| Environment | Evidence | Result |
|---|---|---|
| LocalWP `budly-phase-3-runtime` | 40 plugin files; internal version `1.3.4`; 28 exact files against both `4b46174` and `f964f19`; 12 modified paths; zero exact files against the Drive package | Neither historical artifact; a staging-derived Git-lineage workspace |
| Production | No authorized production inspection endpoint was available | Unverified; no access attempted and no changes made |

The LocalWP differences are confined to the entry point, two customer scripts, and nine Secure Memory/decision modules. This environment must not be used as a source baseline. R1 source remains the release branch from `4b46174`.

For R1 acceptance, the original 40-file staging tree was backed up and hash-verified, the 43-file candidate was installed, 15 staging subtests passed, rollback reproduced the 40-file backup exactly, and candidate reinstallation reproduced the 43-file Git tree exactly.
