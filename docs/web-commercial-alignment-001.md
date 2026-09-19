# WEB-COMMERCIAL-ALIGNMENT-001F: Release Identity & Deployment Packaging Gate Record

**Document ID**: `DOCS-ALIGNMENT-001F`  
**Slice ID**: `WEB-COMMERCIAL-ALIGNMENT-001F`  
**Current Production Baseline**: Budly 1.8.8 PRODUCTION ACCEPTED  
**Target Release**: Budly 1.9.0 PRE-AUTONOMY HARDENING (`1.9.0-rc2` Preproduction Package)  
**Status**: READY FOR LIVE DEPLOYMENT (NOT DEPLOYED)  
**Date**: 2026-09-14  

---

## 1. Lifecycle Truth State Summary

| Lifecycle Dimension | Current State | Evidence / Basis |
|---|---|---|
| **`BUILT`** | **YES (Final RC2 Package)** | Canonical catalog ([`config/canonical_catalog.json`](file:///c:/Users/19196/Documents/Budly/budly-agent/config/canonical_catalog.json), 61 verified entries), updated [`CatalogProvisioner.php`](file:///c:/Users/19196/Documents/Budly/budly-agent/deploy/wordpress/budly-sales-agent/includes/Commerce/CatalogProvisioner.php) with fail-closed authorization gate and coupon deferral, verified release identity (`1.9.0-rc2`), and `deploy/wordpress/budly-sales-agent-1.9.0-rc2.zip`. |
| **`TESTED`** | **PASSED (Targeted Suites)** | **76/76 PASSED** across targeted safety, package identity, and commercial regression suites (`tests/test_catalog_provisioner_safety.py`, `tests/test_offer_relationship_001.py`, `tests/test_web_knowledge_001.py`, `tests/test_wordpress_package.py`). |
| **`DEPLOYED`** | **NO** | Zero modifications executed against live production WooCommerce, WordPress, or Wix instances in this pass. |
| **`LIVE`** | **EXISTING ONLY** | 35 existing WooCommerce products verified via live Store API. Live Stripe payment plan buttons verified. `HTTP 200` on `/product/875/` and `HTTP 404` on `/product/torque-nft-membership/` confirmed live. Consultation destination verified `HTTP 200`. New products, draft pages, coupons, and slug changes **not live**. |
| **`PRODUCTION ACCEPTED`**| **NO** | Production baseline remains Budly 1.8.8 PRODUCTION ACCEPTED. |

---

## 2. Release Identity & Packaging Synchronization

1. **Plugin Header**: `Version: 1.9.0-rc2` in `deploy/wordpress/budly-sales-agent/budly-sales-agent.php`.
2. **Package Version Constant**: `define('BUDLY_SALES_VERSION', '1.9.0-rc2');`.
3. **Conversation Proxy User-Agent**: `'User-Agent' => 'BudlySalesAgent/1.9.0-rc2'`.
4. **Release Manifest**: `release-manifest.json` embedded in package declaring `application_version: 1.9.0-rc2`, `release_stage: PREPRODUCTION_RELEASE_CANDIDATE`.
5. **Rollback Baseline Preserved**: `dist/budly-sales-agent-1.8.8.zip` preserved unaltered (SHA256: `3eabf0d67a386c146d7a7743213fd6018fec1cf32b359b37162e7037724fc811`).

---

## 3. Predeployment Live HTTP Evidence

Recorded at `2026-09-14T06:12:45.414438+00:00`:

| Endpoint | Target URL | Live HTTP Status | Latency | Operational Implication |
|---|---|---|---|---|
| **CCC Homepage** | `https://cccultivate.com/` | `HTTP 200 OK` | 134.7ms | Production site fully operational |
| **Ask Budly Page** | `https://cccultivate.com/ask-budly/` | `HTTP 200 OK` | 104.8ms | Production baseline chat entrypoint live |
| **Shop Catalog** | `https://cccultivate.com/shop/` | `HTTP 200 OK` | 1496.9ms | WooCommerce store operational |
| **Torque Old Product** | `https://cccultivate.com/product/875/` | `HTTP 200 OK` | 1805.4ms | Legacy product page active; must NOT redirect before migration |
| **Torque Target Slug** | `https://cccultivate.com/product/torque-nft-membership/` | `HTTP 404 Not Found` | 2387.8ms | Target slug unprovisioned live; confirms gating necessity |
| **Wix Consultation Destination** | `https://wakenbakelounge.com/service-page/is-cannabis-right-for-me` | `HTTP 200 OK` | 299.2ms | External booking destination confirmed live and responsive |

---

## 4. Controlled Deployment Sequence (11 Steps)

1. **Step 1 — Database Backup**: Execute complete SQL dump of WordPress/WooCommerce production database.
2. **Step 2 — Preserve Live 1.8.8**: Back up live `wp-content/plugins/budly-sales-agent/` directory on server.
3. **Step 3 — Record Live State**: Record live plugin version and file hashes.
4. **Step 4 — Stage RC2**: Upload `budly-sales-agent-1.9.0-rc2.zip` to staging/deployment directory on server.
5. **Step 5 — Controlled Code Replacement**: Extract RC2 package into `wp-content/plugins/budly-sales-agent/`.
6. **Step 6 — Plugin Load & Health Verification**: Verify WordPress admin loads plugin, shortcodes execute, and `https://cccultivate.com/ask-budly/` returns `HTTP 200 OK`.
7. **Step 7 — Immediate Health Gate**: If health check fails, immediately roll back to 1.8.8 backup from Step 2.
8. **Step 8 — Controlled Catalog Provisioning**: Execute `wp eval "\Budly\Commerce\CatalogProvisioner::provision_all();" --user=<admin_user>`.
9. **Step 9 — Verify Provisioned Records**: Confirm creation of external consultation product ($75), draft/hidden community products, and draft pages. Confirm coupons remain deferred.
10. **Step 10 — Controlled Torque Slug Migration**: Execute `wp eval "\Budly\Commerce\CatalogProvisioner::migrate_torque_slug();" --user=<admin_user>`.
11. **Step 11 — Post-Migration Path Verification**: Verify `/product/torque-nft-membership/` returns `HTTP 200 OK`, `/product/875/` returns `HTTP 301`, and consultation button routes to Wix.
