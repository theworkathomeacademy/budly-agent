# Budly v1.5 Release Manifest

Status: Implementation candidate

## Identity

| Field | Value |
|---|---|
| Application | 1.5.0 |
| Schema | 1.3.0 |
| Rules | bros-rules-1.5.0.0 |
| Base tag | budly-v1.4 |
| Base commit | 7b8c3afa09ce15fc7b2e10b4f9220bb837e54598 |
| Branch | release/budly-v1.5 |
| Release tag | budly-v1.5 (pending Project Owner acceptance and merge) |
| Production deployment | Prohibited |
| CI | GitHub Actions run 31034548881 passed |

## Governed components

- Ten allowlisted commercial-memory object types with bounded scalar values.
- Versioning, provenance, confidence, aging, supersession, invalidation, expiration, deletion, correction, export, consent, and audit controls.
- Structured conversation summaries without chain-of-thought.
- Deterministic commercial context with fixed keys and explicit memory references.
- Customer REST controls protected by verified server session, CSRF nonce, ownership, rate limiting, idempotency, consent, and audit.
- Administrator browser, filters, correction, invalidation, deletion, export, and audit inspection protected by WordPress capability and REST nonce.
- Additive schema 1.3.0 tables: `budly_commercial_memory` and `budly_conversation_contexts`.
- Governed rule configuration: `commercial-memory-1.5.0.0`; accepted recommendation and qualification rules remain unchanged.

## Exclusions

Native CRM, lead pipeline, opportunities, lifecycle, commerce attribution, revenue reporting, affiliate intelligence, semantic retrieval, vector databases, LLMs, autonomous reasoning, learning, marketing automation, workflow execution, and multi-agent coordination are absent.

## Build

Use `python scripts/build_plugin.py --output dist/budly-sales-agent-1.5.0.zip --source-commit <accepted-commit>`. The final commit, ZIP SHA-256, and tag target are recorded only after acceptance.
