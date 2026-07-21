# Blueprint summary

## North star

Budly Agent #7 replaces manual affiliate recruiting with an AI-assisted operating
system that discovers, qualifies, recruits, onboards, activates, and develops
affiliates. The blueprint rejects signup count as the main success measure. Its
north-star outcome is the **Activated Affiliate**: someone who completes onboarding
and produces a first confirmed sale.

## Operating philosophy

- Education before selling
- Automation with human oversight
- Relationships over transactions
- Data-driven optimization
- Growth without proportional administrative headcount

The affiliate program is built on education, community, entrepreneurship, and
automation. It values authenticity, consistency, engagement, and willingness to
learn more than raw follower count.

## Affiliate lifecycle

1. Acquire a prospect and preserve source attribution.
2. Qualify on alignment, engagement, audience fit, responsiveness, and experience.
3. Educate through a personalized, non-pressuring recruitment conversation.
4. Invite qualified prospects to apply.
5. Review and enroll approved applicants.
6. Deliver structured onboarding and compliance guidance.
7. Coach toward a first campaign and confirmed sale.
8. Monitor performance and sustain momentum.
9. Recognize, advance, and develop leaders and mentors.
10. Measure every stage and refine the system.

## Target architecture

- **Botpress:** conversation brain, routing, workflows, knowledge access
- **Airtable:** operational CRM and system of record
- **GoAffPro:** affiliate accounts, links, attribution, commissions, coupons, payouts
- **OpenAI:** language understanding, response drafting, classification, coaching
- **Gmail:** lifecycle email
- **Twilio:** selective SMS reminders
- **Stripe:** underlying purchases and subscriptions
- Optional later: Google Drive, Discord, calendars, and deeper analytics

The architectural rule is deliberate separation of concerns: Botpress orchestrates,
Airtable stores, GoAffPro owns affiliate mechanics, and the model assists with
language and reasoning. Business data must remain portable.

## Governance

Humans retain responsibility for legal review, compliance uncertainty, strategic
partnerships, payment/commission disputes, brand management, and executive
decisions. Every important action should be idempotent, logged, testable, and
recoverable. API credentials never belong in prompts or workflow nodes.

## Build implication

The full blueprint describes an enterprise program, not a one-shot chatbot. The
correct first release is a narrow vertical slice: intake -> qualification ->
education -> invitation/nurture -> CRM write -> audit log -> escalation. Later
releases add applications, GoAffPro enrollment, onboarding, activation, coaching,
recognition, leadership, and analytics.

