# Commercial Source Authority Matrix

**Document ID**: `DOCS-AUTH-MATRIX-001`  
**Version**: 0.5  
**Status**: ACTIVE WORKING BASELINE — Post Final Deployment Gate (WEB-COMMERCIAL-ALIGNMENT-001E)  
**Governing Authority**: Owner-Approved Decisions, Full Wix Benefit Truth, & Raw Store API Baseline  
**Next Release Target**: 1.9.0 (`1.9.0-rc2` Preproduction Package)  
**Last Updated**: 2026-09-13  

---

## 1. Authoritative Commercial Rules & Decisions

| Domain / Decision Area | Owner-Approved Policy & Authority Decision | Epistemic Status |
|---|---|---|
| **Universal Commercial Catalog** | **WooCommerce** is the universal commercial catalog for products, books, classes, services, memberships, one-time purchases, subscriptions, and externally fulfilled commercial offers. | `OWNER-APPROVED` |
| **Commercial Price Authority** | **Live WooCommerce Store API** is the sole price authority. Static Python/JSON pricing must not override live WooCommerce commercial truth. | `OWNER-APPROVED` |
| **Payment Route vs. Catalog Authority** | The payment execution route (WooCommerce native or verified Stripe checkout links) is decoupled from commercial catalog authority. | `OWNER-APPROVED` |
| **Educational Content Authority** | WooCommerce is NOT the sole authority for rich educational content. Detailed curriculum, syllabi, narratives, and educational resources originate from Wix, BROS, or an approved Knowledge Registry with provenance. | `OWNER-APPROVED` |
| **Infused Basics Classification** | Infused Basics is a **BOOK** (`ccc:book:infused-basics`, $40.00). It is educational, narrative, and cannabis-cooking focused, associated with recipes on the website. It is NOT a course, class, membership, or free course. | `OWNER-APPROVED` |
| **NFT Membership Taxonomy** | **Wake'n'Bake Legends NFT Memberships** have four approved tiers: **Bronze ($5,000), Copper ($10,000), Titanium ($20,000), Platinum ($40,000)** across 10 characters (`SOURCE-DERIVED STRUCTURE`). Live WooCommerce catalog is authoritative. Benefits are `BENEFIT_SOURCE_NOT_PRESENT_IN_WOOCOMMERCE`. | `OWNER-APPROVED` / `SOURCE-VERIFIED` |
| **Community Memberships & Full Benefit Set** | **Wake'n'Bake Community Memberships**: Lounge Pass (Free, 1 benefit), Lounge Member ($9.99/mo, 6 benefits), Lounge Elite ($24.99/mo, 6 benefits) are approved for future launch with full verified benefits (Wix Plan IDs: `a101970a-...`, `1658a089-...`, `ac8a8d86-...`). | `APPROVED_NOT_RELEASED` |
| **Customer Availability Gate** | `APPROVED` truth does NOT equal customer availability. Unreleased community tiers and discount codes must NOT be presented as purchasable or active. | `OWNER-APPROVED` |
| **Coupon Deferral Policy** | Live WooCommerce coupon creation is **DEFERRED UNTIL LAUNCH** (`PRELAUNCH_CONFIGURATION_PRESENT`, `REDEMPTION_BEHAVIOR_NOT_RUNTIME_VERIFIED`). | `OWNER-APPROVED` / `SAFETY-GATED` |
| **Canonical Brand Domains** | **Wake'n'Bake Lounge**: `https://wakenbakelounge.com` (Wix content platform)<br>**CCC Sales**: `https://cccultivate.com` (WordPress/WooCommerce)<br>**CCC Brand/Education**: Future `https://compassionatecarecultivators.com`; currently available at `https://learn.cccultivate.com` (Wix).<br>*Discrepancy*: Wix primary API URL is `dmckenzies.wixsite.com/wakenbakelounge` (`DOMAIN_CONFIGURATION_DISCREPANCY`, backlog: `WNB-CANONICAL-DOMAIN-001`). | `OWNER-APPROVED` / `SOURCE-VERIFIED` |
| **Newsletter Status** | Subscription capture is available on Wix (`UPDATE_CAPTURE_AVAILABLE`), but active email marketing campaigns are in draft/not-started state (`NEWSLETTER_DELIVERY: INACTIVE_OR_UNVERIFIED`). Permitted phrasing: *"You can sign up for updates on Wake'n'Bake Lounge."* | `SOURCE-VERIFIED` |
| **Email Provider & Capability** | Target provider is **Brevo**. Brevo is currently `NOT_CONFIGURED`. Budly must NOT claim automated email sending until `SEND_EMAIL` capability is verified. Safe current phrasing: *"I can note your interest for the team"* (or *"save your interest"* if CRM consent is granted). | `OWNER-APPROVED` / `SOURCE-VERIFIED` |

---

## 2. Commercial Source Authority Matrix

