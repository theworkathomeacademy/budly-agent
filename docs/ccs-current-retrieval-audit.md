# COMMERCIAL-CATALOG-SNAPSHOT-001: Current Retrieval Audit

**Document ID**: `DOCS-CCS-AUDIT-001`  
**Version**: 1.0  
**Date**: 2026-09-14  
**Governing Standard**: CCS-001, CCS-002, CCS-003  
**Status**: COMPLETE (Phase 1 Baseline)  

---

## 1. Executive Summary

An exhaustive audit of the `budly-agent` repository was conducted to identify all current commercial data sources, hardcoded commercial facts, retrieval adapters, prompt injection rules, alias maps, and fallback behaviors.

Prior to `COMMERCIAL-CATALOG-SNAPSHOT-001`, commercial retrieval was fragmented across:
1. **Live WooCommerce Store API** (`/wp-json/wc/store/v1/products`), which lacks authenticated access, omitting drafts, private products, and unreleased community tiers.
2. **Static JSON Configuration Files** (`canonical_catalog.json`, `products.json`, `product_facts.json`, `commercial-knowledge-v1.0.json`).
3. **Hardcoded System Prompt Rules** in `src/budly_runtime/production_runtime.py` specifying obsolete prices and tier definitions.
4. **Hardcoded Alias Dictionaries** in `src/budly_runtime/production_knowledge.py`.
5. **Decoupled Recommendation Routers** in `src/sales_agent.py` and `SOCIAL-TO-SALE-001/recommendation_router.py`.

This audit establishes the baseline for the canonical Commercial Catalog Snapshot system.

---

## 2. Inventory of Current Commercial Retrieval Sources

| Source Component | File Path | Authority Domain | Mechanism | Limitations & Vulnerabilities |
|---|---|---|---|---|
| **Live Store API Caller** | `src/budly_runtime/production_knowledge.py:108-238` | Product prices, stock, names | Unauthenticated GET to `https://cccultivate.com/wp-json/wc/store/v1/products?per_page=100` | Excludes draft, hidden, and unreleased products (e.g. Woo 1047-1049). Unauthenticated, latency on turn. |
| **Approved Policy Adapter** | `src/budly_runtime/production_knowledge.py:318-358` | Policy records | Loads `config/policies.json` & `config/products.json` | Requires `owner_approved` status; links-only validation for products. |
| **Commercial Knowledge JSON** | `config/budly_runtime/commercial-knowledge-v1.0.json` | Ecosystem entities, feature truth, offer relationships | Loaded by `ApprovedRepositoryKnowledgeAdapter` | Static file; contains outdated Wix domain references and manual offer relationships. |
| **Canonical Catalog Seed** | `config/canonical_catalog.json` | 72 Canonical catalog entities | Static JSON registry | Preproduction baseline; missing live synchronization, CSV generator, and manifest hashing. |
| **Product Allowlist & Facts** | `config/products.json`, `config/product_facts.json` | Product allowlist, categories, formats | Static JSON loaded by `SalesAgent` | Manual dual maintenance; price ranges hardcoded in facts. |
| **Hardcoded Prompt Pricing & Tiers** | `src/budly_runtime/production_runtime.py:261-271` | System prompt instruction text | String injection into OpenAI package | Hardcoded pricing strings and superseded membership rules (e.g. Silver/Gold/OG) embedded directly in code. |
| **Synonym & Keyword Map** | `src/budly_runtime/production_knowledge.py:126-162` | Query token expansion | Static in-memory dictionary | Semantic collisions (e.g. mapping `membership` to `nft` / `legends` without distinguishing Community tiers). |
| **Tool Gateway & Registry** | `src/budly_runtime/tool_gateway.py` | `knowledge.retrieve` capability | Capability-governed tool execution | Clean authorization boundary; ready to bind to canonical snapshot loader. |
| **Recommendation Engine** | `src/sales_agent.py:369-436` | Product scoring & ranking | In-memory tag matching against `config/products.json` | Independent ranking pipeline not yet unified with canonical catalog IDs. |
| **Social-to-Sale Conversion Spine** | `SOCIAL-TO-SALE-001/recommendation_router.py` | Social intent routing & CTA | JSON CTA registry matching | Maps intents to canonical product IDs; needs binding to current snapshot. |
| **Ephemeral Session Store** | `src/budly_runtime/production_runtime.py:90-126` | Turn memory | In-memory LRU session cache | Bounded process memory; does not store durable customer PII. |
| **Safe Fallback Handler** | `src/budly_runtime/production_runtime.py:514-523` | Conversational safety | `safe_no_match`, `legacy_guided_flow` | Safe fallback active on validation failure or missing knowledge. |

---

## 3. Analysis of Specific Hardcoded Knowledge Contradictions

### 3.1. Community Memberships vs. Legends NFT Memberships
- **Current Prompt Rule** (`production_runtime.py:268`): Hardcoded "Silver Legend ($3,000), Gold Legend ($5,000), and Legend OG ($10,000)".
- **Canonical Approved Reality**: Wake'n'Bake Legends NFT memberships have 4 tiers: Bronze ($5k), Copper ($10k), Titanium ($20k), Platinum ($40k) across 10 characters.
- **Wake'n'Bake Community Memberships**: Lounge Pass ($0), Lounge Member ($9.99/mo), Lounge Elite ($24.99/mo) are unreleased community subscriptions (`APPROVED_NOT_RELEASED`, `customer_purchasable=false`).
- **Required Fix**: Entity resolution must strictly isolate `wnb:community:*` from `wnb:nft:*`.

### 3.2. Infused Basics Book vs. Course Hallucination
- **Current State**: `config/canonical_catalog.json` correctly classifies `ccc:book:infused-basics` as `BOOK` ($40.00).
- **Required Fix**: Ensure all prompt rules, synonym maps, and retrieval adapters treat Infused Basics exclusively as a book, never as a course or free trial.

### 3.3. Consultation Service ("Is Cannabis Right For Me?")
- **Current State**: Represented in Wix Bookings ($75) with public URL `https://wakenbakelounge.com/service-page/is-cannabis-right-for-me`, corresponding to Woo ID 1046.
- **Required Fix**: Authoritatively mapped as `ccc:service:is-cannabis-right-for-me` with verified fulfillment and safe framing.

---

## 4. Preservation & Migration Strategy

1. **Legacy Retrieval Preservation**: Retain existing adapters and endpoints during development.
2. **Canonical Snapshot Implementation**: Build complete pipeline in `src/budly_runtime/commercial_snapshot/`.
3. **Feature-Gated Cutover**: Allow side-by-side verification before retiring legacy Store API polling.
4. **Zero Downtime**: Snapshot artifacts (`budly-commercial-catalog.json`, `budly-commercial-catalog.csv`, `catalog-manifest.json`) are generated into `Staging/` and published atomically to `Current/`.

---
