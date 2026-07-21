# Product knowledge audit

Verified July 16, 2026 against the public CCCultivate shop and WooCommerce Store API.

- 32 public-shop products are in the agent catalog.
- 35 records were returned by the Store API.
- Three non-public records are deliberately excluded: the friends-and-family body butter, Holiday Health & Healing, and CBD Tincture Spray.
- Current store price, price range, WooCommerce type, purchasability, stock flag, variants, package facts, and minimums were captured where exposed.
- External products are not described as directly purchasable because their final destination and terms were not confirmed by the Store API.

## Approval gaps

The website contains therapeutic marketing language, but no evidence was supplied showing that medical claims were legally or internally approved. The agent therefore has no approved therapeutic benefits. It may discuss product format, package facts, ingredients explicitly shown by the store, and current price; it must not promise relief, relaxation, sleep, pain reduction, stress reduction, treatment, or other health outcomes.

The business owner approved customer-facing purchase and support policies on July 17, 2026. They are stored in `config/policies.json` and published locally at `/policies.html`. Complete product labels, allergen information, certificates of analysis, detailed shipping restrictions, and product-specific NFT tier perks still require source documentation. The agent flags those narrower gaps instead of guessing.
