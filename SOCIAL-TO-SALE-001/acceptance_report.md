# SOCIAL-TO-SALE-001: Phase STS-1 Acceptance Test Report

**Project**: BROS / Budly Ecosystem  
**Phase**: STS-1 Conversion Spine Foundation  
**Date**: 2026-09-07  
**Status**: ACCEPTED & PASSED (21 / 21 Tests Passing)  

---

## 1. Test Suite Summary

| Test Module | Tests Run | Passed | Failed | Errors |
| :--- | :---: | :---: | :---: | :---: |
| `test_cta_registry.py` | 4 | 4 | 0 | 0 |
| `test_attribution.py` | 3 | 3 | 0 | 0 |
| `test_intent_and_qualification.py` | 4 | 4 | 0 | 0 |
| `test_positive_acceptance.py` | 1 | 1 | 0 | 0 |
| `test_negative_acceptance.py` | 8 | 8 | 0 | 0 |
| `test_conversion_spine_e2e.py` | 1 | 1 | 0 | 0 |
| **Total** | **21** | **21** | **0** | **0** |

---

## 2. Positive Acceptance Requirements Matrix

| # | Requirement | Status | Evidence / Verification Method |
|---|---|:---:|---|
| 1 | Valid attributed Instagram entry captured | PASSED | `TestPositiveAcceptance.test_complete_positive_conversion_spine_journey` extracts `source=social`, `platform=instagram` into `EntrySessionContext`. |
| 2 | Correct content ID attached to journey | PASSED | `content_id=IG-20260906-0002` verified in initial and updated `conversion_journeys` record. |
| 3 | Ask Budly session created | PASSED | Anonymous session ID initialized with `conversion_state='initiated'`. |
| 4 | Product interest recognized | PASSED | Utterance for Botanical Collection mapped to `PRODUCT_INTEREST` and `BOTANICAL_COLLECTION`. |
| 5 | Journey updated deterministically | PASSED | SQLite row updated with intent, topic, destination, and state. |
| 6 | Appropriate qualification state assigned | PASSED | Assigned `QUALIFIED_NURTURE` on initial product interest; advanced to `QUALIFIED_PURCHASE_READY` on purchase signal. |
| 7 | Approved CTA selected | PASSED | Verified CTA (`CTA-BOTANICAL-VOL1-EXPLORE` / `CTA-BOTANICAL-VOL1-SHOP`) selected from active registry. |
| 8 | Approved destination returned | PASSED | `https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/` returned. |
| 9 | No manual data transfer by d-mac | PASSED | Entire pipeline executes autonomously; Lead and Journey records stored in CRM table without manual intervention. |

---

## 3. Negative Acceptance Requirements Matrix

| # | Requirement | Status | Evidence / Verification Method |
|---|---|:---:|---|
| 1 | Unknown CTA ID rejected or safely downgraded | PASSED | `test_negative_1_unknown_cta_downgraded`: Unknown CTA ID downgraded to default `CTA-ASK-BUDLY-001` with `cta_downgraded=True`. |
| 2 | Inactive CTA never selected | PASSED | `test_negative_2_inactive_cta_never_selected`: Inactive/Draft CTA filtered out; downgraded safely. |
| 3 | Missing attribution allows conversation | PASSED | `test_negative_3_missing_attribution_allows_conversation`: Defaults to `source='direct'`, `platform='web'`. |
| 4 | Invalid content ID does not create false attribution | PASSED | `test_negative_4_invalid_content_id_does_not_create_false_attribution`: PII, emails, and invalid characters stripped. |
| 5 | Unapproved destination cannot be recommended | PASSED | `test_negative_5_unapproved_destination_cannot_be_recommended`: Router fails closed or selects verified active CTA. |
| 6 | Anonymous visitor does not become lead prematurely | PASSED | `test_negative_6_anonymous_visitor_does_not_become_lead`: Anonymous commercial/purchase-intent visitors achieve `QUALIFIED_PURCHASE_READY` and receive verified recommendations without creating a CRM `lead_id` until voluntary contact information is supplied. |
| 7 | No invented price/offer/reservation claims | PASSED | `test_negative_7_no_invented_price_or_offer_claims`: Dialogue suggestions contain only verified statements. |
| 8 | Repeated identical event does not duplicate records | PASSED | `test_negative_8_idempotency_prevents_duplicate_journey`: Same session re-entry maintains single idempotent DB row. |

---

## 4. Observability Verification

The simulated pilot test (`test_conversion_spine_e2e.py`) verified complete end-to-end trace evidence:
- **Acquisition Origin**: `source=social`, `platform=instagram`
- **Post ID**: `content_id=IG-20260906-0002`, `published_post_id=POST-BOTANICAL-01`
- **Entry CTA**: `CTA-ASK-BUDLY-001`
- **User Intent**: `PRODUCT_INTEREST` -> `PURCHASE_INTENT`
- **Topic**: `BOTANICAL_COLLECTION`
- **Qualification Transition**: `UNQUALIFIED` -> `QUALIFIED_NURTURE` -> `QUALIFIED_PURCHASE_READY`
- **Recommendation Destination**: `https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/`
- **State Advancement**: `initiated` -> `recommended`
