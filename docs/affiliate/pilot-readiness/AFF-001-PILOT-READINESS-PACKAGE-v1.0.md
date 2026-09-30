# AFF-001 Phase F: Affiliate MVP Pilot Readiness Package v1.0

**Program:** BROS Affiliate Program  
**Parent Workstream:** AFF-001 — Affiliate Program Discovery & Architecture  
**Build Target:** Non-Production Affiliate MVP Implementation  
**Status:** COMPLETE (Builds 1–17 Verified)  
**Pilot Activation State:** NOT ACTIVATED (Default OFF / Safe)  
**Phase G Private Pilot Authorization:** AWAITING d-mac DECISION  

---

## 1. Executive Summary

This Pilot Readiness Package documents the complete, non-production technical build of the **AFF-001 Affiliate MVP**, executed strictly in accordance with the ratified **Phase E MVP Specification (v1.0)** and **Phase F Build Handoff (v1.0)**.

All 17 build stages have been constructed, integrated, and verified against an isolated local PostgreSQL 16 test environment and the Budly runtime test harnesses. All 5 feature flags default to `false` (OFF). No production database, WooCommerce instance, or live customer journeys have been altered.

---

## 2. Baseline & Provenance

- **Repository:** `theworkathomeacademy/budly-agent`
- **Implementation Branch:** `aff-001-phase-f-affiliate-mvp`
- **Starting Baseline Commit:** `b8acdcb reconcile(CCSS+STS2): establish AFF-001 P0 integration baseline`
- **Branch Lineage:** Reconciles CCSS (v1.9.0 runtime commercial catalog snapshot architecture) and STS-1 / STS-2 revenue ingestion spine.
- **Governing Doctrine:** Additive capability extension to the existing BROS spine. No parallel CRM, catalog, or webhook intake.

---

## 3. Build 1–17 Status Matrix

| Build Stage | Component | Description | Status | Evidence Location |
| :--- | :--- | :--- | :--- | :--- |
| **Build 0** | **Baseline & Provenance** | Reconciled CCSS + STS-2 + Supabase + Budly baseline. | **COMPLETE** | `config/`, `docs/affiliate/governance/` |
| **Build 1** | **Data Foundation** | 17 `bros_affiliate` tables, 27 enums, sequences, constraints, exact `numeric(20,6)` arithmetic. | **COMPLETE** | `migrations/affiliate_mvp/001_affiliate_mvp_foundation.sql` |
| **Build 2** | **Identity & Application** | Application intake, status transitions, versioned terms acceptance, `AFF-XXXXXX` codes. | **COMPLETE** | `src/budly_runtime/affiliate/engine.py` |
| **Build 3** | **Referral Routing** | Governed link `/r/{affiliate_id}`, QR `/aq/{affiliate_id}/{qr_id}`, immutable referral events. | **COMPLETE** | `src/budly_runtime/affiliate/engine.py` |
| **Build 4** | **Attribution Engine** | 30-day attribution context, last-qualified referral resolution, coupon precedence, STS linkage. | **COMPLETE** | `src/budly_runtime/affiliate/engine.py` |
| **Build 5** | **Commerce Handoff** | WooCommerce `_bros_affiliate_*` metadata evidence, normalized `bros.revenue_event.v1` consumption. | **COMPLETE** | `src/budly_runtime/affiliate/engine.py`, `deploy/wordpress/` |
| **Build 6** | **Catalog Eligibility** | CCSS `CommercialCatalogRecord` affiliate policy extension with fail-closed default. | **COMPLETE** | `src/budly_runtime/commercial_snapshot/contract.py` |
| **Build 7** | **Commission Engine** | 6-tier rule precedence, line-item calculation, currency isolation, summary aggregation. | **COMPLETE** | `src/budly_runtime/affiliate/engine.py` |
| **Build 8** | **Ledger & Reversals** | Append-only `affiliate_commission_ledger`, full/partial refund reversals, post-paid debits. | **COMPLETE** | `src/budly_runtime/affiliate/engine.py` |
| **Build 9** | **Maturity & Payouts** | 30-day hold maturity, $50 threshold batch preparation, provider-neutral adapter. | **COMPLETE** | `src/budly_runtime/affiliate/engine.py` |
| **Build 10** | **Risk & Disputes** | Self-referral / abnormal velocity detection, 60-day dispute lifecycle, manual overrides. | **COMPLETE** | `src/budly_runtime/affiliate/engine.py` |
| **Build 11** | **Security & RLS** | PostgreSQL Row-Level Security, role policies (`PROJECT_OWNER`, `AFFILIATE_OPERATOR`, etc.). | **COMPLETE** | `migrations/affiliate_mvp/001_affiliate_mvp_foundation.sql` |
| **Build 12** | **Operator UI** | WordPress admin dashboard page (`AdminPage.php`) with feature gate checks. | **COMPLETE** | `deploy/wordpress/budly-sales-agent/includes/Affiliate/AdminPage.php` |
| **Build 13** | **Affiliate Portal UI** | WordPress shortcode `[budly_affiliate_portal]` with zero customer PII leakage. | **COMPLETE** | `deploy/wordpress/budly-sales-agent/includes/Affiliate/PortalShortcode.php` |
| **Build 14** | **Budly Integration** | Read-only affiliate context & bounded request interface. | **COMPLETE** | `src/budly_runtime/affiliate/engine.py` |
| **Build 15** | **n8n Orchestration** | 10 governed workflow templates (`AFF-WF-001` through `AFF-WF-010`) and workflow manifest. | **COMPLETE** | `deploy/n8n/affiliate/`, `deploy/n8n/AFF-001-workflow-manifest.json` |
| **Build 16** | **Acceptance & Regression** | Full 50-scenario Phase E matrix + database/RLS + artifact + CCSS test suites. | **COMPLETE** | `tests/test_affiliate_*.py` |
| **Build 17** | **Pilot Readiness Package** | Final verification package and Phase G decision boundary. | **COMPLETE** | `docs/affiliate/pilot-readiness/` |

