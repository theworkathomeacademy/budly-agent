# Budly v1.6 Traceability Matrix

Target: application `1.6.0`, schema `1.4.0`, customer rules `bros-rules-1.5.0.0`, commerce configuration `commerce-attribution-1.6.0.0`.

| Requirement | Authority | Implementation | Test/evidence |
|---|---|---|---|
| Immutable commerce events | DATA_MODEL, EVENT_MODEL, DB Specification | `CommerceRepository`, `budly_commerce_events` | unique event-key and replay tests |
| WooCommerce financial authority | v1.6 specification, MA-002 decision | `WooCommerceAdapter::ingest()` re-reads `WC_Order` | authority and tamper-boundary tests |
| Order linkage and evidence | DATA_MODEL, ISR-001 | `AttributionService`, `budly_order_links` | attribution/conflict tests |
| Affiliate preservation | DATA_MODEL, DASHBOARD_SPEC | `budly_affiliate_attribution`, event affiliate reference | schema tests |
| Currency-separated reporting | DASHBOARD_SPEC, Administration Specification | `RevenueService`, `budly_revenue_daily`, admin report | metric/currency tests |
| Protected administration | Administration Specification | `/admin/commerce/report`, `/admin/commerce/health` | capability/bounds tests |
| Additive migration | MA-002 migration contract | `Migrator`, schema `1.4.0` | migration-contract suite |
| No customer-facing change | historical handoff | isolated `includes/Commerce`; no template/asset edits | regression test and Git diff |

Technical refinements: WordPress prefixes are applied through `Config::table`; currency is bounded to three characters; monetary fields use `DECIMAL(20,6)`; external event keys and order links are unique; UTC WordPress timestamps and deterministic indexes support replay, reconciliation, and reporting. These refinements implement the promoted model without removing a package record.
