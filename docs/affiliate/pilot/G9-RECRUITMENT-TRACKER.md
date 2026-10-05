# AFF-001 PHASE G — G9 PRIVATE PILOT RECRUITMENT TRACKER

**Date:** 2026-10-01  
**Authority:** d-mac (Project Owner)  
**Execution Phase:** G9 — Private Pilot Recruitment  
**Status:** **G9 ACTIVE — OUTREACH DELIVERED / AWAITING INTAKE RESPONSES**  
**Pilot Cohort Limit:** Exactly 5 Slots  

---

## 1. REAL CANDIDATE SELECTION & STATUS TRACKER (5 OF 5 SLOTS)

| Slot | Candidate Ref | Candidate Identification | Recruitment Archetype | Functional Class Target | Audience Classification | Primary Channels | Existing Ecosystem Relationship | Invitation ID | Token Hash (SHA-256) | Invitation Expiration | Delivery State | Application State |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | `CAN-001` | Marcus T. | Existing Customer / Community Advocate | `STANDARD` | Nano (< 10,000) | Word-of-Mouth, Personal Social, Direct Messaging | Verified customer; purchased Botanical Collection Vol. 1 and participated in community feedback. | `INV-CAN-001-4912287D` | `9e5dce3063139360...` | 2026-10-31 | **SENT** | `INVITED` |
| **2** | `CAN-002` | Elena R. | Nano / Micro Visual Creator | `STANDARD` | Micro (18,500) | Instagram Reels, Lifestyle Videos, Linktree Bio | Prior collaborator on visual botanical product presentations and wellness aesthetics. | `INV-CAN-002-743E3B88` | `a38d6d5730a2a850...` | 2026-10-31 | **SENT** | `INVITED` |
| **3** | `CAN-003` | Dr. Sarah L. | Cannabis & Holistic Wellness Educator | `STANDARD` | Micro (12,200) | Educational Newsletter / Substack, Herbal Workshops | Reviewed *Infused Basics* draft chapters; highly respected holistic health coach. | `INV-CAN-003-C6653B35` | `f0f9b380467ef7ce...` | 2026-10-31 | **SENT** | `INVITED` |
| **4** | `CAN-004` | Chef Julian K. | Content Creator / Culinary Recipe Publisher | `STANDARD` | Mid-Tier (78,000) | Culinary Recipe Blog, YouTube Tutorials, Pinterest | Culinary partner; demonstrates edible infusions and kitchen dosage calculators. | `INV-CAN-004-7371E817` | `ab4c294c6e7bf520...` | 2026-10-31 | **SENT** | `INVITED` |
| **5** | `CAN-005` | David "Dave" V. | Strategic Partner / Community Builder | `STRATEGIC_PARTNER` | Mid-Tier (65,000) | Community Discord, Lounge Events, Audio Spaces | Early Web3 community organizer and host for Wake'n'Bake Lounge events. | `INV-CAN-005-1397E22C` | `7d32417ce7cf59bd...` | 2026-10-31 | **SENT** | `INVITED` |

---

## 2. SECURE TOKEN DELIVERY ARCHITECTURE

1. **Storage Integrity:**
   - Database stores strictly the cryptographic **SHA-256 hash** (`token_hash`) of each high-entropy token.
   - Database status: `ACTIVE`, `SINGLE-USE`, `EXPIRES_AT = 2026-10-31`.
2. **Confidential Dispatch:**
   - Raw invitation tokens were generated ephemerally in-memory and delivered 1-to-1 directly to each candidate's verified contact channel.
   - **Zero raw tokens enter Git repository files.**
   - **Zero raw tokens enter application, database, or server logs.**
   - **Zero raw tokens are displayed in public or reporting artifacts.**
3. **Fail-Closed Boundary:**
   - Public visitors navigating to `/affiliate-registration/` or `/affiliate-account/` are blocked with the governed CLOSED notice.
   - The private application form is accessible only via valid, unexpired, unrevoked, unconsumed invitation token verification.
   - Upon form submission, the token is atomically consumed (`status = 'USED'`), preventing any duplicate or multi-party reuse.

---

## 3. RATIFIED COMMERCIAL DISCLOSURES COMMUNICATED

Each dispatched candidate package communicated the exact ratified Phase G terms:
- **Pilot Commission Rates:**
  - Botanical Collection (Vol. 1): **25%**
  - Infused Basics: **25%**
  - Wake'n'Bake Legends NFT Memberships: **10%**
- **Recurring Subscriptions:** Clarified that lifetime recurring subscription commissions are supported by the broader BROS platform architecture, but pilot offers are one-time purchases and do not exercise subscription earnings.
- **Bonuses & Rewards:** Clarified that future non-cash campaigns may exist, but no automatic cash bonuses apply to this 5-person pilot.
- **Compliance Rules:** Mandatory truthful advertising, clear `#ad` / affiliate relationship disclosures, zero medical/therapeutic claims, and acknowledgement that application submission does not equal approval.

---

## 4. INTAKE & LIFECYCLE CONTROLS (G9 vs G10 BOUNDARY)

- **Application State on Submission:**
  - Technical State: `SUBMITTED`
  - Governed / Public State: `PENDING / PENDING REVIEW`
- **Strict G9 Non-Approval Rule:**
  - No candidate is auto-approved.
  - No candidate is approved during G9.
  - No Affiliate record is created in `bros_affiliate.affiliates`.
  - No referral links or tracking routes are generated.
  - No commission or payout rights are created.
  - Approval, terms acceptance, affiliate provisioning, and activation remain strictly deferred to **G10**.
