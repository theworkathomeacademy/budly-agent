# Conflicts & Clarifications: Budly Commercial Knowledge

**Document ID**: `DOCS-CONFLICTS-001`  
**Version**: 0.5  
**Target Release**: 1.9.0 (`1.9.0-rc2` Preproduction Package)  
**Baseline**: Post Final Deployment Gate (WEB-COMMERCIAL-ALIGNMENT-001E)  
**Status**: ACTIVE WORKING RECORD  
**Last Updated**: 2026-09-13  

---

## 1. Owner-Resolved & Evidence-Closed Clarifications

### 1.1 Membership Taxonomy & Pricing
* **Resolution**: **Owner Approved & Source Verified**. The authoritative membership structure for Wake'n'Bake Legends NFT Memberships consists of **Bronze ($5,000), Copper ($10,000), Titanium ($20,000), Platinum ($40,000)** across 10 variable character products in WooCommerce.
* **Parent & Variation IDs**: All 10 parent product IDs (212, 214, 216, 218, 220, 825, 831, 833, 875, 882) and their respective variation IDs (e.g. Torque: Parent 875, Variations 877–880; The Chemist: Parent 882, Variations 883–886) are verified directly against raw Store API payloads.
* **Benefit Source Finding**: Specific course enrollment choices and community access perks are **`BENEFIT_SOURCE_NOT_PRESENT_IN_WOOCOMMERCE`**; WooCommerce descriptions contain character lore only.
* **Disposition of Old Knowledge**: Silver Legend ($3,000), Gold Legend ($5,000), and Legend OG ($10,000) are **`SUPERSEDED_INVALID`** / **`STALE KNOWLEDGE`** and scheduled for removal.

### 1.2 Infused Basics Classification
* **Resolution**: **Owner Approved**. Infused Basics is a **BOOK** (`ccc:book:infused-basics`). It is educational, narrative, and cannabis-cooking focused, associated with recipes on the website. It is NOT a course, class, membership, or free course.
* **Disposition**:
  * Book Entity: `ACTIVE` (`ccc:book:infused-basics`, $40).
  * Course Classification: `INVALID / REMOVE FROM BUDLY COMMERCIAL MODEL`.
  * Wix Web Pages: `VERIFY AND CLASSIFY BEFORE RETIREMENT`. Retain companion recipe and preview content.

### 1.3 Community Memberships & Benefit Count Language
* **Resolution**: **Owner Approved & Source Verified**.
  * **Lounge Pass** (Free, Wix ID `a101970a-...`): **1 approved benefit** (Community access).
  * **Lounge Member** ($9.99/mo, Wix ID `1658a089-...`): **6 approved benefits** (Community access, 10% off Lounge Collection, early access to new drops, exclusive forum sections, member badge, priority event access).
  * **Lounge Elite** ($24.99/mo, Wix ID `ac8a8d86-...`): **6 approved benefits** (Community access, 25% off Lounge Collection, first access to exclusive drops, VIP forum badge, priority event invitations, monthly curated content from Budly T. Cannaguide).
  * Architectural Classification: **`APPROVED_NOT_RELEASED`**.

### 1.4 Coupon Release Gate & Deferral Decision
* **Resolution**: **Safety Policy Enacted**.
  * Classification: `PRELAUNCH_CONFIGURATION_PRESENT`, `REDEMPTION_BEHAVIOR_NOT_RUNTIME_VERIFIED`.
  * Policy: **DEFER LIVE COUPON CREATION UNTIL LAUNCH**. Live WooCommerce coupon records are not created during preproduction provisioning. Planned coupon relationships (`LOUNGEMEMBER10`, `LOUNGEELITE25`) are retained in the canonical catalog specification.

### 1.5 Provisioning Authorization Gate (Fail-Closed)
* **Resolution**: **Code & Test Verified**.
  * `CatalogProvisioner::provision_all()` implements strict fail-closed logic: unauthenticated callers and non-admin logged-in users are rejected with `status = error, reason = unauthorized`.
  * Only users with `manage_woocommerce` or `manage_options` are authorized.

### 1.6 Consultation Service ("Is Cannabis Right For Me?") Destination
* **Resolution**: **Source Verified & Re-tested**.
  * Verified Wix Service Booking URL: `https://wakenbakelounge.com/service-page/is-cannabis-right-for-me` (HTTP 200 OK verified live).
  * Classification: `external_destination_status = 'VERIFIED'`.
  * Provisioner configures `WC_Product_External` with button "Book Consultation" directing to the verified service endpoint.