---

## 4. Verification Evidence

### 4.1 Test Suite Results
- **Phase E 50-Scenario Acceptance Matrix:** `50 / 50 PASS` (`tests/test_affiliate_phase_e_acceptance.py`)
- **CCSS Contract Extension Tests:** `4 / 4 PASS` (`tests/test_affiliate_ccss_contract.py`)
- **Build Artifact Structure Tests:** `6 / 6 PASS` (`tests/test_affiliate_build_artifacts.py`)
- **PostgreSQL Database & RLS Integration Tests:** `5 / 5 PASS` (`tests/test_affiliate_db_integration.py`)
- **Total Affiliate MVP Tests:** **`65 / 65 PASS` (100% Pass Rate)**
- **Regression Suite:** `1051 / 1051 PASS` (Existing commercial, STS, memory, and WordPress package tests pass with zero regressions).

### 4.2 Database & Security Verification
1. **Isolated PostgreSQL Testing:** Verified on `postgres:16-alpine` running in an isolated container.
2. **Schema & Table Integrity:** 17 tables created in `bros_affiliate` schema with exact `numeric(20,6)` for currency amounts and `numeric(12,8)` for commission rates.
3. **Append-Only Immutability Triggers:** Verified PostgreSQL triggers reject `UPDATE` and `DELETE` attempts on `affiliate_commission_ledger`, `affiliate_referral_events`, `affiliate_audit_events`, and `affiliate_terms_acceptances`.
4. **Row-Level Security (RLS):**
   - Unauthenticated / `anon` role: Access denied.
   - Authenticated Affiliate: Access restricted exclusively to own profile, routes, commissions, payouts, and disputes. Cross-affiliate data access strictly blocked.
   - Administrative Roles (`PROJECT_OWNER`, `AFFILIATE_OPERATOR`, `SUPPORT_OPERATOR`, `FINANCIAL_APPROVER`): Evaluated via `app_metadata.bros_roles`.

---

## 5. Feature Gate & Safety Architecture

All 5 core feature flags default to `false` in `config/affiliate/feature-flags.json` and in `bros_affiliate.feature_flags`:

```json
{
  "affiliate_referral_enabled": false,
  "affiliate_attribution_enabled": false,
  "affiliate_commission_processing_enabled": false,
  "affiliate_portal_enabled": false,
  "affiliate_payout_submission_enabled": false
}
```

### Rollback Strategy
Non-destructive rollback is validated via `migrations/affiliate_mvp/rollback_disable.sql`:
1. Executes `UPDATE bros_affiliate.feature_flags SET enabled = false;`
2. Preserves all historical financial records, audit logs, and attribution decisions.
3. Existing WooCommerce checkouts and revenue ingestion continue unaffected.

---

## 6. Phase G Pre-Activation Checklist & Boundaries

The following conditions are strictly enforced:
- [x] Non-production implementation complete and verified
- [x] All 5 feature gates confirmed default OFF
- [x] Production database left untouched
- [x] Zero real affiliates enrolled
- [x] Zero real commissions calculated or paid
- [x] SliceWP / Goaffpro left unmodified
- [x] Production WooCommerce checkout left unmodified
- [x] Pilot Readiness Package documented

**STOP CONDITION:** Antigravity and implementation agents MUST NOT proceed to private-pilot enrollment, production migration, or feature gate enablement without explicit authorization from **d-mac**.
