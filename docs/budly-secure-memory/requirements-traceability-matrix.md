# Phase 3 Requirements Traceability Matrix

Baseline: approved Assets 1–5, version 1.0  
Compared implementation: deployed/local Budly Sales Agent 1.2.0  
Assessment date: 2026-07-21

## Status definitions

- **Implemented**: behavior is present and consistent with the approved requirement.
- **Partially Implemented**: a meaningful subset exists, but the requirement is not complete.
- **Missing**: no conforming implementation exists.
- **Implemented Incorrectly**: code exists but conflicts with the approved security or architecture rule.
- **Deferred**: intentionally outside Version 1 or blocked by a documented external dependency.

Static source-marker tests do not by themselves qualify a security boundary as implemented.

## Current implementation overlay — Phase 5 checkpoint

This overlay supersedes the original 1.2.0 baseline status wherever the same requirement appears below. WordPress/MySQL runtime claims remain **Partially Implemented** until executed in the target runtime.

| Requirement | Status | Current implementation evidence | Remaining evidence |
|---|---|---|---|
| Verified identity/profile read | Implemented | `GET /identity`, `GET /profile`; customer resolved only from `SessionGuard` | WordPress REST integration |
| Allowlisted profile update | Implemented | `ProfileService::FIELDS`, validation, CSRF, storage consent | WordPress/MySQL integration |
| Structured preference read/update | Implemented | `GET/PATCH /preferences`, explicit three-field allowlist, storage consent | WordPress/MySQL integration |
| Customer-visible memory preview | Implemented | `GET /memory/preview`; classification query and response allowlists | Runtime restricted-field test |
| Conversation-scoped memory-use authorization | Implemented | `budly_memory_contexts`; session/customer/agent/conversation/purpose/expiry binding | Runtime transition test |
| Start Fresh | Implemented | Context becomes `approved=0,start_fresh=1`; stored memory and marketing consent unchanged | Runtime transition test |
| Shared and agent namespace retrieval | Implemented | Session ownership, current consent/context, registered-agent scope and namespace checks | Runtime cross-agent test |
| Structured summary storage | Implemented | `POST /memory/summary`; schema and sensitive-content validation; consent reference | Runtime database test |
| Summary provenance | Implemented | Server-built source, agent, conversation, session reference, schema, timestamp and correction flag | Runtime serialization test |
| Memory correction | Implemented | `PATCH /memory/{memory_id}`; customer-scoped ownership and active storage consent | Runtime cross-customer test |
| Selective deletion | Implemented | `DELETE /memory/{memory_id}`; explicit confirmation and customer-scoped de-identification | Runtime deletion test |
| Delete all memory | Implemented | Transactional profile/preference/context/memory removal and revoke-all sessions | Runtime rollback/revocation test |
| Customer data export | Implemented | `GET /memory/export`; self-only, customer-visible records and allowlisted provenance | Runtime privacy test |
| Duplicate/replay prevention | Implemented | Summary content hash plus database idempotency claims and replay response | Concurrent MySQL test |
| Summary size/count limits | Implemented | 8 KiB summary, 20 list items, 500 characters/item, 100 active records/customer | Boundary-value runtime tests |
| Sensitive-data restrictions | Implemented | Key allowlist and patterns for secrets, payment cards, government IDs, diagnoses, hidden prompts/reasoning | Runtime payload corpus |
| Retention metadata | Implemented | 365-day configurable operational default, `expires_at`, `retention_policy` | Policy approval and cleanup execution |
| Consent-aware writes | Implemented | Profile, preference, summary and correction writes fail closed without storage consent | Runtime consent-withdrawal test |
| Consent-aware retrieval | Implemented | Agent retrieval requires active use consent and approved non-Start-Fresh context; preview remains customer review | Runtime immediate-withdrawal test |
| Cross-customer isolation | Implemented | All repositories bind `customer_id` from the verified session; browser customer IDs are ignored | Adversarial WordPress API test |
| Gate C Authorization | Implemented | WordPress/MySQL adversarial ownership, session, CSRF, origin, role, namespace, scope, and cross-customer tests passed | Independent peer review |
| Gate D Consent and Memory | Implemented | Complete runtime lifecycle, concurrency, rollback, privacy, revocation, and isolation tests passed | Independent peer review |
| Asset 3 customer experience | Partially Implemented | Phase 6 controls plus desktop/mobile semantic and visual review; labels and mobile layout corrected | Independent assistive-technology review |
| Asset 4 administration | Implemented | WordPress capability/nonce/role, health, audit, cleanup, SMTP, and revocation runtime tests passed | Production operations parity |
| Asset 4 cleanup/operations | Partially Implemented | Phase 8 daily/manual bounded cleanup and run summaries; 6 tests | WP-Cron/MySQL failure/recovery tests |
| Asset 2/4 security hardening | Partially Implemented | Legacy bypass disabled and request/audit/privacy/DoS controls added; 7 tests | Runtime adversarial tests, scan and peer review |
| Asset 4 acceptance/documentation | Partially Implemented | API/schema/security/operations/runtime/final candidate documents complete | Execute runtime plan |
| Gate E Administration | Implemented | Code-contract and WordPress runtime requirements passed | Production operations parity |
| Gate F Production Readiness | Partially Implemented | Gates A-E passed; 96/96 tests; staging package and runtime evidence updated | Production inventory, independent accessibility/peer review, CSP compatibility, hosting outage/monitoring validation |