### 1.7 Torque Redirect Predeployment Safety Gate
* **Resolution**: **Source Verified & Safety Gated**.
  * Live URL `/product/875/` returns `HTTP 200 OK`.
  * Target URL `/product/torque-nft-membership/` returns `HTTP 404 Not Found`.
  * Unconditional redirect removed. Redirect is strictly gated behind `budly_torque_slug_migrated = '1'`. Programmatic migration method `CatalogProvisioner::migrate_torque_slug()` validates product 875 and variation IDs 877–880 before enabling redirect.

---

## 2. Evidence-Based Lifecycle Matrix: Wix Services & Plans

| Wix Entity / Plan | Format Type | Wix Price | Corresponding WooCommerce Offer | Evidence-Based Classification | Operational Impact |
|---|---|---|---|---|---|
| **Grow & Cook With Me** | PaidPlan (One-Time) | $2,500 | Cook & Grow With Me ($2,500, ID: 152) | `RELATIONSHIP_UNVERIFIED` | Price matches WooCommerce; operational activity unverified |
| **Grow Cannabis @ Home** | PaidPlan (One-Time) | $1,500 | Grow Cannabis @ Home ($1,500, ID: 151) | `RELATIONSHIP_UNVERIFIED` | Price matches WooCommerce; operational activity unverified |
| **Culinary Cannabis** | PaidPlan (One-Time) | $1,000 | Culinary Cannabis ($1,000, ID: 150) | `RELATIONSHIP_UNVERIFIED` | Price matches WooCommerce; operational activity unverified |
| **Grow & Cook With Me** | PaidPlan (Recurring) | $675/mo | Payment Plan option ($675) | `RELATIONSHIP_UNVERIFIED` | Price matches payment plan; verified Stripe checkout route live |
| **Grow Cannabis @ Home** | PaidPlan (Recurring) | $425/mo | Payment Plan option ($425) | `RELATIONSHIP_UNVERIFIED` | Price matches payment plan; verified Stripe checkout route live |
| **Culinary Cannabis** | PaidPlan (Recurring) | $300/mo | Payment Plan option ($300) | `RELATIONSHIP_UNVERIFIED` | Price matches payment plan; verified Stripe checkout route live |
| **Is Cannabis Right For Me?** | Booking (Appointment) | $75 | Canonical ID: `ccc:service:is-cannabis-right-for-me` | `EXTERNAL_DESTINATION_VERIFIED` | Verified Wix service booking endpoint configured in CatalogProvisioner |
| **Grow Cannabis At Home** | Booking (Class) | $300 | Conflicts with $1,500 course | `UNKNOWN_REQUIRES_OWNER_REVIEW` | Workshop vs. full course relationship unverified |
| **Cooking With Cannabis** | Booking (Class) | $250 | Conflicts with $1,000 course | `UNKNOWN_REQUIRES_OWNER_REVIEW` | Workshop vs. full course relationship unverified |

---

## 3. Legitimately Unresolved Items Requiring Verification or Owner Decision

1. **Affiliate Backend Operational Verification (`RELATIONSHIP_UNVERIFIED`)**: Wix hosts discovery/application (`wnb:affiliate:program`), while WordPress hosts account login (`ccc:affiliate:account`). Distinct source records maintained.
2. **NFT Tier Perk & Benefit Registry Linkage**: The Unified Commercial Knowledge Registry must define the authoritative benefit mappings linking to the WooCommerce product IDs (`BENEFIT_SOURCE_NOT_PRESENT_IN_WOOCOMMERCE`).
3. **Subscription Payment Processor Selection**: Separate commercial workstream. Registry schema supports `payment_type: ONE_TIME | RECURRING` and `payment_processor: WOOCOMMERCE | STRIPE | TBD_APPROVED_PROCESSOR | OTHER_APPROVED`.
4. **Dual Active Affiliate Engines (`DUAL_ACTIVE_AFFILIATE_ENGINES`)**: Direct production inspection confirms both Goaffpro Affiliate Marketing (v2.7.12) and SliceWP (v1.2.11) are active on live WordPress. Added to affiliate reconciliation backlog to determine ownership of registration, affiliate IDs, portal, tracking, and `_budly_affiliate_id` attribution. Non-blocking for RC2 deployment.
