# Budly Conversational Runtime Phase 1 Implementation Report

Status: non-production prototype; production deployment and traffic cutover are prohibited.

## 1. Repository audit

- Assigned handoff path: `C:\Users\19196\Documents\Codex\2026-08-24\codex-handoff-budly-conversational-runtime-phase` (initially empty and not a Git repository).
- Verified baseline: `C:\Users\19196\Documents\Codex\2026-07-29\master-engineering-handoff-budly-sales-agent\v171-workspace`.
- Baseline remote: `https://github.com/theworkathomeacademy/budly-agent.git`.
- Baseline branch/commit: `main` at `87093bd33db344281d998aaa2c6e1f0b1f89ea85`.
- Baseline state: clean. The adjacent `release/budly-v1.6` checkout was dirty because `v171-workspace/` was untracked and was not selected.
- Controlled development checkout: cloned from the verified baseline into the assigned handoff path. No production system was contacted or changed.

Existing components audited and preserved:

- WordPress plugin: `deploy/wordpress/budly-sales-agent`.
- Bootstrap/router: `includes/SecureMemory/Bootstrap.php`, `includes/SecureMemory/Api/Routes.php`.
- Conversation: `includes/Conversation/ConversationManager.php`, `includes/Lifecycle/LifecycleEngine.php`, `src/conversation_service.py`.
- Session/security: `Sessions/*`, `SessionGuard`, `RequestSecurity`, consent and memory services.
- Recommendation: deterministic `src/sales_agent.py` and `DecisionService` structures.
- Provider integration: existing server-side OpenAI calls in Python proof code; no provider-neutral production gateway existed.
- Attribution: existing `includes/Commerce/AttributionService.php` and related hooks; no competing attribution implementation was added.
- Tests: standard-library `unittest`, PHP executable tests, packaging and release contract tests.
- Feature flags: no suitable existing conversational-runtime flag registry was found; Phase 1 uses isolated configuration with safe defaults.

## 2. Implementation summary

Built a server-side, standard-library-only `src/budly_runtime` shell beside the legacy application:

1. orchestrator sequences a turn without embedding commercial policy;
2. model-independent, process-local sessions hold the required Phase 1 state;
3. recent turns are bounded and older operational text is summarized without hidden reasoning;
4. versioned personality modules load from configuration;
5. prompt layers use the required deterministic precedence and label customer/knowledge text as untrusted data;
6. a provider-neutral gateway routes to replaceable adapters;
7. deterministic mock adapters prove the interface without credentials;
8. strict validation yields PASS, REPAIR, FALLBACK, or BLOCK with one repair attempt;
9. approved-only `knowledge.retrieve` returns provenance or logs a knowledge gap;
10. structured turn and commercial-event contracts omit chain-of-thought and secrets.

Deviations and bounded omissions:

- No real provider adapter was activated because no authorized, safely configured credentials were established in the selected repository. The deterministic mock is the proof provider.
- No WordPress endpoint was wired. This intentionally keeps the prototype non-production and the legacy runtime untouched.
- The later authorized TG-P01 work promoted the subordinate interface into the canonical controlled ADR-008 vertical slice; see `docs/tool-gateway/TG-P01-IMPLEMENTATION-REPORT.md`.
- The exact named Conversation governing documents were not locally available. Requirements explicit in the owner handoff were implemented; exact personality prose and any document-dependent policy remain blocked pending authoritative artifacts.
- The ratified model scenario names and adapter contract are scaffolded; no candidate model was scored or declared a winner.

## 3. Files changed

- `src/budly_runtime/__init__.py`: public prototype interface.
- `src/budly_runtime/config.py`: feature flags and non-production configuration guard.
- `src/budly_runtime/session.py`: session schema, isolation, history bounding, summarization.
- `src/budly_runtime/personality.py`: versioned package loading and module validation.
- `src/budly_runtime/prompt.py`: deterministic prompt precedence and trust boundaries.
- `src/budly_runtime/model.py`: gateway, adapter interface, request/result contracts, mocks.
- `src/budly_runtime/validation.py`: structured validation, repair, block, and safe errors.
- `src/budly_runtime/knowledge.py`: retrieval trigger, approved retrieval, tool checks and normalization.
- `src/budly_runtime/events.py`: turn and commercial event contracts.
- `src/budly_runtime/orchestrator.py`: sequencing and composition root.
- `config/budly_runtime/personality-package-v0.1.json`: versioned personality configuration.
- `config/budly_runtime/runtime.example.json`: safe configuration and environment variable names.
- `tests/test_budly_runtime_phase1.py`: Phase 1 unit, integration, and adversarial tests.
- `tests/model_acceptance/scenarios-v0.1.json`: ratified-scenario harness scaffold.
- This report.

## 4. Configuration

Safe defaults:

- `budly_llm_enabled=false`
- `budly_structured_output_enabled=true`
- `budly_knowledge_retrieve_enabled=false`
- `budly_session_memory_enabled=true` (process-local only)
- `budly_model_fallback_enabled=true`
- `budly_conversation_logging_enabled=true`

Model registry roles are `mock-primary`, `mock-fallback`, `TBD` complex escalation, and `mock-summarizer`. Reserved server-side environment variable names are `BUDLY_MODEL_PROVIDER`, `BUDLY_MODEL_NAME`, and `BUDLY_MODEL_API_KEY`; no values or secrets were created or printed.

