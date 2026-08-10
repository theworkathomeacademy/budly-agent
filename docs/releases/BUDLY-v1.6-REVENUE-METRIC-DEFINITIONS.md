# Budly v1.6 Revenue Metric Definitions

All amounts derive from verified server-side WooCommerce orders and are grouped by source UTC date and ISO currency. Currencies are never combined or converted.

| Metric | Definition |
|---|---|
| Verified orders | Distinct orders with one accepted payment/completed revenue event |
| Gross order value | Sum of authoritative WooCommerce order totals, once per order |
| Discounts/shipping/tax | Corresponding WooCommerce order fields on the accepted revenue event |
| Refunds | Sum of new verified refund deltas |
| Net revenue | Gross order value minus verified refund deltas |
| Attributed revenue | Net amounts whose order link state is `attributed` |
| Unattributed revenue | Net amounts not deterministically attributed |
| Average order value | Gross order value divided by verified orders; zero when no orders |
| Attribution coverage | Attributed verified orders divided by all verified orders |
| Conflict rate | Conflicted links divided by all order links |

Pending, failed, and cancelled orders do not create revenue. Click, cart, checkout, recommendation, and browser purchase claims are behavioral evidence only. Product-, conversation-, recommendation-, affiliate-, subscription-, and funnel views remain limited to dimensions with verified source evidence; absent evidence is reported as unknown rather than inferred.
