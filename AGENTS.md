# Budly Repository Instructions

## Phase 3: Secure Returning-Customer Memory

Before modifying the secure returning-customer memory system, read:

1. `docs/budly-secure-memory/README.md`
2. `docs/budly-secure-memory/asset-1-secure-memory-architecture.md`
3. `docs/budly-secure-memory/asset-2-threat-model.md`
4. `docs/budly-secure-memory/asset-3-customer-experience.md`
5. `docs/budly-secure-memory/asset-5-identity-memory-api.md`
6. `docs/budly-secure-memory/asset-4-codex-build-command.md`

These documents are authoritative.

The existing version 1.2.0 implementation is an incomplete MVP and may not override the approved specifications.

## Implementation Rules

- Do not invent requirements when the approved documents address the issue.
- Do not silently weaken security or consent requirements.
- Do not treat browser-provided consent as authoritative.
- Do not allow unauthenticated profile or memory modification.
- Do not begin Phase 4 until Phase 3 acceptance is complete.
- Record any unavoidable deviation in the traceability matrix.
- Add tests for every corrected vulnerability and authorization boundary.

## First Required Action

Before coding, compare the current repository against Assets 1–5 and create a requirements traceability matrix.

Use Asset 4 as the implementation command after completing that comparison.
