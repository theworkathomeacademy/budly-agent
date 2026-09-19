# Commercial Catalog Snapshot: Public Catalog Exclusions & Visibility Audit (CCS-006)

**Document ID**: CCS-DOC-EXCL-001  
**Governance Standard**: CCS-006 Public Catalog Visibility & Publication Policy v0.1  
**Registry ID**: BUDLY-CANONICAL-COMMERCIAL-CATALOG-001  
**Audit Date**: 2026-09-15T14:15:00Z  
**Authority**: d-mac (Project Owner)

---

## 1. Executive Summary

In accordance with ratified governance standard **CCS-006**, public customer-facing Budly must not mirror the complete WooCommerce inventory or internal product drafts. Public Budly is authorized to retrieve, recommend, and discuss ONLY commercial entities that are published, publicly visible, actively released, and explicitly classified as udly_visibility = PUBLIC.

### Catalog Inventory Counts
- **Total Internal Canonical Inventory**: **76 records** (Preserved in config/canonical_catalog.json and config/commercial_catalog/Internal/)
- **Total Public Commercial Snapshot**: **73 records** (Generated in config/commercial_catalog/Current/)
- **Total Excluded Records**: **3 records**
- **PRE_RELEASE_ALLOWED Records**: **0 records** (No pre-release exceptions authorized)
- **INTERNAL_ONLY Records**: **0 records**

---

## 2. Excluded Records Audit

The following 3 records are internal-only draft offers and are strictly **EXCLUDED** from the public commercial catalog snapshot:

| Canonical ID | Entity Name | Entity Type | Source Status | Catalog Visibility | Release State | Budly Visibility | Exclusion Reason & Governance Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| wnb:community:lounge-pass | Wake'n'Bake Lounge Pass | COMMUNITY_MEMBERSHIP | DRAFT (Woo 1047) | hidden (WP Page 1050) | APPROVED_NOT_RELEASED | EXCLUDED | **APPROVED_NOT_RELEASED / DRAFT / HIDDEN**: Pre-launch free community membership pass. Unreleased; page 1050 is a protected draft. |
| wnb:community:lounge-member | Wake'n'Bake Lounge Member | COMMUNITY_MEMBERSHIP | DRAFT (Woo 1048) | hidden (WP Page 1051) | APPROVED_NOT_RELEASED | EXCLUDED | **APPROVED_NOT_RELEASED / DRAFT / HIDDEN**: Pre-launch monthly paid community membership (.99/mo). Unreleased; page 1051 is a protected draft; planned coupon LOUNGEMEMBER10 is non-public. |
| wnb:community:lounge-elite | Wake'n'Bake Lounge Elite | COMMUNITY_MEMBERSHIP | DRAFT (Woo 1049) | hidden (WP Page 1052) | APPROVED_NOT_RELEASED | EXCLUDED | **APPROVED_NOT_RELEASED / DRAFT / HIDDEN**: Pre-launch monthly VIP community membership (.99/mo). Unreleased; page 1052 is a protected draft; planned coupon LOUNGEELITE25 is non-public. |

---

## 3. Hidden & Unreleased Product Review

- **Active Hidden Products Requiring Owner Review**: **0**.
  - All 73 public items (10 NFT Parents, 40 NFT Variations, 3 Courses, 3 Payment Plans, 2 Books, 1 Service, 14 CBD lines) are verified as published and publicly accessible on cccultivate.com.
  - The 3 Lounge Community items are the only draft/hidden items in the 76-record inventory.
- **Fail-Closed Retrieval Verification**:
  - DeterministicEntityResolver(public_only=True) strictly fails closed (NO_MATCH) on queries targeting excluded records.
  - CommercialSnapshotLoader loaded in public context holds 0 excluded records, returning None on any direct lookup.
  - Planned coupon codes (LOUNGEMEMBER10, LOUNGEELITE25) are omitted from public metadata.

---

## 4. Internal Canonical Inventory Preservation

The complete 76-record canonical inventory is preserved for:
- Administration and reporting
- Future launch preparation when Project Owner authorizes release
- Verified returning-customer relationship and entitlement resolution (via ReturningCustomerCommercialService)
- Source authority reconciliation
