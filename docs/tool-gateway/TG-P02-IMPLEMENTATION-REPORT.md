# TG-P02 — BROS Tool Gateway `operational.metrics.retrieve`

Status: controlled local non-production prototype. Production deployment is prohibited.

## A. Baseline

- Repository: `C:\Users\19196\Documents\Codex\2026-08-24\codex-handoff-budly-conversational-runtime-phase`
- Branch: `main`
- Starting HEAD: `87093bd33db344281d998aaa2c6e1f0b1f89ea85`
- Ending HEAD: `87093bd33db344281d998aaa2c6e1f0b1f89ea85`
- Commit created: none.
- Initial state: accepted TG-P01 and Phase 1 files were untracked and uncommitted. They were preserved.
- Final state: TG-P02 files are also untracked and uncommitted for MATT-003 review.

## B. Reuse analysis

TG-P02 reuses the accepted TG-P01 implementation for:

- `ToolRequest`, `Actor`, and `CapabilityRef` contracts;
- normalized `NormalizedResult` and shared error classes;
- Level/T authority reconciliation;
- production environment guard;
- explicit actor authorization;
- purpose, channel, domain, and classification enforcement;
- `ToolRegistry` routing authority;
- adapter health normalization;
- context-minimization boundary;
- adapter failure and output-validation normalization;
- `AuditSink`, `AuditEvent`, evidence references, and UTC timestamps.

The accepted registry was generalized from one registered capability to multiple registered capabilities. `knowledge.retrieve` remains on the same gateway and adapter path. No parallel Tool Gateway, actor system, result format, error model, authority resolver, health framework, or audit system was created.

Duplicated logic: none. Metrics-specific input and output validation are capability schemas inside the existing gateway validation boundary.

## C. Files

Created:

- `config/tool_gateway/tg-p02-operational-metrics-fixtures.json` — six deterministic synthetic metrics.
- `tests/test_tg_p02_operational_metrics.py` — exactly TG-P02-T01 through TG-P02-T20.
- `docs/tool-gateway/TG-P02-IMPLEMENTATION-REPORT.md` — this report.

Modified:

- `src/budly_runtime/tool_gateway.py` — multi-capability registry support; typed metrics input/context/item; explicit TG-P02 grants; local metrics adapter; metrics validation; metric-domain audit field; capability-specific permission evidence version.

Deliberately untouched:

- TG-P01 tests and fixtures;
- conversational orchestrator;
- WordPress/PHP files;
- secure memory and consent;
- commerce and attribution;
- database schema/migrations;
- endpoints, deployment, DNS, Cloudflare, n8n, Supabase, WooCommerce, credentials, and production configuration.

## D. Capability registration

```text
capability_id: operational.metrics.retrieve
capability_version: 1.0
bros_level: 1
tool_class: T0
enabled: true
environments: automated_test, development, prototype
purposes: operational_status, system_health_review, internal_test, admin_review
channels: website_chat, internal_test, admin_console
adapter: local_operational_metrics 1.0
fallback: none
```

Budly scope: `tool_gateway` and `system_health`; `PUBLIC` and `INTERNAL`; bounded website/internal channels and purposes.

Administrator/test-harness scope: explicitly listed `revenue_operations`, `tool_gateway`, `workflow_operations`, and `system_health`; `PUBLIC`, `INTERNAL`, and `RESTRICTED`; bounded administrative/internal channels and purposes.

No wildcard domain, classification, actor, provider, or purpose grant exists.

## E. Acceptance matrix