| Entity / Fact Category | Authoritative Source | Secondary Source | Status | Freshness Method | Approval Requirement | Conflict Rule | Budly Conversational Fallback |
|---|---|---|---|---|---|---|---|
| **Product Name** | WooCommerce (Live Store API) | `config/products.json` allowlist | `ACTIVE` | Real-time query per turn | `products.json` allowlist match | WooCommerce live name wins | *"I don't have an approved source for that product."* |
| **Product Price** | WooCommerce (Live Store API) | NONE | `ACTIVE` | Real-time query per turn | WooCommerce `is_purchasable` | Live WooCommerce wins; static prompt prices invalid | Decline to guess price; provide product link. |
| **Product Availability** | WooCommerce (Live Store API) | NONE | `ACTIVE` | Real-time query per turn | `is_in_stock` & `is_purchasable` | Live WooCommerce wins | *"Availability is listed on our product page."* + link |
| **Course Payment Plan (Stripe)** | Verified Stripe Checkout Route | WooCommerce external product | `ACTIVE` | Real-time form inspection | Verified live route (`https://buy.stripe.com/...`) | Live Stripe route authoritative for checkout | Route customer to payment plan product page. |
| **Product Description** | WooCommerce `short_description` (Live) | `commercial-knowledge-v1.0.json` | `ACTIVE` | Real-time query | Owner-approved resource summary | WooCommerce description wins for purchasable items | Use approved JSON summary; do not invent specs. |
| **Book (Infused Basics / Botanical v1)** | WooCommerce (Live Store API) | `commercial-knowledge-v1.0.json` | `ACTIVE` | Real-time query | Owner-approved book entity | WooCommerce wins for price/stock; JSON for narrative identity | Link to book product page. |
| **Class / Course Full Enrollment** | WooCommerce (Live Store API) | `commercial-knowledge-v1.0.json` | `ACTIVE` | Real-time query | Owner-approved course entity | WooCommerce wins for commercial offers | *"Current pricing is available on the course page."* + link |
| **Class / Course Curriculum & Detail** | Wix CMS / Knowledge Registry / BROS | WooCommerce `short_description` | `ACTIVE` | Knowledge Registry / provenance | Owner-approved syllabus / curriculum | Approved Registry wins over generic model recall | Use approved syllabus summary; do not invent curriculum. |
| **Consultation Service ("Is Cannabis Right For Me?")** | Wix Bookings ($75) | Canonical catalog specification | `ACTIVE_CATALOG_GAP` | Wix Bookings verification | Owner approval to add to WooCommerce | Direct to verified Wix service URL: `https://wakenbakelounge.com/service-page/is-cannabis-right-for-me` | Direct customer to Wix consultation page or note interest. |
| **Wake'n'Bake Legends NFT Memberships** | WooCommerce (Live Store API) | `commercial-knowledge-v1.0.json` | `ACTIVE` | Real-time query | Owner-approved structure (Bronze $5k, Copper $10k, Titanium $20k, Platinum $40k across 10 characters) | Live WooCommerce catalog wins; hardcoded Silver/Gold/OG rules are `SUPERSEDED_INVALID` | Link to `/legends/` or specific character product page. |
| **Community Memberships (Full Benefits)** | Verified Wix Membership Plans | Canonical catalog specification | `APPROVED_NOT_RELEASED` | Wix plan verification | Owner-approved full benefit package | Do NOT present as currently purchasable | State full value proposition when explaining upcoming memberships; do not quote unreleased codes. |
| **Discount Codes (LOUNGEMEMBER10, etc.)** | Owner-Approved Specifications | `CatalogProvisioner` draft configuration | `APPROVED_NOT_RELEASED` | Static registry | Tied to unreleased community memberships | **DEFER LIVE CREATION UNTIL LAUNCH** | Do not reveal discount codes. |
| **Newsletter Status** | Wix Platform subscription infrastructure | `commercial-knowledge-v1.0.json` | `UPDATE_CAPTURE_AVAILABLE` | Verified via live Wix API | Owner-approved | State update capture is available; do NOT claim recurring active delivery | *"You can sign up for updates on Wake'n'Bake Lounge."* |
| **Forum / Community** | `commercial-knowledge-v1.0.json` | Wix Platform | `ACTIVE` (Community); `NOT_OFFERED` (Forum) | Manual verification | Owner-approved feature truth | Community active on Wake'n'Bake Lounge; no public bulletin board | Direct to online community at `wakenbakelounge.com`. |
| **Affiliate Program (Discovery & Portal)** | Wix (`/affiliates`) & WordPress (`/affiliate-account/`) | `commercial-knowledge-v1.0.json` | `RELATIONSHIP_UNVERIFIED` | Audit of live portals | Preserve separate source identifiers | Do NOT assert single vs separate programs until verified | Present respective portal link based on customer context (application vs account). |
| **Customer Return Policy** | `config/policies.json` | `cccultivate.com/customer-policies/` | `ACTIVE` | Manual file edit | `owner_approved` | `policies.json` authoritative | Link to `/customer-policies/`. |
| **Canonical Brand Domain — Wake'n'Bake** | `https://wakenbakelounge.com` | Wix technical origin (`dmckenzies.wixsite.com/wakenbakelounge`) | `ACTIVE` (`DOMAIN_CONFIGURATION_DISCREPANCY`) | Owner-approved | Owner-approved canonical domain | Use canonical domain for all customer links | Output `https://wakenbakelounge.com`. |

---

## 3. Verified Community Membership Benefit Truth

| Membership Tier | Canonical ID | Price | Billing Model | Benefit Count | Verified Wix Plan ID | Full Approved Benefits |
|---|---|---|---|---|---|---|
| **Lounge Pass** | `wnb:community:lounge-pass` | $0.00 | Free | **1** | `a101970a-4600-4dbb-8e49-e91cfed93d80` | • Community access |
| **Lounge Member** | `wnb:community:lounge-member` | $9.99/mo | Recurring Monthly | **6** | `1658a089-db78-418c-85ed-ac01d5bcabb0` | • Community access<br>• 10% off all Lounge Collection products (`LOUNGEMEMBER10`)<br>• Early access to new drops<br>• Exclusive forum sections<br>• Member badge<br>• Priority event access |
| **Lounge Elite** | `wnb:community:lounge-elite` | $24.99/mo | Recurring Monthly | **6** | `ac8a8d86-961d-417e-84a3-47cd6537db9f` | • Community access<br>• 25% off all Lounge Collection products (`LOUNGEELITE25`)<br>• First access to exclusive drops<br>• VIP forum badge<br>• Priority event invitations<br>• Monthly curated content from Budly T. Cannaguide |
