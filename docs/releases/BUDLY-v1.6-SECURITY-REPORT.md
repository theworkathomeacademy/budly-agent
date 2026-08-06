# Budly v1.6 Security Report

Commerce amounts, currency, status, identity, and refunds are read from `WC_Order`; public ingestion and client-supplied financial values are absent. Stable unique keys reject replay, prepared SQL protects queries, identifiers and dates are bounded, administrator reports require WordPress capability checks, page sizes are capped, and significant events are audited without payment credentials. Raw card data is never stored. WooCommerce absence degrades reporting without changing the customer conversation. Gate F and production deployment remain blocked.