| ID | Test function | Expected | Actual evidence | Result |
|---|---|---|---|---|
| T01 | `test_t01_unknown_actor` | `DENIED/UNKNOWN_ACTOR`; no adapter | Exact status/error; `last_context=None`; dedicated output `ok` | PASS |
| T02 | `test_t02_production_environment` | `DENIED/ENVIRONMENT_DENIED`; no adapter | Production rejected before invocation; output `ok` | PASS |
| T03 | `test_t03_unknown_capability` | `DENIED/UNKNOWN_CAPABILITY` | Exact normalized error; output `ok` | PASS |
| T04 | `test_t04_caller_cannot_select_metrics_provider` | Caller cannot route provider | Extra `provider=supabase` rejected by strict schema; output `ok` | PASS |
| T05 | `test_t05_authorized_administrator_retrieval` | Success with provenance/audit | Active metric, local adapter identity, evidence ID, TG-P02 permission version; output `ok` | PASS |
| T06 | `test_t06_authorized_budly_bounded_retrieval` | Budly receives permitted metric only | `system.health.status` returned as `PUBLIC`; output `ok` | PASS |
| T07 | `test_t07_restricted_metric_denied_to_budly` | Restricted value excluded/denied | Successful empty result; restricted diagnostic absent from serialized response; output `ok` | PASS |
| T08 | `test_t08_restricted_metric_allowed_to_administrator` | Authorized administrator receives restricted metric | Restricted synthetic item returned; output `ok` | PASS |
| T09 | `test_t09_unauthorized_domain` | `DENIED/DATA_SCOPE_DENIED` | Exact normalized denial; output `ok` | PASS |
| T10 | `test_t10_malformed_input` | `INPUT_VALIDATION_FAILED` | Invalid limit denied; adapter untouched; metric domain retained in minimized audit; output `ok` | PASS |
| T11 | `test_t11_superseded_metric_excluded` | Superseded item absent | `SUCCESS` with empty items; output `ok` | PASS |
| T12 | `test_t12_missing_provenance` | `FAILED/OUTPUT_VALIDATION_FAILED` | Missing source rejected; no result; output `ok` | PASS |
| T13 | `test_t13_adapter_failure` | `FAILED/ADAPTER_FAILURE` | Deterministic exception normalized; no result; output `ok` | PASS |
| T14 | `test_t14_unavailable_adapter` | `UNAVAILABLE/TOOL_UNAVAILABLE` | Exact status/error; no fallback or result; output `ok` | PASS |
| T15 | `test_t15_empty_valid_result` | `SUCCESS`, `items=[]` | Exact empty success; output `ok` | PASS |
| T16 | `test_t16_result_limit` | At most one item | Two requested, maximum one returned; output `ok` | PASS |
| T17 | `test_t17_correlation_preservation` | Correlation preserved in request/result/audit | All IDs matched; audit records metric domain; output `ok` | PASS |
| T18 | `test_t18_context_injection_does_not_reach_adapter` | Extra context rejected/minimized | Customer-email field rejected; adapter context remains `None`; output `ok` | PASS |
| T19 | `test_t19_disabled_capability` | `DENIED/CAPABILITY_DISABLED` | Exact denial; adapter untouched; output `ok` | PASS |
| T20 | `test_t20_tg_p01_regression_preservation` | TG-P01 remains 20/20 | Nested TG-P01 suite ran 20 and succeeded; dedicated TG-P01 rerun also 20/20 | PASS |

## F. Regression

Commands and final results:

```text
python -m unittest tests.test_tg_p01_tool_gateway -v
Ran 20 tests in 0.003s — OK

python -m unittest tests.test_tg_p02_operational_metrics -v
Ran 20 tests in 0.006s — OK

python -m unittest discover -s tests -v
Ran 244 tests in 4.258s — OK
```

The full suite used PHP 8.2.33 on PATH for the existing two PHP-backed wrapper tests. No PHP file was modified.

One test-harness correction was made before final evidence: the TG-P01 test class import moved inside T20 so the dedicated TG-P02 module reports exactly 20 tests rather than also discovering the imported TG-P01 class. No gateway behavior changed for that correction.

## G. Security confirmation

- No production system accessed.
- No production credentials used or created.
- No customer PII or customer analytics used.
- No production metrics fetched.
- No external deployment or public endpoint created.
- No database migration created or executed.
- No production n8n access.
- No production Supabase read or write.
- No production WooCommerce access.
- No production Cloudflare change.
- All metrics are deterministic synthetic fixtures.
- Retrieval has no side effects and triggers no action, recommendation, alert, restart, campaign, or provider change.
- No subsequent capability was implemented.

## H. Deviations

No deviations.

## I. Known limitations

- Local JSON fixtures and process-local audit evidence only.
- One local metrics adapter and no fallback.
- Three deterministic time-window names; fixtures currently represent `current_snapshot` only.
- Explicit prototype actor-type grants, not production identity integration.
- No ingestion, historical analytics, aggregation engine, interpretation, forecasting, alerting, dashboards, or action automation.

## J. Final classification

**TG-P02 PASS — READY FOR MATT-003 ACCEPTANCE**

This report does not authorize another capability, commit, deployment, or production action.
