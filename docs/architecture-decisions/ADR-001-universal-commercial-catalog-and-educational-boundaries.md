# ADR-001: Universal Commercial Catalog Authority & Educational Knowledge Boundaries

**Status**: APPROVED / ACCEPTED  
**Date**: 2026-09-13  
**Deciders**: Project Owner (BROS Governing Authority)  
**Target Release**: 1.9.0  

---

## 1. Context

Prior to release 1.9.0, Budly's commercial knowledge was fragmented across multiple sources:
- Hardcoded Python system-prompt rules in `production_runtime.py` specifying static prices and tier definitions.
- Static JSON registries (`commercial-knowledge-v1.0.json`, `product_facts.json`, `products.json`).
- Live WooCommerce Store API endpoints.
- Wix CMS platforms hosting community and educational content.

This fragmentation caused production anomalies, including pricing contradictions, the hallucination of a "free course" for Infused Basics, and scripted capability promises with no underlying execution backend.

---

## 2. Decisions

### Decision 1: WooCommerce is the Universal Commercial Catalog
WooCommerce (`cccultivate.com`) is designated as the sole authoritative commercial catalog for:
- Product, book, course, class, service, and membership commercial existence.
- Active customer-facing commercial names and descriptions.
- Live price, sale status, and stock availability.
- Purchasability and purchase destinations.
- One-time purchase vs. recurring subscription classification.
- External payment routing metadata where applicable.

*Rule*: Static Python or JSON pricing must never override live WooCommerce commercial truth.

### Decision 2: Decoupling of Commercial Catalog Authority from Payment Processing
An offer recorded in WooCommerce represents approved commercial truth regardless of whether the transaction is completed via native WooCommerce checkout, Stripe, or a third-party cannabis-friendly subscription processor. The payment processing path is decoupled from catalog authority.

### Decision 3: Separation of Commercial Authority from Rich Educational Content
WooCommerce is the universal *commercial* catalog, but is **NOT** the sole authority for rich educational content. Detailed curriculum, syllabi, narratives, and educational resources may originate from Wix, BROS foundation libraries, or an approved Knowledge Registry with full provenance. The Unified Commercial Knowledge Registry connects rich educational content to the respective WooCommerce commercial entity.

### Decision 4: Epistemic Gating on Unreleased Offers
Owner approval of a commercial concept does not equal customer availability. Unreleased community tiers (e.g., Lounge Pass, Lounge Member, Lounge Elite) and discount codes are classified as `APPROVED_NOT_RELEASED` and must never be presented as purchasable until formally launched in the active commercial catalog.

### Decision 5: Deterministic Capability Gating for Outbound Communication
Budly may only assert outbound capabilities (e.g., sending emails via Brevo under `BREVO-OUTBOUND-001`) when:
1. `SEND_EMAIL.enabled == true`.
2. Provider health is verified in real-time.
3. Customer has provided a valid destination address.
4. Specific consent requirements have been satisfied.
5. Message content falls within approved authority scope.

In the absence of a verified capability, Budly must strictly use non-committal recording phrases (*"I can note your interest for our team"*).

---

## 3. Consequences

### Positive:
- Single source of truth for all pricing, eliminating hallucinated or stale price quotes.
- Clean separation between commercial transactions (WooCommerce) and educational content (Wix/Registry).
- Elimination of false capability claims.
- Safe handling of pre-release business strategies.

### Operational Adjustments:
- Production runtime code must be refactored to remove hardcoded prices and invalid membership tiers.
- Commercial JSON registry must be updated to align with the authority matrix.
- `BREVO-OUTBOUND-001` must be implemented before automated email claims are permitted.