## Asset 1 — Secure Memory Architecture

| ID | Requirement | Status | Current evidence / deviation | Remediation target |
|---|---|---|---|---|
| A1-1.1 | Passwordless secure identity verification and memory retrieval without traditional accounts | Partially Implemented | Email code request and direct recall exist in `tracking.php`; no approved session or service boundary | Phases 1–5 |
| A1-1.1a | Voluntarily remember approved preferred name, goals, interests, experience, budget, formats, summaries, support requests, and preferences | Partially Implemented | Name/phone/email and one text summary are stored; structured approved categories are absent | Phase 5 |
| A1-1.1b | Store information only with appropriate consent | Implemented Incorrectly | Public tracking trusts browser-provided `memory_consent`; consent can be forged | Phase 4, highest priority |
| A1-1.1c | Protect privacy and prevent unauthorized access | Implemented Incorrectly | OTP reduces unauthorized reads, but memory writes and consent are unauthenticated | Phases 3–5, 9 |
| A1-1.1d | Use remembered information only with explicit permission | Missing | Verification immediately returns history; no preview/use approval per conversation | Phase 5 |
| A1-1.2 | Securely resume previous conversations | Partially Implemented | Up to five summaries are returned after an OTP; no session, namespace, or approved context | Phases 3 and 5 |

## Asset 2 — Threat Model and Abuse Cases

