# CCC Wake'n'Bake Membership Entitlements 0.3.0

Install the plugin ZIP in WordPress and activate it after Flexible Subscriptions and WooCommerce. It does not publish membership products, create subscriptions, charge customers, or modify CBD routing.

## Authoritative integration

Inspected official Flexible Subscriptions **1.8.5** source (`src/Subscription/Subscription.php`, `SubscriptionFinder.php`, `SubscriptionScheduledCancel.php`). The plugin listens to `fsub/subscription/status/updated` (arguments: subscription, new status, previous status) and `fsub/subscription/new` (first argument: subscription). These actions trigger a reconciliation. Each helper also reads `wc_get_orders` with `type=fsb_subscription`, `customer_id`, and `status=any`, so metadata cannot grant access on its own. The subscription is a `WC_Order`; `get_customer_id()`, `get_type()`, `get_status()`, `get_items('line_item')`, and `get_current_period_end()` provide the authoritative fields. Each line item's `get_product_id()` is matched against product ID **and** the current SKU from `wc_get_product()`.

`active` grants access. `pending-cancel` grants access only before its current paid period ends. `on-hold`, `cancelled`, `expired`, missing/unknown statuses, and an overdue pending cancellation grant none. An active subscription after reactivation restores access. Elite outranks Member. No account identity is hard-coded.

PASS is derived only from a `shop_order` in Processing or Completed state containing Product 1047 whose live SKU is `WNB-MBR-PASS`. It is never inferred from account existence. Active Member/Elite outrank PASS; when paid entitlement ends, a valid PASS acquisition becomes the fallback.

Metadata `_ccc_wnb_membership_{level,status,subscription_id,product_id,sku,badge_key,badge_label,transition_utc}` is a downstream cache. Call namespaced `CCC\WNB\get_membership_state($user_id)`, `get_membership_level`, `get_membership_badge`, `has_community_access`, `is_active_member`, `is_active_elite`, `can_access_level`, or `get_approved_discount_percentage` to reconcile against the order store.

WordPress capabilities `ccc_wnb_pass_access` (with the compatible alias `ccc_wnb_community_access`), `ccc_wnb_member_access`, and `ccc_wnb_elite_access` derive dynamically. Elite satisfies all levels; Member satisfies Member and Pass; Pass satisfies Pass only. Protect minimum page content with `[ccc_wnb_protected level="pass"]...[/ccc_wnb_protected]`, using `member` or `elite` for higher levels. Badge keys and labels derive from the same state; no visual badge artwork is created.

## Automatic discount exclusions

The cart receives 10% for Member or 25% for Elite. The hook applies only when the cart has no coupon and an item is at its unchanged regular price. It excludes the Membership and bulk product categories, Product IDs 1047–1049, and the verified class payment-plan IDs 455, 457, and 460. Full-payment course IDs 150, 151, and 152 remain eligible. It does not alter coupon definitions or CCC Payment Routing Guard behavior.

The `commercial-truth.json` file is approved, unreleased offer data. For matching Lounge membership questions, the plugin adds it to Budly's already-signed deterministic runtime context. It is not injected into unrelated or LEGENDS-only questions. Budly explains the rules but does not determine entitlement or discounts, and the payload explicitly blocks public availability claims while the paid products remain unpublished.
