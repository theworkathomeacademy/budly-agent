# TG-P01 — BROS Tool Gateway `knowledge.retrieve`

Status: controlled local non-production prototype. Production deployment is prohibited.

## A. Baseline

- Repository: `C:\Users\19196\Documents\Codex\2026-08-24\codex-handoff-budly-conversational-runtime-phase`
- Branch: `main`
- Starting HEAD: `87093bd33db344281d998aaa2c6e1f0b1f89ea85`
- Ending commit: none; changes remain uncommitted for MATT-003 review.
- Initial state: existing related untracked Phase 1 files under `src/budly_runtime`, `config/budly_runtime`, `docs/conversation`, and tests. They were preserved.
- Existing gateway: only the prior explicitly subordinate `knowledge.py` prototype existed. TG-P01 replaces its execution role with the canonical typed service in `tool_gateway.py`; the conversation orchestrator now uses that path.

The named ratified BROS document files were not present in this checkout. This implementation follows the owner-provided TG-P01 handoff and its explicit ADR-008 rules. No conflicting local governing artifact was found.

## B. Files

Created for TG-P01:

- `src/budly_runtime/tool_gateway.py` — typed contracts, authority reconciliation, permissions, registry, adapter, health, validation, audit, and normalized results.
- `config/tool_gateway/tg-p01-knowledge-fixtures.json` — five synthetic fixtures; no production or customer data.
- `tests/test_tg_p01_tool_gateway.py` — TG-P01-T01 through TG-P01-T20.
- `docs/tool-gateway/TG-P01-IMPLEMENTATION-REPORT.md` — boundaries, operation, evidence, and acceptance report.

Modified related Phase 1 files:

- `src/budly_runtime/knowledge.py` — removed the earlier executable gateway; retained retrieval-trigger and compatibility data helpers.
- `src/budly_runtime/orchestrator.py` — routes typed `knowledge.retrieve` requests through TG-P01.
- `tests/test_budly_runtime_phase1.py` — removed tests for the superseded gateway signature.
- `docs/conversation/BUDLY-CONVERSATIONAL-RUNTIME-PHASE1-REPORT.md` — records canonical TG-P01 promotion and corrected test count.

Deliberately unchanged: WordPress plugin, secure memory, consent, commerce, production configuration, database schema, endpoints, DNS, Cloudflare, n8n, Supabase, WooCommerce, and live Budly.

## C. Architecture

- Capability-first: `ToolRequest` contains a strict `CapabilityRef`; unknown capabilities fail closed.
- Actor permission: explicit actor-type entries exist only for `budly_service`, `administrator`, and `test_harness`; there is no wildcard.
- Authority: `reconcile_authority` applies the most restrictive Level/T rule. T2 requires an explicit bounded-write authorization argument; TG-P01 executes only Level 1/T0.
- Environment: only `automated_test`, `development`, and `prototype` are allowed. `production` is executable-test denied before adapter resolution.
- Purpose/channel/data scope: definition and actor permissions control all three; request fields cannot self-authorize.
- Context minimization: the adapter receives only query, domain, result limit, authorization-derived classifications, request ID, and correlation ID.
- Provider abstraction: registry selects `LocalKnowledgeAdapter`; the request schema rejects provider/backend/connection routing fields.
- Filtering: the adapter returns only Active, permitted-domain, permitted-classification fixtures. Superseded and Draft fixtures are excluded.
- Output validation: every returned item must contain non-empty ID, title, version, domain, status, classification, source reference, and content. Invalid output becomes `OUTPUT_VALIDATION_FAILED`; it is never repaired.
- Audit: each gateway execution and auditable raw-request denial creates an `AuditEvent` without query content, arbitrary context, PII, credentials, or hidden reasoning.
- Fail-safe behavior: disabled/unavailable adapters do not select substitutes; exceptions and malformed output cannot become success.

Local execution, once Python 3 is available:

```text
python -m unittest tests.test_tg_p01_tool_gateway -v
python -m unittest tests.test_budly_runtime_phase1 -v
python -m unittest discover -s tests -v
```

No HTTP endpoint is created.

## D. Tests

Tests added: 20 TG-P01 acceptance tests, one for each required scenario.

Commands attempted on 2026-08-24:

```text
python -m unittest tests.test_budly_runtime_phase1 -v
py -m unittest tests.test_budly_runtime_phase1 -v
where.exe uv
where.exe docker
wsl.exe -e sh -lc "command -v python3 && python3 --version"
```

