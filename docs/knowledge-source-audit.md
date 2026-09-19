# Knowledge Source Audit: Budly 1.8.8 Runtime & Knowledge Ecosystem

**Document ID**: `DOCS-KNOWLEDGE-AUDIT-001`  
**Target Release**: 1.9.0  
**Current Production Baseline**: 1.8.8 PRODUCTION ACCEPTED  
**Commit**: `b0604505df870002cf73ee6d4a20fa0ef1f1334e`  
**Status**: DRAFT / FINAL EVIDENCE INTEGRITY CORRECTION (SOURCE-RECONCILIATION-001B)  
**Last Updated**: 2026-09-13  

---

## 1. Executive Summary

This audit establishes the definitive, verified baseline of all knowledge sources, commercial entities, domain configurations, and operational capabilities across Budly 1.8.8 runtime, WordPress/WooCommerce, and Wix platforms.

### Key Evidence-Based Findings (SOURCE-RECONCILIATION-001B):
1. **Live WooCommerce NFT Membership Catalog**: Exact parent product IDs and variation IDs for all 10 character NFT memberships have been verified directly against the raw Store API payload. All 10 are variable products containing 4 explicit variation objects: **Bronze ($5,000)**, **Copper ($10,000)**, **Titanium ($20,000)**, and **Platinum ($40,000)**.
2. **NFT Benefit Source**: Specific course enrollment choices and community access perks are **`BENEFIT_SOURCE_NOT_PRESENT_IN_WOOCOMMERCE`**; WooCommerce product descriptions contain character lore only.
3. **Coupon Verification**: Coupons `LOUNGEMEMBER10` and `LOUNGEELITE25` are classified as **`NOT_VERIFIED`** in WooCommerce (the public Store API cannot inspect administrative coupon tables without authentication).
4. **"Is Cannabis Right For Me?" ($75)**: Verified as an active consultation booking on Wix absent from WooCommerce, classified as **`ACTIVE_CATALOG_GAP`**.
5. **Wix Plans & Services Lifecycle**: Wix PaidPlans ($1000/$1500/$2500 one-time, $300/$425/$675 recurring) are classified as **`RELATIONSHIP_UNVERIFIED`** (candidate alternate checkout formats). Wix Bookings ($250/$300 classes) are classified as **`UNKNOWN_REQUIRES_OWNER_REVIEW`**.
6. **Newsletter Status**: Verified via live Wix inspection. Subscription forms exist (`UPDATE_CAPTURE_AVAILABLE`), but all campaigns are draft/not-started (`NEWSLETTER_DELIVERY: INACTIVE_OR_UNVERIFIED`). Permitted phrasing: *"You can sign up for updates on Wake'n'Bake Lounge."*
7. **Domain Configuration**: Verified discrepancy (`DOMAIN_CONFIGURATION_DISCREPANCY`) between Wix API primary (`dmckenzies.wixsite.com/wakenbakelounge`) and canonical domain (`wakenbakelounge.com`). Logged as `WNB-CANONICAL-DOMAIN-001`.
8. **Affiliate Backend**: Relationship classified as **`RELATIONSHIP_UNVERIFIED`**. Wix hosts discovery/application (`wnb:affiliate:program`), while WordPress hosts account login (`ccc:affiliate:account`) and WooCommerce tracks `_budly_affiliate_id`.

---

## 2. Classification Taxonomy & Epistemic Status

Every finding in this audit is classified under one of the following authoritative states:

* **`OWNER-APPROVED`**: Explicitly decided and ratified by the Project Owner.
* **`SOURCE-VERIFIED`**: Directly evidenced by inspectable code, raw API payloads, or repository files.
* **`INFERRED`**: Deduced from context, but lacking explicit source documentation.
* **`UNKNOWN_REQUIRES_VERIFICATION`** / **`NOT_VERIFIED`**: Insufficient evidence to establish truth; must not be asserted as true or false by runtime.
* **`ACTIVE_CATALOG_GAP`**: Active customer-facing service/product identified on an external channel (e.g. Wix) that is absent from the authoritative WooCommerce commercial catalog.
* **`STALE / INVALID`** or **`SUPERSEDED_INVALID`**: Historical or incorrect data in code/config superseded by owner decisions.
* **`APPROVED_NOT_RELEASED`**: Owner-approved business truth that is NOT yet customer-available or purchasable.
* **`ACTIVE`**: Verified active commercial or educational asset.
* **`ACTIVE_DISTINCT_SERVICE`**: Verified active distinct service.
* **`RELATIONSHIP_UNVERIFIED`**: Offer exists but operational relationship between channels requires further verification.
* **`LEGACY`**: Preserved for historical context; not active for new interactions.
* **`RETIRED`**: Formally deactivated entity.

---

## 3. Verified Live WooCommerce NFT Membership Parent & Variation Matrix

Every ID, attribute name, variation ID, and price verified against raw WooCommerce Store API response:

