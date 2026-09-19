# TG-P06 Local Recall Prototype

`customer.memory.retrieve` is a controlled, non-production T0 capability. It
reads only the isolated TG-P05A preference and TG-P05B relationship-fact
stores and writes only minimized recall audit evidence to `tg_p06`.

Required local configuration:

- `TG_P05A_DATABASE_URL`: localhost database `bros_tg_p05a_test`
- `TG_P05B_DATABASE_URL`: localhost database `bros_tg_p05b_test`
- `TG_P06_DATABASE_URL`: localhost database `bros_tg_p06_test`

No secret values belong in source control. The adapter independently verifies
localhost database names and refuses production execution.

Run the dedicated suite:

```powershell
python -m unittest tests.test_tg_p06_customer_memory_recall -v
```

Rollback removes only the isolated audit schema:

```powershell
psql -d bros_tg_p06_test -f migrations/tg_p06/rollback.sql
```

Prototype boundaries:

- synthetic identities and memory only;
- deterministic purpose/relevance policy;
- no production identity provider;
- no memory writes, corrections, deletions, consent changes, or outreach;
- no public endpoint and no production deployment.