| ID | Requirement / acceptance criterion | Status | Current evidence / gap | Required work |
|---|---|---|---|---|
| A2-2.1 | Only verified customers access remembered information | Partially Implemented | OTP is required for the recall response; no verified session protects later operations | Session-bound authorization |
| A2-2.2 | Consent is always respected | Implemented Incorrectly | Consent is a forgeable client Boolean and is not checked as independent storage/use consent | Server consent service |
| A2-2.3 | Prevent retrieval through guessing/enumeration | Partially Implemented | Neutral request response and attempt limits exist; per-email limits, monitoring, immutable expiry absent | Verification hardening |
| A2-2.4 | Protect administrative functions | Partially Implemented | Sales dashboard uses capability/nonces; approved memory administration does not exist | Phase 7 |
| A2-2.5 | Security-sensitive actions observable | Missing | Client tracking events are forgeable; no append-only audit service | Audit foundation |
| A2-2.6 | Compartmentalize subsystem compromise | Missing | Verification, identity, consent, memory, and tracking share one procedural file and tables | Modular services and scopes |
| A2-4 | Enforce every Internet→API→verification→session→memory→database→admin trust boundary | Missing | Public AJAX handlers cross multiple boundaries without session/agent authorization | REST services/middleware |
| A2-5 | Address curious visitor, bot, malicious customer/admin, external attacker, and insider capabilities | Partially Implemented | Basic public throttling/capability checks only | Threat-mapped controls/tests |
| A2-AC1 | Email enumeration: neutral responses, rate limits, audit, monitoring | Partially Implemented | Neutral response and IP limit exist; no per-email limit, trusted audit, or monitoring | Phase 2/7/9 |
| A2-AC2 | Code guessing: five attempts, request lock, short expiry, rate limit, audit | Partially Implemented | Five-attempt deletion/IP limit exist; expiry can be extended; no durable request/audit | Phase 2 |
| A2-AC3 | Replay: single use, atomic transition, immediate invalidation | Partially Implemented | Successful transient is deleted, but atomic database consumption is absent | Phase 2 |
| A2-AC4 | Session hijacking: secure HttpOnly cookie, token hash, idle/absolute expiry | Missing | No server-side customer session | Phase 3 |
| A2-AC5 | Cross-customer access: resolve ownership only from session | Implemented Incorrectly | Submitted email selects the customer | Phases 3 and 5 |
| A2-AC6 | SQL injection: parameterized queries, validation, least privilege | Partially Implemented | Lookups use `$wpdb->prepare`; no complete API/data-layer review or DB-role documentation | Phase 1/9 |
| A2-AC7 | XSS: validation, contextual escaping, CSP where appropriate | Partially Implemented | Chat bubbles and PHP output escape; no complete stored-memory/payload test or CSP review | Phase 9 |
| A2-AC8 | CSRF protection on consent/deletion | Missing | Those endpoints do not exist; existing AJAX nonce is not an approved session-bound design | Phases 3–5 |
| A2-AC9 | Verification flooding: per-IP and per-email limits, lockouts, monitoring | Partially Implemented | IP-only transient limits; no per-email limit/monitoring | Phase 2/7 |
| A2-AC10 | DoS: rate limits, proxy protection, timeouts, monitoring, graceful degradation | Partially Implemented | Some endpoint limits and mail timeout patterns exist; tracking is unthrottled | Phases 2/8/9 |
| A2-AC11 | Administrative abuse: RBAC and immutable attributable audit | Missing | Capability checks exist only for sales admin; no immutable admin audit | Phases 1 and 7 |
| A2-AC12 | Memory deletion: verified ownership, confirmation, audit | Missing | No deletion flow | Phase 5 |
| A2-AC13 | Backup exposure: encryption/access/key-management guidance | Missing | No backup security or recovery documentation | Phases 8 and 10 |
| A2-AC14 | Insider harvesting: least privilege, export restrictions, audit/review | Missing | Event CSV exists without secure-memory access controls/audit | Phases 7–10 |
| A2-AC15 | Consent bypass: validate before every retrieval and fail closed | Implemented Incorrectly | One Boolean is read during verification; no independent/current use decision | Phase 4/5 |
| A2-8 | Address all critical risks before production | Missing | Known high forged-consent/memory-poisoning defect remains | Gates B–F |
| A2-9 | Monitor failures, limits, revocation, deletion, authorization, backup, and audit failures | Missing | No approved metrics/alerts | Phases 7–8 |
| A2-10 | Document residual risks | Missing | No Phase 3 residual-risk document | Phase 10 |
| A2-11 | Peer review, security automation, dependency scan, static analysis, secret management, updates | Missing | Only Python tests; no scan/CI/review record | Phases 9–10 |
| A2-12 | Trace each threat mitigation to tasks/tests/signals | Missing | This matrix identifies gaps; final threat-control matrix with test results/signals remains | Phase 10 |

## Asset 3 — Customer Experience and Screen Copy

| ID | Requirement | Status | Current evidence / gap | Required work |
|---|---|---|---|---|
| A3-1 | Low-friction, transparent, permission-based, customer-controlled experience | Partially Implemented | Friendly recall prompt exists; preview/control journey is absent | Phase 6 |
| A3-2 | Simplicity, transparency, respect, confidence, accessibility principles | Partially Implemented | Tone is calm and form is responsive; full principles and accessibility not validated | Phase 6/10 |
| A3-3 | Returning vs Start Fresh journey through preview and consent choice | Missing | Returning button exists; approved state machine does not | Phase 6 |
| A3-4 | Welcome Back screen and exact primary/secondary choices/copy | Missing | Button is embedded inside new-customer form with different copy | Phase 6 |
| A3-5 | Verify Your Email screen, validation, neutral success copy | Partially Implemented | Equivalent screen exists; approved heading/copy/neutral sentence differs | Phase 6 |
| A3-6 | Check Inbox screen with Verify and rate-limited Resend | Partially Implemented | Code field exists; Resend is missing and copy differs | Phase 6 |
| A3-7 | Distinct incorrect, expired, and locked states | Missing | One generic invalid/expired message is used | Phase 2/6 |
| A3-8 | Verification Successful screen before memory display | Missing | Verification directly renders history | Phase 6 |
| A3-9 | Allowlisted Memory Preview cards and four choices | Missing | Raw text summaries are immediately shown; no use/start-fresh/privacy decisions | Phase 5/6 |
| A3-10 | Start Fresh explanation and action; preserve saved memory | Missing | No post-verification Start Fresh state | Phase 5/6 |
| A3-11 | Memory Enabled confirmation and continuation | Missing | No explicit current-context use approval | Phase 5/6 |
| A3-12 | Privacy Settings for storage/use/marketing with explanations | Missing | One initial memory checkbox only | Phase 4/6 |
| A3-13 | Delete Memory warning, confirmation checkbox, irreversible action | Missing | No deletion UI/API | Phase 5/6 |
| A3-14 | Memory Deleted confirmation | Missing | No deletion flow | Phase 6 |
| A3-15 | Session Expired screen and Verify Again | Missing | No session system | Phase 3/6 |
| A3-16 | Calm, actionable system error messages | Partially Implemented | Some calm errors exist; no standardized states/codes | Phase 1/6 |
| A3-17 | Visible loading states for send/verify/load/update/delete | Partially Implemented | Submit button disables; approved loading messages are absent | Phase 6 |
| A3-18 | Nothing Saved Yet empty state | Partially Implemented | A short no-history bubble exists; approved screen/action is absent | Phase 6 |
| A3-19 | Keyboard, screen reader, errors, contrast, responsive/touch, reduced motion | Partially Implemented | Semantic inputs/responsive CSS exist; no announced errors, reduced-motion rule, or audit | Phase 6/10 |
| A3-20 | Friendly, respectful, clear, professional, reassuring, educational tone | Implemented | Existing copy generally conforms | Preserve in Phase 6 |
| A3-21 | Plain, concise, purpose-explaining, control-reinforcing production copy | Partially Implemented | Some purpose/control copy exists; approved copy incomplete | Phase 6 |
| A3-22 | Customer completes verify, preview, use choice, consent, deletion, recovery, mobile journey | Missing | Only request-code UI was live-smoke-tested | Phases 5–6/10 |
| A3-23 | Future passkeys/devices/mobile/multilingual remain non-Version-1 enhancements | Deferred | Explicitly excluded by Assets 4/5 | No Phase 3 implementation |
| A3-24 | All screens/workflows/copy/errors/loading/accessibility align with Assets 1/2 | Missing | Full journey not implemented | Gate F |