| Character Name | Parent ID | Parent Slug | Attribute Name | Bronze Var ID & Price | Copper Var ID & Price | Titanium Var ID & Price | Platinum Var ID & Price | Purchasable | In Stock | Permalink |
|---|---|---|---|---|---|---|---|---|---|---|
| **Azurea Skye** | 212 | `azurea-skye` | `Membership tier` | 277 ($5,000) | 278 ($10,000) | 279 ($20,000) | 280 ($40,000) | True | True | `https://cccultivate.com/product/azurea-skye/` |
| **Cookie Cutter** | 214 | `cookie-cutter` | `Membership Tier` | 281 ($5,000) | 282 ($10,000) | 283 ($20,000) | 284 ($40,000) | True | True | `https://cccultivate.com/product/cookie-cutter/` |
| **Dizel** | 216 | `dizel` | `Membership Tiers` | 285 ($5,000) | 286 ($10,000) | 287 ($20,000) | 288 ($40,000) | True | True | `https://cccultivate.com/product/dizel/` |
| **The Monarch** | 218 | `the-monarch` | `Membership Tiers` | 289 ($5,000) | 290 ($10,000) | 291 ($20,000) | 292 ($40,000) | True | True | `https://cccultivate.com/product/the-monarch/` |
| **The Original Guardian** | 220 | `the-original-guardian` | `Membership Tiers` | 293 ($5,000) | 294 ($10,000) | 295 ($20,000) | 296 ($40,000) | True | True | `https://cccultivate.com/product/the-original-guardian/` |
| **The Don** | 825 | `the-godfather-og-nft-membership` | `Membership Tiers` | 826 ($5,000) | 827 ($10,000) | 828 ($20,000) | 829 ($40,000) | True | True | `https://cccultivate.com/product/the-godfather-og-nft-membership/` |
| **Gamma Blaze** | 831 | `bruce-banner-3-nft-membership` | `Membership Tiers` | 867 ($5,000) | 868 ($10,000) | 869 ($20,000) | 870 ($40,000) | True | True | `https://cccultivate.com/product/bruce-banner-3-nft-membership/` |
| **Berry Bliss** | 833 | `strawberry-banana-nft-membership` | `Membership Tiers` | 871 ($5,000) | 872 ($10,000) | 873 ($20,000) | 874 ($40,000) | True | True | `https://cccultivate.com/product/strawberry-banana-nft-membership/` |
| **Torque** | 875 | `875` | `Membership Tiers` | 877 ($5,000) | 878 ($10,000) | 879 ($20,000) | 880 ($40,000) | True | True | `https://cccultivate.com/product/875/` |
| **The Chemist** | 882 | `the-chemist-nft-membership` | `Membership Tiers` | 883 ($5,000) | 884 ($10,000) | 885 ($20,000) | 886 ($40,000) | True | True | `https://cccultivate.com/product/the-chemist-nft-membership/` |

---

## 4. Evidence-Based Wix Service & Plan Lifecycle Classification

| Wix Entity / Record | Format Type | Wix Price | Corresponding WooCommerce Offer | Evidence-Based Classification | Operational Impact |
|---|---|---|---|---|---|
| **Grow & Cook With Me** | PaidPlan (One-Time) | $2,500 | Cook & Grow With Me ($2,500, ID: 152) | `RELATIONSHIP_UNVERIFIED` | Price matches WooCommerce; operational activity unverified |
| **Grow Cannabis @ Home** | PaidPlan (One-Time) | $1,500 | Grow Cannabis @ Home ($1,500, ID: 151) | `RELATIONSHIP_UNVERIFIED` | Price matches WooCommerce; operational activity unverified |
| **Culinary Cannabis** | PaidPlan (One-Time) | $1,000 | Culinary Cannabis ($1,000, ID: 150) | `RELATIONSHIP_UNVERIFIED` | Price matches WooCommerce; operational activity unverified |
| **Grow & Cook With Me** | PaidPlan (Recurring) | $675/mo | Payment Plan option ($675) | `RELATIONSHIP_UNVERIFIED` | Price matches payment plan; operational activity unverified |
| **Grow Cannabis @ Home** | PaidPlan (Recurring) | $425/mo | Payment Plan option ($425) | `RELATIONSHIP_UNVERIFIED` | Price matches payment plan; operational activity unverified |
| **Culinary Cannabis** | PaidPlan (Recurring) | $300/mo | Payment Plan option ($300) | `RELATIONSHIP_UNVERIFIED` | Price matches payment plan; operational activity unverified |
| **Is Cannabis Right For Me?** | Booking (Appointment) | $75 | None in WooCommerce | `ACTIVE_CATALOG_GAP` | Active Wix service absent from WooCommerce commercial catalog |
| **Grow Cannabis At Home** | Booking (Class) | $300 | Conflicts with $1,500 course | `UNKNOWN_REQUIRES_OWNER_REVIEW` | Workshop vs. full course relationship unverified |
| **Cooking With Cannabis** | Booking (Class) | $250 | Conflicts with $1,000 course | `UNKNOWN_REQUIRES_OWNER_REVIEW` | Workshop vs. full course relationship unverified |

---

## 5. WooCommerce Catalog Gap & Coupon Verification Status

1. **Wake'n'Bake Community Memberships**:
   - Lounge Pass (Free): **`DOES_NOT_EXIST`** in WooCommerce.
   - Lounge Member ($9.99/mo): **`DOES_NOT_EXIST`** in WooCommerce.
   - Lounge Elite ($24.99/mo): **`DOES_NOT_EXIST`** in WooCommerce.
   - *Status*: **`APPROVED_NOT_RELEASED`**.
2. **Community Membership Discount Codes**:
   - `LOUNGEMEMBER10`: **`NOT_VERIFIED`** in WooCommerce coupon store.
   - `LOUNGEELITE25`: **`NOT_VERIFIED`** in WooCommerce coupon store.
   - *Status*: **`APPROVED_NOT_RELEASED`** / **`NOT_VERIFIED`**.
3. **Active Service Gap**:
   - "Is Cannabis Right For Me?" ($75 appointment): **`ACTIVE_CATALOG_GAP`** (exists on Wix Bookings, absent from WooCommerce).
