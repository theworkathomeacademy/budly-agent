# Budly v1.6 Idempotency and Replay Report

External event keys combine WooCommerce order identity, governed event type, and a source-state revision hash. The database enforces uniqueness and the adapter checks before insertion. Payment/completed hooks share an order-level revenue guard. Refund events store only the difference between WooCommerce's current verified refund total and previously recorded refund deltas. Repeated events are audited as replays and return a duplicate result without changing events, links, or totals.
