# SOCIAL-TO-SALE-002 — STS-2 Recommendation to Attributed Revenue

Date: 2026-09-10  
Owner: d-mac  
Status: BLOCKED — production version drift discovered before deployment

## 1. Existing architecture discovered

- WordPress already persists governed recommendation decisions with conversation, session, journey, product, and STS attribution evidence.
- WooCommerce order metadata was readable by the existing Budly commerce adapter, but no component populated the Budly identifiers on an order.
- The existing `order.updated` n8n workflow verifies WooCommerce HMAC signatures, normalizes `bros.revenue_event.v1`, applies an idempotency guard, and invokes `bros_ingest_revenue_event`.
- Supabase `public.revenue_events.event_payload` already stores the complete normalized event. No Supabase schema migration is required.
- Existing WordPress commerce-event and order-link storage can derive conversion state from authoritative WooCommerce revenue evidence. No WordPress schema migration is required.

## 2. Minimum bridge chosen and why

The server issues a non-secret, bounded `sts2_<32 hex>` correlation ID plus HMAC only after an authoritative `recommended` decision. The full association remains in a short-lived server-side transient. The recommendation URL carries only the signed opaque token. WooCommerce validates the signature and selected-product binding, copies correlation/conversation/decision identifiers into non-commercial order metadata, and clears the browser/session token after order linkage.

Both guided and conversational Ask Budly recommendations use the same governed DecisionService and bridge. Customer-supplied values cannot select a different product, change price, create revenue, or declare conversion.

The n8n normalizer copies only validated Budly metadata into `commerce_correlation` in the existing normalized event. Supabase stores it inside the existing JSON event payload, preserving the current RPC, HMAC, idempotency, PII exclusions, and service-role boundary.

## 3. Canonical changes

- Branch: `sts-2-attributed-revenue`
- Implementation commit: `745d6c2e29147ebbb80148216a73c9c90856b54d`
- Plugin candidate version: `1.8.2`
- Commerce rules version: `commerce-correlation-1.8.2.0`
- Changed files: 27 (1,009 insertions, 34 deletions)
- Principal additions:
  - `includes/Commerce/CommerceCorrelationService.php`
  - `deploy/n8n/REV-Woo-Order-Event-Intake-STS2.json`
  - `scripts/patch_sts2_revenue_workflow.py`
  - STS-2 PHP, Python, and Node tests
- The proven STS-1 branch was not modified destructively.

## 4. Tests

- Full Python regression: 257 passed, 0 failed.
- STS-2 PHP runtime correlation harness: passed.
- STS-2 Node revenue normalizer runtime harness: passed.
- JavaScript syntax: passed.
- PHP syntax for the changed conversational proxy: passed.
- Version consistency: passed for 1.8.2.
- Repository validation: passed (269 previously tracked files at validation time).
- `git diff --check`: no whitespace errors; only existing Windows line-ending warnings.
- Two independent deterministic builds were byte-identical:
  - Size: 765,193 bytes each
  - SHA-256: `873AA712AC7CDC714BBFFB26FD2D9FB798E08F4BB965AE3ADBDCC6B549FAE744`

## 5. Deployment state

No STS-2 production deployment was performed.

Pre-deployment inspection on 2026-09-10 found the active production plugin at `cccultivate.com` is **Budly Sales Agent 1.8.3**, not the authorized/recovered 1.8.1 baseline. The current STS-2 candidate is 1.8.2; installing it would be an unreviewed production downgrade.

A read-only local search found no canonical 1.8.3 source or package under the Codex project directories. Therefore the 1.8.3 delta cannot presently be reconciled or safely rebased. The public `/ask-budly/` endpoint remained HTTP 200. No plugin, WooCommerce, n8n, Supabase, catalog, pricing, or production data was changed.

## 6. Controlled production evidence

Not executed. Production deployment was stopped before upload because the live 1.8.3 source/provenance is unavailable. No checkout or financial action was attempted.

## 7. Revenue attribution result

The deterministic path is implemented and tested locally, but no production order or revenue event was generated. The required production chain is therefore unproven.

Exact missing links:

- STS-2 code reconciled with the currently deployed 1.8.3 source
- STS-2 WordPress deployment
- STS-2 n8n workflow deployment/activation verification
- controlled attributed WooCommerce order
- persisted BROS revenue event carrying the same correlation
- authoritative conversion record and attributed revenue amount

## 8. Genuine owner authorization / provenance boundary

This is not yet the payment boundary. It is a production source-of-truth boundary: proceeding requires the canonical source or rollback package for the deployed Budly Sales Agent 1.8.3, or explicit owner direction identifying the authorized 1.8.3 source. Overwriting it with 1.8.2 would discard an unknown production change.

Once that drift is reconciled and deployment gates are green, a real checkout will still stop at the owner payment/financial authorization boundary unless d-mac explicitly performs or authorizes that transaction.

## 9. STS-2 disposition

**STS-2: BLOCKED**

Reason: production is ahead of the recovered canonical baseline and its 1.8.3 source/provenance is unavailable. No PASS is claimed.

## 10. STOP

Stopped before any production mutation, n8n change, or financial transaction.
