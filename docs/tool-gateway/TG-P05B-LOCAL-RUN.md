# TG-P05B Local Relationship-Memory Prototype

TG-P05B adds only `customer.relationship_fact.record` to the accepted canonical
Tool Gateway. It records bounded R1 relationship context explicitly stated or
confirmed by a synthetic customer. It does not implement recall, deletion,
correction, external enrichment, downstream action, or related-person identity.

## Configuration

- PostgreSQL 17-compatible local server
- Isolated database `bros_tg_p05b_test`
- Isolated schema `tg_p05b`
- Connection supplied through `TG_P05B_DATABASE_URL`
- Psycopg pinned by `requirements-tg-p04.txt`

No password or connection secret belongs in source control. The adapter rejects
production, remote hosts, other database names, and schemas other than
`tg_p05b`.

## Registry and safety boundary

`config/tool_gateway/tg-p05b-relationship-fact-registry.json` versions:

- R1 recordable fact definitions and field validators
- R2/RX deny-only definitions
- allowed purposes
- minor-related field constraints
- a bounded source-context-summary allowlist
- initial status and supersession behavior

Related-person context remains JSON inside the authorized customer's fact row.
The migration creates no person, customer, lead, contact, consent, lifecycle,
commerce, marketing, or recommendation table.

## Migration and rollback

Apply `migrations/tg_p05b/001_relationship_fact.sql` only to
`bros_tg_p05b_test`. It creates:

- `tg_p05b.relationship_facts`
- `tg_p05b.relationship_fact_audit_events`
- idempotency, singleton-fact, history, correlation, and audit indexes

No existing schema is altered. `migrations/tg_p05b/rollback.sql` drops only the
isolated `tg_p05b` schema.

## Tests

With TG-P04, TG-P05A, and TG-P05B database variables configured:

```powershell
python -m unittest tests.test_tg_p05b_relationship_fact -v
python -m unittest tests.test_tg_p01_tool_gateway -v
python -m unittest tests.test_tg_p02_operational_metrics -v
python -m unittest tests.test_tg_p03_activity_record -v
python -m unittest tests.test_tg_p04_activity_persistence -v
python -m unittest tests.test_tg_p05a_customer_preference -v
python -m unittest discover -s tests -v
```

Test cleanup truncates only the two `tg_p05b` tables and is not capability
authority.