## 5. Database/session changes

No migrations or database changes. Phase 1 session state exists only in a process-local `SessionManager`; it is not CRM or persistent customer memory. Restarting/removing the prototype clears it. This prevents silent persistence of inferred facts and avoids changing ratified secure-memory controls.

## 6. Tests

Intended commands:

```text
python -m unittest tests.test_budly_runtime_phase1 -v
python -m unittest discover -s tests -v
php tests/php/v171_bootstrap_load.php
php tests/php/v171_stabilization.php
```

Execution result on 2026-08-24:

- Phase 1 Python tests: **not run**; `python` was not found and `py` reported `No installed Python found!`.
- Full legacy Python suite: **not run** for the same environment blocker.
- PHP tests: **not run**; no PHP executable was found on PATH.
- Static checks performed: Git whitespace check, JSON parsing, forbidden-secret/client-key scan, changed-file inspection.

The Phase 1 suite contains 25 tests covering sessions, package loading, prompt ordering, variables, schema/repair, fallbacks, routing, tool normalization, orchestration, provider swap, retrieval/provenance/gaps, continuity, events, feature-disable coexistence, prompt injection, malicious retrieved text, malformed output, timeout/unavailability, fabricated execution, pressure, cross-session isolation, and inferred-memory exclusion. These tests are implemented but must not be represented as passed until executed in a runtime-enabled environment.

## 7. Model Gateway proof

`ProviderAdapter.generate(ModelRequest) -> ProviderResult` is provider-neutral. `ModelGateway` resolves role names through a registry. The swap test replaces `mock-a` with `mock-b` while retaining the same orchestrator, personality object, and `SessionManager`; neither identity nor session logic imports a provider SDK. No permanent model was selected.

## 8. Knowledge retrieval proof

The automated integration fixture defines an approved active record with ID `KN-001`, source `prototype-approved-fixture`, and version `1.0`. The expected path returns its content and records `knowledge_used=[KN-001]` and `tools_executed=[knowledge.retrieve]`. Draft/inactive entries are excluded and latest-version-per-domain wins. The missing path records `no_approved_active_match` and the mock returns an honest limitation. Execution remains pending because Python is unavailable.

## 9. Security verification

- Sessions use UUIDs and isolated deep copies; no cross-session lookup is exposed.
- No client code, endpoint, provider SDK, or credential value was added.
- Customer and retrieved content occupy lower, explicitly untrusted prompt layers.
- Only allowlisted operational fields update session state; model-inferred customer context is ignored.
- Provider claims are schema/governance validated before customer visibility.
- Model tool requests cannot execute directly; normalization, capability, authority, purpose, and input checks precede the gateway.
- Logs contain operational fields, IDs, provenance, and metrics—not prompts, raw customer messages, credentials, or chain-of-thought.
- Existing CSRF, origin, consent, privilege, secure-memory, and commerce code is unchanged.

## 10. Rollback/coexistence

To disable: leave or set `budly_llm_enabled=false`. The prototype then returns a disabled/coexistence message and the existing Budly implementation remains untouched. To remove Phase 1, delete only `src/budly_runtime`, `config/budly_runtime`, `tests/test_budly_runtime_phase1.py`, `tests/model_acceptance/scenarios-v0.1.json`, and this report. No migration rollback is needed.

## 11. Traceability

| Implemented requirement | Evidence | Governing authority |
|---|---|---|
| Governance/model independence | prompt, model gateway, validator | Technical Blueprint; Intelligence Architecture; handoff |
| Versioned personality | personality loader + JSON package | Personality artifacts; Prompt Architecture |
| Session/history boundary | session manager and tests | Runtime Specification; Acceptance Test Suite |
| Structured model response | adapter payload + validator | Brain Contract; Model Acceptance Suite |
| Approved knowledge/provenance | knowledge gateway | Knowledge Architecture; Acceptance Test Suite |
| Tool authority path | tool normalization and gateway checks | ADR-008; Technical Blueprint |
| Safe degradation | mapped deterministic responses | Acceptance Test Suite |
| Observability/no hidden reasoning | event logger and tests | Acceptance Test Suite; Prompt Architecture |
| Legacy coexistence | safe-disabled flag; no plugin changes | owner authorization boundary |
| Model bake-off harness | scenario JSON + adapter contract | Model Acceptance Suite |

## 12. Conflicts and blockers

1. The named ratified Conversation artifacts and BROS `.docx` files were not found locally. Exact content/version verification remains blocked.
2. TG-P01 now supplies the controlled canonical ADR-008 vertical slice; broader Tool Gateway phases remain outside this prototype.
3. No authorized provider credential/configuration was established; real-adapter proof is blocked.
4. Python and PHP runtimes are unavailable, so executable acceptance evidence is blocked.
5. No production endpoint, storage policy, or persistent-memory integration was chosen; those choices are intentionally outside authorization.

## 13. Recommendation

The architecture shell is **implementation-complete but not yet acceptance-ready for the controlled model bake-off**. Before bake-off, provide the ratified artifacts, execute all tests in an environment with Python (and legacy PHP checks), resolve any failures, and authorize/configure one non-production provider credential. It is not production-ready and no production action is recommended or authorized.
