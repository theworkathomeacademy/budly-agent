# TG-P05A Local Preference-Memory Prototype

TG-P05A adds only `customer.preference.record` to the accepted canonical Tool
Gateway. It persists explicitly customer-stated, low-risk preferences under an
active, purpose-matched memory authorization. It does not grant marketing
consent or implement retrieval, deletion, correction, relationship facts, or
general profile updates.

## Configuration

- PostgreSQL 17-compatible local server
- Isolated database named `bros_tg_p05a_test`
- Isolated schema `tg_p05a`
- Connection supplied at runtime through `TG_P05A_DATABASE_URL`
- Psycopg version pinned by `requirements-tg-p04.txt`

No password or connection secret belongs in source control. The adapter
independently refuses production, non-local hosts, other database names, and
schemas other than `tg_p05a`.

## Registry

The versioned preference allowlist is
`config/tool_gateway/tg-p05a-preference-registry.json`. Unknown keys, unknown
values, sensitive-category disguises, inferred facts, behavioral signals, and
recommendation-only sources fail closed.

## Migration and rollback

Apply `migrations/tg_p05a/001_customer_preference.sql` only to
`bros_tg_p05a_test`. It creates:

- `tg_p05a.customer_preferences`
- `tg_p05a.preference_audit_events`
- idempotency, one-active-preference, history, correlation, and audit indexes

No existing schema is altered. To remove the prototype, execute
`migrations/tg_p05a/rollback.sql` against the isolated test database. It drops
only schema `tg_p05a`.

## Tests

With both TG-P04 and TG-P05A local database variables configured:

```powershell
python -m unittest tests.test_tg_p05a_customer_preference -v
python -m unittest tests.test_tg_p01_tool_gateway -v
python -m unittest tests.test_tg_p02_operational_metrics -v
python -m unittest tests.test_tg_p03_activity_record -v
python -m unittest tests.test_tg_p04_activity_persistence -v
python -m unittest discover -s tests -v
```

Test cleanup truncates only the two `tg_p05a` tables. That cleanup authority is
not exposed through `customer.preference.record`.
