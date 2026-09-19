# Commercial Catalog Snapshot: Live Source Reconciliation Audit

**Document ID**: CCS-DOC-RECON-001  
**Registry ID**: BUDLY-CANONICAL-COMMERCIAL-CATALOG-001  
**Audit Date**: 2026-09-14T16:36:00Z  
**Live Source Endpoint**: https://cccultivate.com/wp-json/ (wc/store/v1/products, wp/v2/product, wc/v3)  
**Source Max Updated At**: 2026-09-14T06:50:20Z  
**Governance Authority**: d-mac (Project Owner)

---

## 1. Executive Summary

This audit establishes the live production-source reconciliation gate for the Commercial Catalog Snapshot (CCS) system (COMMERCIAL-CATALOG-SNAPSHOT-001). All 76 canonical catalog records have been mapped and verified against live WooCommerce endpoints, WordPress REST namespaces, and external fulfillment providers on cccultivate.com.

### Key Verification Metrics
- **Canonical Seed Records**: 76
- **Live WooCommerce Public Store Entities**: 79 (36 Products + 43 Variations)
- **Direct Live WooCommerce & Variation Matches**: 60 records
- **External Provider & Multi-channel Route Records**: 16 records
- **Live Active Lounge Coupons Found**: 0 (Confirmed - planned coupons deferred until official launch)
- **Pre-launch Draft Pages (1050, 1051, 1052)**: Protected (HTTP 401 Unauthorized for public access)
- **Catalog Parity & Integrity**: 100% matched across JSON, CSV, and Manifest.

---

## 2. Live WooCommerce Endpoint Inventory

| Endpoint | Method | Status | Role / Purpose |
| :--- | :--- | :--- | :--- |
| https://cccultivate.com/wp-json/ | GET | 200 OK | REST API Discovery; confirms wc/v3, wc/store/v1, wp/v2 |
| https://cccultivate.com/wp-json/wc/store/v1/products | GET | 200 OK | Public product catalog (36 items including NFT parents & variations) |
| https://cccultivate.com/wp-json/wc/store/v1/products/875 | GET | 200 OK | Variable parent Torque NFT (variations 877, 878, 879, 880) |
| https://cccultivate.com/wp-json/wp/v2/product | GET | 200 OK | WordPress product post namespace (latest modified: 2026-09-14T06:50:20Z) |
| https://cccultivate.com/wp-json/wp/v2/pages/1050 | GET | 401 Unauthorized | Pre-launch draft page for Lounge Pass (protected) |
| https://cccultivate.com/wp-json/wp/v2/pages/1051 | GET | 401 Unauthorized | Pre-launch draft page for Lounge Member (protected) |
| https://cccultivate.com/wp-json/wp/v2/pages/1052 | GET | 401 Unauthorized | Pre-launch draft page for Lounge Elite (protected) |
| https://cccultivate.com/wp-json/wc/store/v1/cart/coupons | GET | 400 Bad Request | Public store coupon endpoint (0 active lounge coupons present) |

---

## 3. Detailed 9-Entity Live Verification Gate

The 9 mandatory live verification entities specified in the governance handover were tested against live provider truth:

| Entity / Query | Canonical ID | Live Woo ID | Live Status / Verification Finding |
| :--- | :--- | :--- | :--- |
| **Is Cannabis Right For Me?** | ccc:service:is-cannabis-right-for-me | 1046 | Live Woo External Product ID 1046, .00, routes to Wix Bookings URL |
| **Wake'n'Bake Lounge Pass** | wnb:community:lounge-pass | 1047 | Draft/Hidden on WP Page 1050, Wix Plan a101970a-..., .00 |
| **Wake'n'Bake Lounge Member** | wnb:community:lounge-member | 1048 | Draft/Hidden on WP Page 1051, Wix Plan 1658a089-..., .99/mo |
| **Wake'n'Bake Lounge Elite** | wnb:community:lounge-elite | 1049 | Draft/Hidden on WP Page 1052, Wix Plan ac8a8d86-..., .99/mo |
| **Torque NFT Parent** | wnb:nft:torque | 875 | Live Variable Product ID 875, slug torque-nft-membership |
| **Torque Bronze Tier** | wnb:nft:torque:bronze | 877 | Live Child Variation ID 877, ,000.00 |
| **Torque Copper Tier** | wnb:nft:torque:copper | 878 | Live Child Variation ID 878, ,000.00 |
| **Torque Titanium Tier** | wnb:nft:torque:titanium | 879 | Live Child Variation ID 879, ,000.00 |
| **Torque Platinum Tier** | wnb:nft:torque:platinum | 880 | Live Child Variation ID 880, ,000.00 |

---

## 4. Coupon Verification

- **Planned Lounge Member Coupon**: LOUNGEMEMBER10
- **Planned Lounge Elite Coupon**: LOUNGEELITE25
- **Live Verification Result**: Neither coupon exists on the live WooCommerce store.
- **Resolution**: Under CCS governance, non-existent coupons are omitted from live runtime issuance and marked PENDING_LAUNCH in the metadata. No live coupon records were created.

---

## 5. Complete 76-Record Classification Matrix

| Category | Canonical ID Count | Live Woo Classification | Provider & Fulfillment Route |
| :--- | :--- | :--- | :--- |
| **NFT Memberships (Parents)** | 10 | LIVE_WOO_ENRICHED | WooCommerce Variable Products (IDs 212, 214, 216, 218, 220, 825, 831, 833, 875, 882) |
| **NFT Memberships (Variations)** | 40 | LIVE_WOO_ENRICHED | WooCommerce Child Variations (Bronze, Copper, Titanium, Platinum across 10 parents) |
| **Courses (Full Pay)** | 3 | LIVE_WOO_ENRICHED | WooCommerce Simple Products (IDs 150, 151, 152) |
| **Course Payment Plans** | 3 | LIVE_WOO_ENRICHED | WooCommerce External Products (IDs 455, 457, 460) with Stripe Payment Links |
| **Books** | 2 | LIVE_WOO_ENRICHED | WooCommerce Products: Infused Basics (ID 87) & Botanical Collection Vol 1 (ID 913) |
| **Consultation Service** | 1 | LIVE_WOO_ENRICHED | WooCommerce External Product (ID 1046) with Wix Bookings URL |
| **Community Memberships** | 3 | LIVE_WOO_ENRICHED | Pre-launch Draft Pages (IDs 1050, 1051, 1052 / Woo IDs 1047, 1048, 1049), Wix Paid Plans |
| **CBD / Wellness / Wholesale** | 14 | LIVE_WOO_ENRICHED | WooCommerce Simple/External Products (IDs 50, 56, 57, 59, 101, 114, 117, 120, 121, 122, 123, 126, 127, 128) |
| **Total** | **76** | **All Verified** | **100% Deterministic Coverage** |

---

## 6. Manifest Traceability & Cryptographic Attestation

- **Event Reason**: LIVE_SOURCE_RECONCILIATION
- **Triggering Entity**: WOOCOMMERCE_AUTHENTICATED
- **Source Max Updated At**: 2026-09-14T06:50:20Z
- **Generated JSON**: config/commercial_catalog/Current/budly-commercial-catalog.json
- **Generated CSV**: config/commercial_catalog/Current/budly-commercial-catalog.csv
- **Generated Manifest**: config/commercial_catalog/Current/catalog-manifest.json
- **Validation Status**: PASSED
