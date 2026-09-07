# SOCIAL-TO-SALE-001: Phase STS-1 Conversion Spine Foundation

## Mission & Purpose
The primary objective of **SOCIAL-TO-SALE-001 (Phase STS-1)** is to establish the first production-capable conversion spine for the BROS / Budly Ecosystem (Sprint to 100).

```
Social Post (Instagram)
  ↓
Approved CTA (CTA Registry)
  ↓
Attributed Entry Link (Attribution Link Standard)
  ↓
Ask Budly Landing & Intake (Anonymous Journey Initialization)
  ↓
Intent & Topic Recognition (Commercial Taxonomy)
  ↓
Lead Promotion Threshold & Qualification (Deterministic CRM Evaluation)
  ↓
Approved Recommendation Destination (Governed Router)
  ↓
Conversion Journey Record (Native SQLite CRM Persistence)
```

The system proves that a visitor can transition from an Instagram post into the Budly ecosystem, begin a conversation, have their source and intent recognized, receive an appropriate recommendation, and leave behind an attributable commercial journey without manual data movement by `d-mac`.

---

## Architectural Components

### 1. CTA Registry (`cta_registry.py`, `config/cta_registry.json`)
Governs all commercial and engagement calls to action.
- **CTA Classes**: `COMMUNITY_JOIN`, `ASK_BUDLY`, `EXPLORE_PRODUCT`, `SHOP_PRODUCT`, `LEARN_MORE`, `SUBSCRIBE_UPDATES`, `JOIN_CONVERSATION`.
- **Approved Destinations**:
  - `https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/`
  - `https://cccultivate.com/product/infused-basics/`
  - `https://cccultivate.com/shop/`
  - `https://www.wakenbakelounge.com/ask-budly`
  - `https://www.wakenbakelounge.com/`
- **Rule**: Inactive or unapproved CTAs are never selected or published.

### 2. Attribution Link Standard (`attribution.py`)
Deterministic parameter standard surviving landing page navigation:
- `source`: Acquisition channel (e.g., `social`, `direct`)
- `platform`: Origin platform (e.g., `instagram`, `facebook`, `web`)
- `content_id`: Social post/asset ID (e.g., `IG-20260906-0002`)
- `campaign_id`: Marketing campaign identifier (e.g., `STS-PILOT-001`)
- `cta_id`: Governed CTA identifier (e.g., `CTA-ASK-BUDLY-001`)
- `product_or_topic`: Initial product/topic context (e.g., `BOTANICAL_COLLECTION`)
- `published_post_id`: Optional published post tracking ID

**Security**: Strips any email, phone number, or credentials from parameters.

### 3. Ask Budly Intake (`intake.py`)
- Captures attribution on entry: `session_id`, `source`, `platform`, `content_id`, `campaign_id`, `cta_id`, `entry_timestamp`, `landing_route`.
- Safely downgrades unrecognized or inactive CTAs to default `CTA-ASK-BUDLY-001`.
- Preserves anonymous operation until lead criteria are triggered.
- Idempotent: repeated entries with the same session reuse the existing journey.

### 4. Intent & Topic Taxonomy (`intent_taxonomy.py`)
- **Commercial Intents**:
  - `GENERAL_CONVERSATION`
  - `EDUCATION_INTEREST`
  - `COMMUNITY_INTEREST`
  - `PRODUCT_INTEREST`
  - `PURCHASE_INTENT`
  - `SUPPORT_QUESTION`
  - `UNKNOWN`
- **Product Topics**:
  - `BOTANICAL_COLLECTION` (Pilot Product)
  - `COLORING_APP`
  - `WAKE_N_BAKE_CONTENT`
  - `OTHER_APPROVED_PRODUCT`
  - `UNKNOWN`

### 5. Lead Promotion Threshold (`lead_threshold.py`)
Enforces the BROS CRM lifecycle governance by separating commercial qualification from CRM Lead creation:
- **Anonymous Qualified Visitor**: Anonymous visitors expressing product interest or purchase intent can achieve `QUALIFIED_PURCHASE_READY` and receive verified product recommendations, while remaining anonymous (`lead_id=None`).
- **CRM Lead Promotion**: A CRM Lead is only created/linked when approved voluntary identifying information (e.g. email, name, phone) is voluntarily provided by the visitor.
- **Idempotent Linkage**: When identity is supplied, the canonical customer record is linked to the existing conversion journey (`journey.lead_id = customer_id`) exactly once.

### 6. Qualification State Logic (`qualification.py`)
- States: `UNQUALIFIED`, `DISCOVERY`, `QUALIFIED_EDUCATION`, `QUALIFIED_COMMUNITY`, `QUALIFIED_NURTURE`, `QUALIFIED_PURCHASE_READY`, `NOT_CURRENT_FIT`.
- Evaluated deterministically with zero guessing or invented claims.

### 7. Recommendation Router (`recommendation_router.py`)
- Maps `(intent, product_or_topic, qualification_state) -> Approved CTA Record`.
- Guarantees fail-closed safety: no unapproved URLs or invented discount/reservation promises can be emitted.

### 8. Journey & Lead Repository (`journey_repository.py`)
Extends the native BROS CRM SQLite store (`data/sales.db`) with:
- `conversion_journeys` table
- `conversion_leads` table
- `sts_audit_log` table

---

## Directory Structure

```
SOCIAL-TO-SALE-001/
├── __init__.py
├── README.md
├── acceptance_report.md
├── attribution.py
├── config/
│   └── cta_registry.json
├── conversion_spine.py
├── cta_registry.py
├── intake.py
├── intent_taxonomy.py
├── journey_repository.py
├── lead_threshold.py
├── qualification.py
├── recommendation_router.py
└── tests/
    ├── __init__.py
    ├── test_attribution.py
    ├── test_conversion_spine_e2e.py
    ├── test_cta_registry.py
    ├── test_intent_and_qualification.py
    ├── test_negative_acceptance.py
    └── test_positive_acceptance.py
```

---

## How to Run Tests

Execute the STS-1 test suite:
```bash
python -m unittest discover -s SOCIAL-TO-SALE-001/tests -p "test_*.py"
```
