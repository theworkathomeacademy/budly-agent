# Budly v1.6 Attribution Specification

Attribution is deterministic and uses only approved order metadata linked to a verified WooCommerce order. States are `attributed`, `unattributed`, and `conflicted`; events may additionally be `pending` or `reconciled`. A WooCommerce/customer mismatch produces `customer_mismatch` and `review_required`; it never silently merges identities. Evidence may reference session, conversation, decision, customer, or approved affiliate identifiers. Values and hidden reasoning are not stored.
