# Budly v1.6 Reconciliation Guide

Runtime evidence: the accepted synthetic batch reconciled to WooCommerce authority with USD gross 225.000000, refunds 75.000000, net 150.000000 and EUR gross/net 80.000000. Currencies remained separate. Four USD orders and one EUR order were included; pending, failed, and pre-payment cancelled orders contributed zero. One customer mismatch remained `conflicted/review_required` rather than being silently merged. Rebuilding daily aggregates produced the same totals.

Reconciliation compares verified WooCommerce orders/refunds to immutable commerce events and daily aggregates by order ID, currency, status, and source timestamp. Missing records remain `pending`; identity or evidence disagreement becomes `conflicted` and requires administrative review. Reprocessing uses stable event keys and cannot multiply revenue. Rebuild each affected UTC day separately per currency and audit every review or recovery action.
