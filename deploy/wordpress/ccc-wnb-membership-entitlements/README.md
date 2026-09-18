# CCC Wake'n'Bake Membership Entitlements 0.1.0

Install the plugin ZIP in WordPress and activate it after Flexible Subscriptions and WooCommerce. It does not publish membership products, create subscriptions, charge customers, or modify CBD routing.

## Authoritative integration

Inspected official Flexible Subscriptions **1.8.5** source (`src/Subscription/Subscription.php`, `SubscriptionFinder.php`, `SubscriptionScheduledCancel.php`). The plugin listens to `fsub/subscription/status/updated` (arguments: subscription, new status, previous status) and `fsub/subscription/new` (first argument: subscription). These actions trigger a reconciliation. Each helper also reads `wc_get_orders` with `type=fsb_subscription`, `customer_id`, and `status=any`, so metadata cannot grant access on its own. The subscription is a `WC_Order`; `get_customer_id()`, `get_type()`, `get_status()`, `get_items('line_item')`, and `get_current_period_end()` provide the authoritative fields. Each line item's `get_product_id()` is matched against product ID **and** the current SKU from `wc_get_product()`.

`active` grants access. `pending-cancel` grants access only before its current paid period ends. `on-hold`, `cancelled`, `expired`, missing/unknown statuses, and an overdue pending cancellation grant none. An active subscription after reactivation restores access. Elite outranks Member. No account identity is hard-coded.

Metadata `_ccc_wnb_membership_{level,status,subscription_id,product_id,sku,transition_utc}` is a downstream cache. Call namespaced `CCC\WNB\get_membership_state($user_id)`, `get_membership_level`, `is_active_member`, `is_active_elite`, or `get_approved_discount_percentage` to reconcile against the order store. WordPress `current_user_can('ccc_wnb_member_access')` and `current_user_can('ccc_wnb_elite_access')` derive capabilities dynamically; Elite satisfies both.

## Discount gate

The approved 10%/25% amounts are computed by `Entitlement_Rules::eligible_discount`, with Elite winning and existing membership coupon use suppressing an additional membership discount. **No WooCommerce cart mutation is registered in 0.1.0.** On September 17, 2026, the live store had no authoritative Lounge Collection category; the Wake'n'Bake Lounge tag had zero assigned products. Define and approve an exact eligible product grouping and a stacking policy for sales, other coupons, and special offers before enabling automatic discounts. Existing coupon `LoungeMemberElite25` is published but displays a stored amount of 10; this component does not change it.

The `commercial-truth.json` file is approved, unreleased offer data for later Budly ingestion. Budly does not determine customer entitlement.
