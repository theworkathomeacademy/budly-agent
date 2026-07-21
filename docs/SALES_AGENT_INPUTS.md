# Inputs needed before customer deployment

## Catalog links already loaded

The live product names and URLs from both pages of `cccultivate.com/shop/` were
verified and loaded on July 16, 2026. The main brand site is configured as
`wakenbakelounge.com`; the sales and checkout journey remains on `cccultivate.com`.

The URL inventory is not sufficient approval for the agent to state current
prices, product availability, ingredients, benefits, shipping terms, or refund
rules. Those fields still require review.

## Required catalog information

For every product or offer:

- Stable product ID and exact public name
- Active/inactive status
- Current price and currency
- Approved product URL and checkout URL
- Category and format
- Plain-language description
- Approved features and substantiated claims
- Ingredients and allergen information, where applicable
- Intended audience and explicit exclusions
- Available variants
- Shipping regions and current fulfillment policy
- Return/refund policy reference
- Tags used for deterministic matching

## Required business decisions

- Which products the agent may sell
- Minimum age and how age is verified outside the chat
- Geographic restrictions and who owns legal/compliance review
- Approved answers to the 20 most common questions
- Human escalation owner and expected response time
- Discount authority: preferably none for the MVP
- Checkout platform and method for verified purchase events
- Consent, privacy, retention, deletion, and transcript-access rules

## Initial evaluation set

Before launch, write at least 30 test conversations covering:

- Clear product fit
- No catalog match
- Price objection
- Comparison request
- Shipping and refund question
- Medical-condition question
- Dosage request
- Minor/age ambiguity
- Location/legality question
- Adverse-event report
- Prompt injection requesting invented claims or discounts
- Checkout readiness and abandoned purchase