## Asset 4 — Build Command, Implementation Sequence, and Gates

| ID | Requirement | Status | Current evidence / gap | Milestone |
|---|---|---|---|---|
| A4-1 | Assets 1–3 and 5 are authoritative; record deviations | Implemented | Repository instructions and this matrix establish precedence | Ongoing |
| A4-2 | Implement all 11 customer and approved administrator capabilities | Partially Implemented | Request/verify/direct history subset only | Phases 1–8 |
| A4-3 | Respect Version 1 inclusions/exclusions | Partially Implemented | Email OTP/no SMS are aligned; required sessions/REST/consent/audit absent | All phases |
| A4-4.1 | Logical Verification Service boundary and controls | Partially Implemented | Procedural functions exist without approved persistence/service boundary | Phase 2 |
| A4-4.2 | Logical Session Service | Missing | None | Phase 3 |
| A4-4.3 | Logical Memory Service | Implemented Incorrectly | Direct table query/return bypasses approved authorization | Phase 5 |
| A4-4.4 | Logical Consent Service | Missing | Boolean stored on customer only | Phase 4 |
| A4-4.5 | Append-only Audit Service | Missing | Sales event log is client-forgeable and not the approved audit | Phase 1 |
| A4-4.6 | Administration Service | Missing | Sales dashboard is not secure-memory administration | Phase 7 |
| A4-4.7 | Cleanup Service | Missing | No scheduler/status/run summary | Phase 8 |
| A4-5 | Enforce approved customer state model and reject invalid transitions | Missing | Client-only ad hoc steps; no server state machine | Phases 2–6 |
| A4-6.1 | Normalization, neutral request, secure request/code, hash, immutable expiry, attempts, replay, email/IP limits, resend, audit, configurable defaults | Partially Implemented | Basic email/code/hash/attempt/IP/neutral response exist; most controls absent or incorrect | Phase 2 |
| A4-6.2 | Exact neutral response | Partially Implemented | Current response adds profile-related wording and differs | Phase 2/6 |
| A4-6.3 | Replaceable email abstraction, safe failures, admin test, plain nonmarketing email | Partially Implemented | Direct `wp_mail()` with suitable body; no abstraction/status/test | Phase 2/7 |
| A4-7 | Hashed, secure-cookie session; 30m idle/2h absolute; validation/revocation/rotation | Missing | None | Phase 3 |
| A4-8 | Three independent, versioned, historic, fail-closed consent categories | Missing | One forgeable Boolean | Phase 4 |
| A4-9 | Structured/classified memory and customer-visible allowlist | Missing | Unstructured text summary | Phase 5 |
| A4-10 | Nine required logical tables, migrations, indexes, UTC, safe recovery/versioning | Missing | Three legacy tables created via one `dbDelta`; schema version 1.0 | Phase 1 |
| A4-11 | Required versioned REST endpoints and envelopes/errors | Missing | AJAX endpoints only | Phases 1–7 |
| A4-12 | Implement all 15 customer interface states with approved copy/accessibility | Missing | Small subset only | Phase 6 |
| A4-13 | Approved admin sections/actions with controls/audit | Missing | Sales totals page only | Phase 7 |
| A4-14 | Mandatory security controls and explicit threat defenses | Partially Implemented | Sanitization/nonces/hash/basic limits only | Phases 1–9 |
| A4-15 | Separate safe security audit and operational logging | Missing | No such separation | Phases 1/8 |
| A4-16 | Configurable scheduled cleanup and retention behavior | Missing | None | Phase 8 |
| A4-17 | Unit, integration, API, security, and E2E tests listed | Missing | Two source-string recall tests only | Every phase |
| A4-18 | Automated/manual accessibility acceptance | Missing | No tooling or review record | Phases 6/10 |
| A4-19 | Indexed/bounded/paginated/reliable behavior and graceful failure | Missing | Legacy indexes exist but approved services do not | Phases 1/7/8 |
| A4-20 | Preserve conventions or modular secure-memory structure | Missing | Current monolithic `tracking.php` does not satisfy logical separation | Phase 1 |
| A4-21 | Engineering standards and centralized security logic | Partially Implemented | Some strict/sanitized WordPress patterns; logic is duplicated/procedural | All phases |
| A4-22.0 | Reconnaissance and implementation map before coding | Implemented | `phase-3-implementation-map.md` and this matrix | Phase 0 |
| A4-22.1 | Foundation sequence | Missing | Approved foundation not present | Phase 1 |
| A4-22.2 | Verification sequence | Partially Implemented | MVP subset exists | Phase 2 |
| A4-22.3 | Session sequence | Missing | None | Phase 3 |
| A4-22.4 | Consent sequence | Missing | None | Phase 4 |
| A4-22.5 | Memory/profile sequence | Missing | Direct recall is nonconforming | Phase 5 |
| A4-22.6 | Customer experience sequence | Partially Implemented | Entry/request/code/empty fragments | Phase 6 |
| A4-22.7 | Administration sequence | Missing | None | Phase 7 |
| A4-22.8 | Cleanup/operations sequence | Missing | None | Phase 8 |
| A4-22.9 | Security review sequence | Missing | Initial audit only | Phase 9 |
| A4-22.10 | Acceptance/documentation sequence | Missing | Specification and matrix only | Phase 10 |
| A4-23A | Gate A Foundation | Fail | No migrations framework, standard REST envelope, or trusted audit service | Phase 1 |
| A4-23B | Gate B Authentication | Fail | No session creation; replay/rate/expiry runtime tests absent | Phases 2–3 |
| A4-23C | Gate C Authorization | Fail | No session-bound protected endpoints; email selects customer | Phase 3 |
| A4-23D | Gate D Consent and Memory | Fail | Forgeable consent; no use approval/start fresh/deletion/allowlist | Phases 4–5 |
| A4-23E | Gate E Administration | Fail | Approved administration absent | Phase 7 |
| A4-23F | Gate F Production Readiness | Fail | High vulnerability, missing tests/docs/acceptance | Phases 9–10 |
| A4-24 | Produce all 20 implementation deliverables | Missing | Approved assets and this matrix exist; production deliverables mostly absent | Phase 10 |
| A4-25 | Threat-control matrix with file/test/result/risk/signal | Partially Implemented | Requirement gaps are mapped here; final implemented control/test/signal matrix remains | Phase 10 |
| A4-26 | Final implementation report content | Missing | Prior report described MVP, not completed approved implementation | Phase 10 |
| A4-27 | Incremental secure working rules and truthful claims | Partially Implemented | Current re-audit is aligned; deployed MVP was previously overstated | Ongoing |
| A4-28 | Initial assessment/map/plan/testing/constraints before coding | Implemented | Recorded in implementation map and this matrix | Phase 0 |
| A4-29 | Completion only after all approved security/UX/admin/cleanup/tests/docs | Missing | Phase 3 is not complete | Gate F |

