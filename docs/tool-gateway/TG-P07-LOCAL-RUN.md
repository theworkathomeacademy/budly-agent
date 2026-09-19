# TG-P07 Conversation Loop Integration Proof

TG-P07 is a deterministic, synthetic orchestration harness. It registers no
Tool Gateway capability and acquires no authority. Durable operations remain
owned by:

- `customer.preference.record` (TG-P05A)
- `customer.relationship_fact.record` (TG-P05B)
- `customer.memory.retrieve` (TG-P06)

The harness models verified synthetic sessions, `ACTIVE` versus `START_FRESH`
memory use, bounded current-session turns and topic summaries, ephemeral
instructions, explicit durable candidates, capability results, and correlation
references.

Run locally with the accepted TG-P04 through TG-P06 localhost PostgreSQL test
configuration, then execute:

```powershell
python -m unittest tests.test_tg_p07_customer_memory_conversation_loop -v
```

Boundaries:

- no production LLM, frontend, identity, CRM, or session manager;
- no raw historical transcript loading;
- no umbrella memory capability;
- no consent, lifecycle, commerce, marketing, or customer-profile mutation;
- no migration, public endpoint, deployment, or production credentials.
