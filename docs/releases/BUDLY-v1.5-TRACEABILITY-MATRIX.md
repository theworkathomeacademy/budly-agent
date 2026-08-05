# Budly v1.5 Commercial Memory Foundation Traceability Matrix

Status: Implementation baseline  
Baseline: annotated tag `budly-v1.4` / `7b8c3afa09ce15fc7b2e10b4f9220bb837e54598`  
Target: application `1.5.0`, schema `1.3.0`, rules `bros-rules-1.5.0.0`

This matrix is the required pre-code comparison between the authorized v1.5 handoff, the ratified BROS authorities, Secure Memory Assets 1–5, and the accepted v1.4 implementation. Status is updated as implementation evidence becomes available.

## Authority reconciliation

| Authority | v1.5 constraint | Reconciliation |
|---|---|---|
| Founding Laws and BCAM | Education, trust, consent, transparency, customer control, no architectural drift | Governs all customer-facing and memory behavior |
| BROS Foundation Library and Constitution | Customer information is privileged; deterministic policy and human authority prevail | Commercial memory is structured, minimal, reviewable, and never autonomous |
| BROS Technical Blueprint | Relational system of record, modular services, provenance, typed results, fail-closed policy | Extend the existing WordPress modular monolith; no platform rewrite |
| BROS Database & Record Structure Specification | UUID identities, provenance, timestamps, immutable audit, controlled migrations | Add versioned commercial-memory and conversation-context records through schema `1.3.0` |
| BROS Intelligence Architecture | Approved inputs, evidence, confidence, explainability, no hidden reasoning | Context builder returns a deterministic payload only; no chain-of-thought |
| BROS Administration Specification | Role-based access, search/filter/pagination, auditability, actionable review | Add capability-protected memory review controls with bounded results |
| Commercial Constitution and Revenue Operating Model | Customer-fit signals may support service and recommendations without pressure or fabricated knowledge | Limit types to the ten authorized commercial-memory categories |
| ISR-001 | Preserve accepted Secure Memory and v1.4 engineering controls | Extend rather than rebuild identity, consent, session, audit, and packaging foundations |
| Historical v1.5 Secure Memory package | Verified session ownership, neutral verification, consent on every access, structured fields, deletion, abuse controls | Existing v1.4 controls are preserved and reused; new objects remain session-bound |
| Hero Offer Architecture | Program Index marks this authority in progress, not ratified | No Hero Offer behavior is implemented in v1.5 |

## Requirement and gap matrix

| ID | Authorized requirement | v1.4 evidence | Gap | v1.5 action | Acceptance evidence |
|---|---|---|---|---|---|
| CM-01 | Ten governed commercial-memory types | Structured conversation summaries and preferences exist | No typed commercial object model | Add strict type allowlist and value schemas | Type-policy and rejection tests |
| CM-02 | UUID, customer, namespace, type, value, confidence, source, timestamp, consent, expiration, audit reference | Existing memory has UUID-like ID, ownership, namespace, provenance, expiry | Confidence, version lineage, explicit consent state and audit reference are not first-class | Add schema `1.3.0` commercial-memory table | Migration and serialization tests |
| CM-03 | No free-form AI memory | Summary allowlist and sensitive-pattern rejection exist | Commercial values need dedicated bounded schemas | Reject unknown types, keys, nested arbitrary content, sensitive content, and hidden reasoning | Negative payload corpus |
| MG-01 | Versioning, provenance, confidence and aging | Summary provenance and timestamps exist | No commercial version chain or deterministic aging | Add version, source evidence, confidence basis, observed/effective timestamps and deterministic age state | Version/aging tests |
| MG-02 | Supersession and invalidation | Corrections overwrite current summary | No immutable predecessor relationship | Insert a new version and mark prior object superseded/invalidated | Supersession tests |
| MG-03 | Expiration, deletion, correction and export | Existing summary expiry/delete/correct/export | Not available for commercial objects | Implement customer-owned operations with tombstones and minimal audit | Expiry/delete/correct/export tests |
| MG-04 | Consent enforcement and mutation audit | Independent storage/use consents and append-only audit exist | Commercial access/mutation events absent | Reuse consent service; audit every read and mutation | Consent-withdrawal and audit tests |
| CC-01 | Deterministic commercial context | Existing memory-use context binds session/conversation/purpose | No reusable commercial recommendation payload | Add a context builder with fixed keys, ordering, limits and exclusions | Determinism tests |
| CC-02 | Verified profile, summary, memory, objective, consent, journey, exclusions, preferences | Data exists across profile, memory and decision inputs | No single governed assembly boundary | Compose only server-resolved and allowlisted evidence | Cross-customer and no-hidden-reasoning tests |
| CX-01 | Structured conversation summaries | Existing summary schema covers topic, questions, corrections and next step | Missing products, recommendations, decisions, escalations and outcome fields | Add a dedicated structured conversation-context schema | Conversation-context validation tests |
| AD-01 | Browser, search, filters and expiration review | Health, audit and decision admin views exist | No governed commercial-memory review | Add capability-protected paginated query and filters | Admin authorization/filter tests |
| AD-02 | Delete, correct, export and audit inspection | Session revocation and audit controls exist | No commercial-memory admin mutations | Add nonce-protected operations with reason and audit attribution | Admin CSRF/role/audit tests |
| API-01 | Read, update, correct, delete and export | Equivalent summary routes exist | No commercial-memory API contract | Add versioned REST routes using verified session ownership | API contract tests |
| API-02 | Authorize and withdraw consent | Generic consent route exists | No explicit commercial-memory convenience contract | Add scoped consent endpoints backed by existing consent service | Immediate-withdrawal tests |
| API-03 | Nonce, role/actor authorization, rate limiting and audit | Session CSRF, admin nonce/capability, global request security and audit exist | New routes require explicit enforcement | Reuse centralized guards; customer role is verified-session actor, administrator role is WP capability | Unauthorized/rate-limit/audit tests |
| DB-01 | Idempotent schema `1.2.0` to `1.3.0` | dbDelta framework and migration ledger exist | New tables/indexes/version record required | Add additive tables and schema record; preserve all existing rows | Repeat-migration and data-preservation tests |
| DB-02 | Rollback without customer/consent/memory loss | v1.4 rollback contract exists | New-table rollback policy absent | Roll back application files; retain additive governed data dormant for forward recovery | Rollback contract tests |
| REL-01 | Application/rules/package release | v1.4 deterministic pipeline exists | Versions and v1.5 release records absent | Update version sources, rules configuration, build metadata and release docs | Repository/version/package tests |
| SCOPE-01 | Exclude CRM, lifecycle, attribution, LLMs, automation and agents | No such v1.5 code exists | Prevent scope leakage | Tests and architecture audit reject prohibited modules/claims | Scope regression test |

## Authorization interpretation

Customer endpoints are “role protected” through the verified-customer actor role established by the server-side session; they never trust a browser-supplied customer identifier. Administrator endpoints require the WordPress `manage_options` capability and a valid REST nonce. This preserves the historical Secure Memory authority while satisfying the v1.5 actor-role requirement.

## Initial risks

- Schema rollback must not drop additive tables or destroy records; rollback disables v1.5 behavior by restoring v1.4 code while retaining data for forward recovery.
- Administrative browsing is bounded, reason-aware, capability-protected, and audited; it is not a casual bulk customer-data browser.
- Confidence represents explicit evidence strength under deterministic rules. It is not predictive scoring.
- “Affiliate interest” and “membership interest” are customer-stated interests only; no affiliate intelligence, approval, lifecycle transition, or marketing automation is authorized.