## Asset 5 — Identity and Memory API

| ID | Requirement group | Status | Current evidence / deviation | Milestone |
|---|---|---|---|---|
| A5-1 | Shared Identity & Memory API centralizes identity, verification, sessions, consent, profiles, preferences, summaries, authorization, deletion, audit | Missing | Legacy plugin tables/handlers are not a shared service | Phases 1–8 |
| A5-2 | API is authoritative; agents do not duplicate shared trust data | Missing | Sales plugin directly creates/queries its own customer/memory data | Phase 1/5 |
| A5-3 | One identity/consent/session system, controlled sharing, isolation, visibility, audit, compatibility | Missing | None of the platform controls exist | All phases |
| A5-4 | Applications access persistence only through logical API services | Implemented Incorrectly | Customer handler directly accesses tables | Phase 1/5 |
| A5-5.1 | Include all listed Version 1 identity/session/profile/consent/memory/admin functions | Missing | Small verification/recall subset | Phases 1–8 |
| A5-5.2 | Exclude passwords/social/SMS/passkeys/biometrics/tracking/ads/marketing inference/raw transcripts/public search/bulk export/unapproved identity | Implemented | No excluded authentication/advertising features added; raw summary is not a full transcript | Preserve |
| A5-6 | Versioned `/wp-json/budly-identity/v1` namespace | Missing | Public `admin-ajax.php` only | Phase 1/2 |
| A5-7 | HTTPS, JSON UTF-8, secure cookie/bearer, content-type validation | Partially Implemented | Production HTTPS; form-encoded AJAX and no secure session/content-type enforcement | Phase 1/3 |
| A5-8 | Registered agent/request/conversation headers and correlation rules | Missing | No agent registry or standard headers | Phase 1/5 |
| A5-9 | Standard success/error envelope with request/version/timestamp metadata and safe errors | Missing | WordPress AJAX envelope only | Phase 1 |
| A5-10 | Correct HTTP status semantics | Partially Implemented | Some AJAX handlers set 400/403/429; full endpoint contract absent | API phases |
| A5-11 | Stable machine-readable error codes | Missing | Human message strings only | Phase 1 |
| A5-12 | Four authentication levels | Missing | No verified/session/memory-authorized/admin API levels | Phases 3–7 |
| A5-13 | Agent registration model and inactive/unknown denial | Missing | None | Phase 1/5 |
| A5-14 | Scope-based authorization without overriding consent | Missing | None | Phase 1/5 |
| A5-15 | Immutable opaque identity resolved from session; server-owned email verification | Implemented Incorrectly | Numeric customer ID/internal email selected by request; no opaque ID/session | Phase 1/3 |
| A5-16 | Explicit allowlisted customer-visible profile model and updates | Missing | Name/email/phone stored together; no approved schema/update endpoint | Phase 5 |
| A5-17 | Structured, purpose-limited, editable/deletable preferences; no sensitive inference | Missing | No preference model | Phase 5 |
| A5-18 | Shared, agent-specific, and restricted namespaces with isolation | Missing | One conversations table | Phase 5 |
| A5-19 | Versioned/classified memory record with agent, consent reference, expiry | Missing | Legacy text row lacks all metadata | Phase 1/5 |
| A5-20 | Nine-condition verified/consented/registered/scoped/schema/audited storage rule and prohibited-data list | Implemented Incorrectly | Browser can store arbitrary summary for arbitrary email | Phases 4–5 |
| A5-21 | Ten-condition session/consent/context/agent/scope/namespace/classification/purpose/audit retrieval rule | Implemented Incorrectly | Correct OTP returns raw profile/history directly | Phases 3–5 |
| A5-22 | Conversation/agent/purpose-bound expiring memory-use context | Missing | None | Phase 5 |
| A5-23 | Independent storage/use/marketing consent with statuses/version/time | Missing | One Boolean | Phase 4 |
| A5-24 | Immediate consent enforcement and no silent recreation | Missing | No withdrawal/use separation | Phase 4/5 |
| A5-25.1 | `POST /auth/request-code` with request ID, 600s, neutral response/stable errors | Implemented Incorrectly | AJAX email request has no request ID/API envelope/durable record | Phase 2 |
| A5-25.2 | `POST /auth/verify` by request ID creates secure session and stable errors | Missing | Email+code returns memory directly | Phases 2–3 |
| A5-26.1 | `GET /auth/session` | Missing | None | Phase 3 |
| A5-26.2 | `POST /auth/logout` revokes server session | Missing | None | Phase 3 |
| A5-27 | `GET /identity` with approved agent/scope | Missing | None | Phase 5 |
| A5-28.1 | `GET /profile` | Missing | None | Phase 5 |
| A5-28.2 | allowlisted `PATCH /profile` | Missing | None | Phase 5 |
| A5-29.1 | `GET /preferences` | Missing | None | Phase 5 |
| A5-29.2 | allowlisted `PATCH /preferences` | Missing | None | Phase 5 |
| A5-30.1 | `GET /consent` | Missing | None | Phase 4 |
| A5-30.2 | immediate/versioned `PATCH /consent` | Missing | None | Phase 4 |
| A5-31 | allowlisted `GET /memory/preview` before use approval | Missing | History is returned during verify | Phase 5 |
| A5-32 | context-bound `POST /memory/use` | Missing | None | Phase 5 |
| A5-33 | `POST /memory/start-fresh`, suppress only current context | Missing | None | Phase 5 |
| A5-34 | authorized `GET /memory/shared` | Missing | None | Phase 5 |
| A5-35 | isolated `GET /memory/agent/{namespace}` | Missing | None | Phase 5 |
| A5-36 | structured consent-gated `POST /memory/summary` | Implemented Incorrectly | Summary storage occurs through unauthenticated tracking | Phase 5 |
| A5-37 | authenticated `DELETE /memory`, de-identification, revocation, audit | Missing | None | Phase 5 |
| A5-38 | minimized policy-filtered `POST /context` | Missing | None | Phase 5 |
| A5-39 | Safe context injection and no unrelated/cross-agent/raw logging use | Missing | No approved context endpoint/policy | Phase 5/9 |
| A5-40 | Freshness metadata and current-statement precedence/correction | Missing | Timestamps display as labels only; no correction behavior | Phase 5 |
| A5-41 | Idempotency for specified state-changing operations | Missing | None | Phases 4–7 |
| A5-42 | Bounded pagination for collections/audit | Missing | Recent sales events fixed at 25; approved collections absent | Phase 7 |
| A5-43 | Allowlisted filters; no raw SQL filters | Missing | Approved audit/filter API absent | Phase 7 |
| A5-44 | Rate limits by IP/email/session/agent/endpoint/admin with suggested defaults | Partially Implemented | IP-only request/verify transient limits | Phases 2–7 |
| A5-45 | Resolve protected ownership exclusively from session | Implemented Incorrectly | Email request controls customer selection | Phase 3/5 |
| A5-46 | Scoped, revocable, rotating service auth; never browser-secret or consent override | Missing | No service authentication | Phase 1/5 |
| A5-47 | Approved administrative endpoint inventory and controls/audit | Missing | None | Phase 7 |
| A5-48 | Safe detailed admin health endpoint | Missing | None | Phase 7/8 |
| A5-49 | Full approved audit-event vocabulary | Missing | Sales events are different and forgeable | Phase 1 onward |
| A5-50 | Safe append-only audit record structure | Missing | None | Phase 1 |
| A5-51 | API/schema/consent versioning | Missing | Plugin/database options only; no approved record versions | Phase 1/4/5 |
| A5-52 | Version 1 backward-compatibility rules | Missing | No Version 1 API | Phase 10 |
| A5-53 | Serializer-enforced data classifications | Missing | No classification model | Phase 5 |
| A5-54 | Minimized requested sections and broad-request rejection | Missing | Direct history returns all five records | Phase 5 |
| A5-55 | Prompt-safety controls, structured data, delimit/filter/limit/detect, no hidden reasoning | Missing | Free-text summaries have no prompt-safety processing | Phase 5/9 |
| A5-56 | Structured conversation summary standard | Missing | Pipe-delimited text summary | Phase 5 |
| A5-57 | Customer correction flow with consent and audit | Missing | None | Phase 5/6 |
| A5-58 | Complete/de-identified deletion, session revocation, audit, truthful result | Missing | None | Phase 5 |
| A5-59 | Fail-closed identity/consent/audit; Start Fresh on memory failure; no session on email failure | Implemented Incorrectly | No services/session; mail result is ignored during request | Phases 1–8 |
| A5-60 | Full security-control list | Partially Implemented | OTP hash/nonces/prepared lookup/escaping/basic limits only | Phases 1–9 |
| A5-61 | Data minimization, independent marketing, review/correction/deletion/isolation/retention | Missing | Small review fragment only | Phases 4–10 |
| A5-62 | Complete authentication/session/consent/memory/agent/security tests | Missing | Static source assertions only | Every phase |
| A5-63 | Agent integration checklist | Missing | Sales agent is not registered/documented/scoped/tested | Phase 5/10 |
| A5-64 | Approved 17-step integration flow | Missing | Current flow skips sessions, preview approval, context authorization, structured storage | Phases 2–6 |
| A5-65 | Prohibit listed integration anti-patterns | Implemented Incorrectly | Direct table access and use-after-verify violate anti-patterns | Phases 1–5 |
| A5-66 | Authorization-safe session-bound caching and invalidation | Missing | No approved session/cache model | Phases 3–5 |
| A5-67 | Privacy-safe observability metrics | Missing | Sales counters only | Phase 7/8 |
| A5-68 | Immediate consent/revocation, graceful memory fallback, no auth fallback | Missing | No approved services | Phases 3–8 |
| A5-69 | Central and per-agent integration documentation | Missing | Existing docs predate Phase 3 implementation | Phase 10 |
| A5-70 | All identity/agent/consent/memory/security/ops/compatibility acceptance checks | Fail | Most required controls absent | Gates A–F |
| A5-71 | Operational Version 1 API, endpoints, security/integration tests/docs, no high defects | Fail | No REST API and high consent-poisoning defect | Gate F |
| A5-72 | Shared trust-layer platform rule | Missing | Existing sales plugin remains an isolated memory implementation | Phase 1 onward |

