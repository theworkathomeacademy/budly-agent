# TG-P07 Requirements Traceability

This pre-implementation matrix compares the TG-P07 orchestration handoff with
the authoritative Secure Returning-Customer Memory Assets 1-5 and accepted
TG-P05A, TG-P05B, and TG-P06 interfaces.

| Requirement | Governing source | Reused authority | TG-P07 proof |
|---|---|---|---|
| No umbrella capability or new authority | ADR-008; TG-P07 sections 1-2, 19 | Canonical Tool Gateway | Harness invokes only accepted capability IDs; T02/T07/T20 |
| Session context is not durable permission | Asset 3 Start Fresh; Asset 5 sections 21-24, 32-33 | TG-P06 session-use state | Per-session mode and ephemeral state; T01/T13/T14 |
| Explicit customer-stated memory only | Asset 4 sections 8-9; Asset 5 sections 17, 20, 57 | TG-P05A/B validation | Candidate routing requires explicit confirmation; T02/T07/T10/T11 |
| Current statement outranks stored memory | Asset 5 sections 39-40, 57 | TG-P06 conflict suppression; TG-P05A/B supersession | T05/T06/T16 |
| Functional/relational recall asymmetry | TG-P06 accepted policy | TG-P06 recall adapter | T04/T08/T09/T14 |
| Start Fresh suppresses without deleting | Asset 3 screen 7; Asset 5 section 33 | TG-P06 `START_FRESH` | T13/T14 |
| Cross-customer/session isolation | Asset 2 abuse case 5; Asset 5 section 45 | Subject grants and verified synthetic identity | T15 |
| Frequency is not consent or truth | TG-P07 sections 7 and 10 | TG-P05A classification and idempotency | T10-T12 |
| Failures cannot become fabricated memory | Asset 2 consent bypass; Asset 5 section 59 | Tool health and transactional adapters | T17/T18 |
| No raw transcript dependency | Asset 4 section 9; Asset 5 sections 55, 65 | Structured session summary and governed memory | T19 |
| Regression preservation | BROS acceptance requirements | TG-P01-TG-P06 suites | T20 and full discovery suite |

No conflict was found. The harness is a test/integration component, not a
customer-facing endpoint, production session manager, or new Tool Gateway
capability.
