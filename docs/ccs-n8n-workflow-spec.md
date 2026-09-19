# Commercial Catalog Snapshot: n8n Workflow Specification (CCS-003)

**Document ID**: `DOCS-CCS-N8N-001`  
**Version**: 1.0  
**Date**: 2026-09-14  
**Governing Standard**: CCS-001, CCS-002, CCS-003  
**Status**: APPROVED SPECIFICATION — Ready for Non-Production Staging  

---

## 1. Overview & Architecture

The n8n workflow orchestrates the automated commercial catalog snapshot lifecycle. It listens for authenticated WooCommerce webhook events, debounces rapid successive modifications, triggers the complete catalog fetch, joins approved enrichment, executes validation, generates atomic snapshot artifacts (`JSON`, `CSV`, `Manifest`), and signals the Budly runtime to reload its read-only cache.

```
+--------------------------+
| WooCommerce Store Change | (product.created / updated / deleted)
+-------------+------------+
              |
              v (HMAC SHA-256 Webhook)
+-------------+------------+
|  n8n Webhook Listener    | (Signature verification & delivery audit)
+-------------+------------+
              |
              v
+-------------+------------+
| Debounce & Coalescing    | (30-second coalescing window per product batch)
+-------------+------------+
              |
              v
+-------------+------------+
| Full Rebuild Trigger     | (`rebuild_catalog` full authenticated fetch)
+-------------+------------+
              |
              +-----------------------+
              |                       |
              v (Pass)                v (Fail)
+-------------+------------+  +-------+--------------------+
| Atomic Current Publish   |  | Quarantine Staging Build   |
+-------------+------------+  +-------+--------------------+
              |                       |
              v                       v
+-------------+------------+  +-------+--------------------+
| Budly Cache Reload Signal|  | Alerting & Incident Log    |
+-------------+------------+  | (Retain Last-Known-Good)   |
              |               +----------------------------+
              v
+-------------+------------+
| Post-Reload Health Probe | (8 probe queries)
+--------------------------+
```

---

## 2. Webhook Ingestion & Authentication

### 2.1. Qualifying Event Triggers
The workflow triggers on the following WooCommerce webhook topics:
- `product.created`
- `product.updated`
- `product.deleted`
- `product.restored`
- `action.woocommerce_variation_created`
- `action.woocommerce_variation_updated`
- `action.woocommerce_variation_deleted`

### 2.2. Webhook Signature Verification
- **Header**: `X-WC-Webhook-Signature`
- **Algorithm**: `HMAC-SHA256(raw_body, WOOCOMMERCE_WEBHOOK_SECRET)`
- **Rule**: If the signature does not match or is absent, reject with HTTP `401 Unauthorized` and emit a security audit record.
- **Idempotency**: Webhook `X-WC-Webhook-Delivery-ID` is cached for 1 hour to suppress duplicate network deliveries.

---

## 3. Debounce, Coalescing, and Rebuild Execution

### 3.1. Debounce Window
- Sequential changes (e.g. bulk stock or price edits) are coalesced over a **30-second window**.
- A single rebuild execution runs at the close of the debounce window, passing all triggering product IDs in `triggering_entity`.

### 3.2. Full Rebuild Policy
- **Rule**: Rebuilds must ALWAYS fetch the COMPLETE relevant catalog (published, draft, pending, private, variable products, child variations).
- **Zero Partial Patches**: Partial or single-row updates are strictly prohibited to prevent data skew and hash divergence.

---

## 4. Snapshot Generation, Validation & Promotion

1. **Fetch**: Authenticated REST API v3 GET `/wp-json/wc/v3/products` with complete pagination.
2. **Normalize & Enrich**: Map into canonical `CommercialCatalogRecord` schema joined with `APPROVED_ENRICHMENT_REGISTRY`.
3. **Pre-Validation**: Check record invariants (no duplicate canonical IDs, `APPROVED_NOT_RELEASED` not purchasable, valid URLs).
4. **Stage Artifacts**: Generate `budly-commercial-catalog.json`, `budly-commercial-catalog.csv`, and `catalog-manifest.json` into `Staging/`.
5. **Staging File Validation**: Verify CSV/JSON record count parity, SHA256 hashes against manifest, and deserialize JSON records.
6. **Promotion & Archiving**:
   - If validation passes: Copy current version to `Archive/<version>/` and atomically promote `Staging/` to `Current/`.
   - If validation fails: Move `Staging/` to `Quarantine/quarantine-<timestamp>/` with `quarantine-reason.txt`. `Current/` remains untouched.

---

## 5. Cache Reload & Health Probing

1. **Signal**: POST authenticated reload signal to Budly runtime endpoint (`/api/v1/commercial/reload`).
2. **Runtime Verification**: Runtime validates manifest hashes and swaps internal memory index.
3. **Health Probes**: Executes 8 deterministic verification queries:
   - "What is Infused Basics?" -> `ccc:book:infused-basics` (Book, not course)
   - "What is Lounge Member?" -> `wnb:community:lounge-member` (Community membership, unreleased)
   - "What do I get with Lounge Elite?" -> `wnb:community:lounge-elite` (Approved benefits)
   - "Can I buy Lounge Elite?" -> `customer_purchasable=false`
   - "What classes do you offer?" -> Canonical courses
   - "Do you have payment plans?" -> Verified payment routes
   - "Is Cannabis Right For Me?" -> `ccc:service:is-cannabis-right-for-me` ($75 consultation)
   - "Torque" -> `wnb:nft:torque` (Legends NFT)

---

## 6. Scheduled Reconciliation & Failure Recovery

- **Daily Cron Schedule**: `0 3 * * *` (03:00 UTC daily).
- **Drift Detection**: Full rebuild executed daily to detect manual database edits or unpublished variations.
- **Retry Policy**: 3 retries with exponential backoff (10s, 30s, 90s).
- **Alerting**: Failure on the 3rd retry triggers high-priority operational alerting via webhook to admin channel.
- **Last-Known-Good Safety**: At no point does a failure in n8n or WooCommerce overwrite or delete `Current/budly-commercial-catalog.json`.

---
