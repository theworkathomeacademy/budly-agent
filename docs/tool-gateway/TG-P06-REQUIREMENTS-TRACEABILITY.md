# TG-P06 Requirements Traceability

This pre-implementation matrix compares the governed recall handoff with the
authoritative Secure Returning-Customer Memory Assets 1-5 and the accepted
TG-P05A/TG-P05B persistence seams. It is limited to the controlled,
non-production `customer.memory.retrieve` prototype.

| Requirement | Governing source | Existing seam | TG-P06 implementation/test |
|---|---|---|---|
| Verified identity before protected recall | Asset 2 abuse case 5; Asset 4 Gates C-D; Asset 5 sections 12, 21, 45 | Tool Gateway actor/subject grants | Strict `VERIFIED` subject input and subject-scope authorization; T02/T05 |
| Session-scoped memory-use permission | Asset 3 Start Fresh/Memory Enabled; Asset 5 sections 21-24, 32-33 | TG-P05 memory authorization concepts | `ACTIVE`, `NOT_GRANTED`, `WITHDRAWN`, `START_FRESH`; T03/T04/T06 and Scenario D |
| Marketing remains independent | Asset 4 section 8; Asset 5 sections 23-24 | TG-P05A consent separation | Marketing is context-only and never authorizes recall; T04 |
| Purpose-limited, minimized context | Asset 4 section 9; Asset 5 sections 38-40, 53-55 | Capability permissions and strict request parsing | Deterministic recall policy, bounded limits, minimized serializer; T07-T18 |
| Functional and relational asymmetry | TG-P06 handoff sections 12-18, 25 | TG-P05A preferences and TG-P05B facts | Separate source queries, thresholds, natural-bridge rules; T08-T12 |
| Staleness and customer correction | Asset 5 sections 39-40, 57 | Durable stated/recorded timestamps and current status | Decay policy, qualification/suppression, current statement override; T14/T17 |
| No sensitive or withdrawn memory | Asset 2 consent bypass; Asset 5 sections 18.3, 21, 24, 53 | TG-P05B R1-only records and memory permission at write | Read-side status/classification filters; T06/T15 |
| No cross-customer access | Asset 2 abuse case 5; Asset 5 sections 21 and 45 | Explicit synthetic subject grants | Fail-closed `SUBJECT_SCOPE_DENIED`; T05 |
| No raw transcript/internal metadata | Asset 4 sections 9 and 15; Asset 5 sections 55 and 65 | Structured TG-P05 records | Allowlisted output serializer; T18 |
| Read-only with auditable evidence | ADR-008; Asset 5 sections 49-50 | Normalized result, correlation, audit patterns | Isolated recall-audit table only; T19 |
| Start Fresh does not delete memory | Asset 3 screen 7; Asset 5 section 33 | Durable TG-P05 stores | Empty context without source writes; Scenario D |
| Regression preservation | BROS acceptance requirements | TG-P01-TG-P05B suites | T20 plus full discovery suite |

No conflict was found. Production identity integration, production consent
resolution, and production customer memory remain explicitly out of scope.