Actual environment results:

- `python`: command not found.
- `py`: launcher present but reports `No installed Python found!`.
- `uv`: not found.
- `docker`: not found.
- WSL execution: access denied while creating the instance.
- TG-P01 executable tests: 0 passed, 0 failed, 20 not run.
- Phase 1 executable tests: 0 passed, 0 failed, 25 not run.

Static checks completed: all JSON fixtures/configuration parse; exactly 20 TG-P01 tests and 25 Phase 1 tests are discoverable by source inspection; no provider SDK/import or network endpoint was added; repository state and changed paths were inspected.

## E. Acceptance Matrix

Because no Python runtime is available, “Actual” below records implemented behavior confirmed by code inspection, not executable acceptance evidence. Every row remains **NOT RUN** until MATT-003 receives a test transcript.

| ID | Expected | Implemented actual | Execution |
|---|---|---|---|
| T01 | Unknown actor denied | `UNKNOWN_ACTOR`, no adapter context | NOT RUN |
| T02 | Production denied | `ENVIRONMENT_DENIED` before adapter | NOT RUN |
| T03 | Unknown capability denied | `UNKNOWN_CAPABILITY` | NOT RUN |
| T04 | Caller cannot route provider | strict schema rejects extra provider field | NOT RUN |
| T05 | Superseded excluded | adapter admits only `Active`; K-TEST-003 excluded | NOT RUN |
| T06 | Restricted data protected | Budly governance domain gets `DATA_SCOPE_DENIED` | NOT RUN |
| T07 | Malformed input denied | raw boundary returns `INPUT_VALIDATION_FAILED` and audit | NOT RUN |
| T08 | Missing provenance fails | `OUTPUT_VALIDATION_FAILED`, result omitted | NOT RUN |
| T09 | Adapter failure normalized | `FAILED/ADAPTER_FAILURE`, no result | NOT RUN |
| T10 | Unauthorized domain denied | `DATA_SCOPE_DENIED` | NOT RUN |
| T11 | Budly retrieval succeeds | Active public fixture, provenance, authority, evidence | NOT RUN |
| T12 | Administrator retrieval succeeds | scoped Restricted governance fixture permitted | NOT RUN |
| T13 | Correlation preserved | request/result/audit use identical ID | NOT RUN |
| T14 | Result bounded | adapter and validator cap to `max_results` | NOT RUN |
| T15 | Empty search succeeds | `SUCCESS` with `items=[]` | NOT RUN |
| T16 | Extra context minimized | strict input rejection; adapter receives nothing | NOT RUN |
| T17 | Authority not downgraded | Level 2/3 and T3/TX deny or require review | NOT RUN |
| T18 | Disabled capability denied | `CAPABILITY_DISABLED`, no adapter call | NOT RUN |
| T19 | Unavailable tool normalized | `UNAVAILABLE/TOOL_UNAVAILABLE`, no fallback | NOT RUN |
| T20 | Denial audited | actor, capability, decision, correlation, error; no query | NOT RUN |

## F. Security

- No production credentials used or created.
- No production system, production data, webhook, external network, or live customer endpoint touched.
- No customer PII or real conversation fixture exists.
- No external deployment or network exposure created.
- Production requests fail closed in code before adapter invocation.
- Provider selection is registry-owned.
- Audit evidence excludes request query/content and arbitrary caller context.
- No database migration was created.

## G. Deviations

1. The governing document files named in the handoff were unavailable locally; the supplied TG-P01 implementation handoff was used as controlling detail.
2. Automated tests could not execute because no usable Python, Docker, uv, or WSL runtime was available. No interpreter installation was inferred as authorized.

## H. Known Limitations

- Process-local audit sink and JSON synthetic fixtures only.
- One capability, one adapter, and no fallbacks.
- Actor authorization is prototype configuration by explicit actor type, not a production identity registry.
- No persistence, HTTP transport, distributed health, production registry database, credential manager, or production wiring.
- The conversation integration uses `customer_policy` as its bounded Phase 1 domain; broader deterministic domain routing requires separate authorization.

## I. Recommendation

**TG-P01 FAIL — CORRECTION REQUIRED**

The implementation is ready for executable review, but TG-P01 cannot pass without running all tests and resolving any failures. This report does not authorize another capability or any production action.
