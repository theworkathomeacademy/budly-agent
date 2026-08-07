# Budly v1.6 Idempotency and Replay Report

Runtime result: passed. Duplicate and repeated processing of the same verified order event returned `duplicate` and did not multiply orders or revenue. The accepted synthetic batch produced 24 event rows; replay attempts were audited separately. Full, partial, and multiple refunds recorded only their new verified deltas. Migration reruns were clean no-ops after schema 1.4.0 and retained exactly one migration and configuration row.

External event keys combine WooCommerce order identity, governed event type, and a source-state revision hash. The database enforces uniqueness and the adapter checks before insertion. Payment/completed hooks share an order-level revenue guard. Refund events store only the difference between WooCommerce's current verified refund total and previously recorded refund deltas. Repeated events are audited as replays and return a duplicate result without changing events, links, or totals.
