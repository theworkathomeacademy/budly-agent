# Budly v1.3.4 traceability matrix

| Requirement ID | Ratified source | Required behavior | Existing implementation | v1.3.4 action | Test evidence |
|---|---|---|---|---|---|
| V134-VERSION | RP-001 release identity; TB-001 observability | Report application, schema, and active rule versions | Plugin v1.3.0; schema v1.1.0 | Advance to 1.3.4/1.2.0; add diagnostics | `test_version_reporting_and_active_rule_versions`; WordPress contract test |
| V134-BOUNDARIES | TB-001 §§5-6 | Explicit modular services and typed policy outcomes | `SalesAgent`, `ConversationService`, SecureMemory services | Preserve services; add governed configuration/evidence boundary | Existing sales and conversation tests |
| V134-QUAL | TB-001 §5.5 | Explainable qualification with stored evidence | Weighted score and audit only | Version thresholds/weights; persist objective, inputs, result, action | `test_qualification_preserves_governed_evidence` |
| V134-REC | TB-001 §5.6 | Filter catalog, rank fit, record provenance | Deterministic matching | Server-authoritative evaluation persists eligibility, exclusions, selection, confidence, and rule version | `DecisionService`; ten staging scenarios |
| V134-NOMATCH | TB-001 qualification/recommendation outcomes | Safe no-match without fabrication | Returned `None` and audit event | Persist governed no-match and clarification/human-help action | `test_safe_no_match_is_recorded_and_never_fabricates` |
| V134-ESC | TB-001 §§5.4, 5.9 | Escalate uncertain/restricted matters with evidence | Escalation table and audit | Persist evidence and audit correlation | `test_escalation_preserves_evidence_and_audit_link` |
| V134-CONFIG | TB-001 §§3, 5.9 | Policy-as-code and historical provenance | Scattered class constants/config files | Add validated `bros_v1_3_4.json` and active versions | `test_configuration_selection_is_idempotent` |
| V134-AUDIT | TB-001 §3 and audit data architecture | Significant decisions auditable | Append-only ordinary audit writes | Add `decision.*` audit events with decision IDs | Escalation/audit linkage test |
| V134-ADMIN | ADS-001; TB-001 admin dashboard | Authorized operational review | Health and audit admin APIs | Bounded/filterable `/admin/decisions` with audited access | HTTPS role/filter/pagination staging matrix |
| V134-MIGRATION | DB-001; RP-001 | Additive, safe, recoverable schema | Idempotent `dbDelta`; SQLite `IF NOT EXISTS` | Add two indexed evidence/config tables | WordPress schema contract; idempotency test |
| V134-CONSENT | TB-001 §§5.2, 14; Secure Memory Assets 1-5 | Consent remains fail-closed and independent | Accepted v1.3.0 SecureMemory | Writer requires consent plus server-owned session/conversation context | Consent-restricted and verified-customer scenarios |
| V134-IDENTITY | TB-001 §5.1; Secure Memory Assets 1-5 | Verified identity and session ownership | Accepted SecureMemory identity/session services | Preserved unchanged | Existing authorization and cross-customer tests |
| V134-MEMORY | TB-001 §5.3; Secure Memory Assets 1-5 | Consent-bound customer memory | Accepted SecureMemory services | Preserved unchanged | Existing Phase 5/6 tests |
| V134-CONVERSATION | TB-001 §5.4 | Guided guarded conversation | `ConversationService` | Connect existing outcomes to evidence via `SalesAgent` | Conversation no-match and regression tests |
| V134-CATALOG | TB-001 §5.6 | Approved catalog only | `products.json` allowlist | Version allowlist and record exclusions | Recommendation evidence test |
| V134-SECURITY | TB-001 §14; Secure Memory Asset 2 | Authorization, isolation, CSRF, append-only audit | Accepted Gates A-E implementation | Preserve; protected admin read only | Existing Phase 5-9 security tests |

Actual implementation locations: `src/sales_agent.py`, `src/conversation_service.py`, `config/bros_v1_3_4.json`, `Decision/DecisionService.php`, `Decision/DecisionRepository.php`, `Database/Migrator.php`, `Admin/AdminRepository.php`, `Admin/AdminService.php`, `Api/Routes.php`, `assets/budly-sales.js`, and `tests/test_bros_v1_3_4.py`.
