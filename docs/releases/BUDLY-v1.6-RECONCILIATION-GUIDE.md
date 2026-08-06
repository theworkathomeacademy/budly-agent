# Budly v1.6 Reconciliation Guide

Reconciliation compares verified WooCommerce orders/refunds to immutable commerce events and daily aggregates by order ID, currency, status, and source timestamp. Missing records remain `pending`; identity or evidence disagreement becomes `conflicted` and requires administrative review. Reprocessing uses stable event keys and cannot multiply revenue. Rebuild each affected UTC day separately per currency and audit every review or recovery action.
