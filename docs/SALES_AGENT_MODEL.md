# AI Sales Agent operating model

## Purpose

Budly Sales is the first customer-facing agent in the broader Budly operating
system. Its job is not to force conversions. It helps an adult customer clarify
what they are shopping for, learn from approved information, select an appropriate
option from the configured catalog, and take a transparent purchase or follow-up
step.

## North-star outcome

**Qualified purchase:** a customer reaches an informed checkout decision using
accurate product information and without a policy or safety violation.

Secondary measures:

- Discovery completion rate
- Qualified opportunity rate
- Product-page or checkout click rate
- Purchase conversion rate
- Human escalation rate and resolution time
- Unsupported-claim rate (target: zero)
- Refund, chargeback, and complaint rate
- Repeat purchase rate, once sufficient data exists

## Lifecycle

`new -> discovery -> qualified -> solution_presented -> ready_to_buy -> won`

Alternative routes:

- `discovery -> nurture`
- `any stage -> human_review`
- `qualified -> no_catalog_match -> human_follow_up`

The MVP implements intake, discovery storage, deterministic opportunity scoring,
catalog matching, lifecycle transitions, local response generation, audit logging,
and human escalation. A completed order is never inferred; it must eventually come
from a verified commerce webhook or a human confirmation.

## Conversation pattern

1. Welcome and set expectations.
2. Identify the customer's shopping goal.
3. Learn experience level and preferred format.
4. Ask budget and timeline only when useful.
5. Match against approved catalog attributes.
6. Explain fit and tradeoffs without unsupported claims.
7. Handle ordinary objections such as price, uncertainty, or timing.
8. Offer checkout, education, nurture, or human help.
9. Log the outcome and next action.

## Boundaries

The agent does not provide medical advice, determine legality, verify age, process
payments, approve refunds, negotiate wholesale terms, or invent catalog details.
These boundaries are workflow rules, not merely prompt suggestions.

## $0 launch model

Run the local CLI with SQLite. Add approved products to `config/products.json`.
Use manual human review and paste approved checkout URLs into configuration. No
OpenAI API, Botpress, Airtable, Twilio, or paid CRM is required for validation.

