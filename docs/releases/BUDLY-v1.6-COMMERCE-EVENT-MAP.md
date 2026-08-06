# Budly v1.6 Commerce Event Map

| WooCommerce hook | Governed event | Revenue effect |
|---|---|---|
| `woocommerce_new_order` | `order_created` | None |
| `woocommerce_payment_complete` | `payment_completed` | Verified order value once |
| `woocommerce_order_status_completed` | `order_completed` | Verified order value only when no earlier revenue event exists |
| `woocommerce_order_status_cancelled` | `order_cancelled` | No new revenue; retained as correction evidence |
| `woocommerce_order_status_failed` | `order_failed` | None |
| `woocommerce_order_refunded` | `order_refunded` | New server-verified refund delta |

Every event has a stable external key, verification state, WooCommerce order reference, UTC source and processing timestamps, currency, fixed-precision amounts, attribution and reconciliation states, evidence, and audit correlation. Browser events never enter the revenue ingestion method.
