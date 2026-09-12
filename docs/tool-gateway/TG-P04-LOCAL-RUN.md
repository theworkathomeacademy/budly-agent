# TG-P04 Local Persistence Prototype

TG-P04 is a controlled, non-production durability proof for the already accepted
`activity.record` capability. It adds no activity types or authority.

## Required local configuration

- PostgreSQL 17-compatible local server
- Isolated database named `bros_tg_p04_test`
- Environment variable `TG_P04_DATABASE_URL`
- Psycopg version pinned by `requirements-tg-p04.txt`

`PostgresActivityAdapter` independently rejects production, non-local database
hosts, database names other than `bros_tg_p04_test`, and schemas other than
`tg_p04`. The caller cannot select the adapter or database.

No password or connection secret belongs in source control. Supply the complete
local connection string through `TG_P04_DATABASE_URL` at test runtime.

## Migration

Apply `migrations/tg_p04/001_activity_persistence.sql` only to the isolated
`bros_tg_p04_test` database. It creates only:

- `tg_p04.activities`
- `tg_p04.audit_events`
- the activity idempotency unique constraint
- correlation/activity lookup indexes

No existing schema or table is altered.

For complete prototype removal, execute `migrations/tg_p04/rollback.sql` against
the isolated test database. The rollback drops only schema `tg_p04`.

## Test execution

With `TG_P04_DATABASE_URL` set and Psycopg available on `PYTHONPATH`:

```powershell
python -m unittest tests.test_tg_p04_activity_persistence -v
python -m unittest tests.test_tg_p01_tool_gateway -v
python -m unittest tests.test_tg_p02_operational_metrics -v
python -m unittest tests.test_tg_p03_activity_record -v
python -m unittest discover -s tests -v
```

Tests truncate only `tg_p04.audit_events` and `tg_p04.activities`. Cleanup SQL
is test-fixture lifecycle behavior and is not exposed through `activity.record`.

## Prototype limits

The adapter has no write fallback and exposes no update, delete, patch, or
replace operation. The proof uses a single local PostgreSQL server and does not
claim production-scale failover, multi-region consistency, or distributed
transaction behavior.