## Approved deferrals and exclusions

| ID | Item | Status | Justification |
|---|---|---|---|
| D-1 | SMS verification / phone-number-only recall | Deferred | Explicitly excluded by Assets 4 and 5; avoids unapproved SMS cost/privacy model |
| D-2 | Passwords, social login, passkeys, biometrics | Deferred | Explicit Version 1 exclusions |
| D-3 | Anonymous cross-device tracking/device fingerprinting | Deferred | Explicit Version 1 exclusion |
| D-4 | Automatic marketing enrollment/advertising profiles | Deferred | Explicitly prohibited; marketing requires independent consent |
| D-5 | Full transcript sharing and bulk customer export | Deferred | Explicitly excluded; structured summaries and customer self-deletion are required instead |
| D-6 | WooCommerce Purchase Attribution (Phase 4 product roadmap phase) | Deferred | Repository instruction prohibits beginning it until all Phase 3 gates pass |
| D-7 | Production deployment of remediation | Deferred | Requires completed gates and explicit deployment authorization; 1.2.0 remains deployed but is not accepted |

## Immediate remediation priority

The first code remediation after completing this matrix is to remove the public
tracking endpoint's authority to create/update consented customers or store memory.
Until the approved session, consent, agent, and memory services are available, the
legacy endpoint must fail closed for all identity, consent, and memory writes while
continuing to accept non-PII sales analytics within bounded limits.

## v1.7.1 production stabilization traceability delta

This patch comparison supersedes only the obsolete implementation-status cells above;
Assets 1-5 remain authoritative and the historical matrix remains preserved as evidence.

| Patch requirement | Governing requirement | Current v1.7 evidence/gap | v1.7.1 action | Acceptance evidence |
|---|---|---|---|---|
| Session errors fail closed | A2 Abuse Cases 4-5; A4 Gate C; A5-15, A5-21, A5-45, A5-59 | v1.7 conversation, relationship, and journey handlers replace non-numeric session results with customer `1` | Centralize verified-customer resolution and return the existing REST error unchanged; prohibit default identity | Executable PHP tests for anonymous, expired, invalid, unverified, and cross-customer access/mutation |
| Truthful private admin aggregates | A4-4.6, A4-13, A4 Gate E; A5-47, A5-48, A5-67 | v1.7 returns literal conversation and lifecycle figures | Query privacy-minimized aggregate values from authoritative v1.7 tables; empty state returns zero | Executable PHP empty/populated/unauthorized tests |
| Governed lifecycle sequence | A4-5; approved v1.7 canonical lifecycle | Stage names are validated but canonical ordering is not | Permit same-stage no-op and one canonical forward step only; preserve evidence and reject jumps | Executable valid-sequence, invalid-jump, and persistence tests |
| PHP adaptive behavior parity | Approved v1.7 implementation; A5-39, A5-40 | PHP skips known fields but ignores approved journey priority and confidence stopping | Add bounded journey priority and confidence threshold behavior without generative questioning | Executable PHP known-field, duplicate avoidance, journey, confidence, and exhausted-question tests |
| Loader completeness | A4-4; v1.7 hotfix `ae9ed566` | Production hotfix loads the two v1.7 modules but no executable completeness guard exists | Preserve loader entries and add executable load/reflect tests | PHP loader regression test |
| Immutable patch provenance | A4 Gate F, A4-24, A4-26 | Production lineage is newer than immutable `budly-v1.7` tag | Version 1.7.1, deterministic package, release records, rollback/restoration evidence; no schema/rules/config change | Repository, version, dual-build, checksum, CI, and LocalWP evidence |
