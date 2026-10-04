# G9E.1 Synthetic Scope Traceability — 2026-10-04

## Repository assessment

The Python Affiliate engine owns gate checks and financial lifecycle behavior. WordPress owns the public/authenticated presentation and previously gated its portal only by a global option plus login state. PostgreSQL/Supabase is the authoritative location for Affiliate identity and durable scope/audit data.

## Security traceability

| Requirement / threat | Control | Source | Test |
|---|---|---|---|
| Client-forged synthetic status | Scope is supplied only from trusted server-side repository state; request fields cannot create a scope | `synthetic_scope.py`, `01_synthetic_scope_guard.sql` | real/unmapped/wrong-Affiliate denial tests |
| Cross-user portal access | Exact WordPress user → Affiliate UUID → AFF code match | `SyntheticScope.php`, `synthetic_scope.py` | portal normal user, Affiliate B, owner denial tests |
| Real referral admission | Exact token, synthetic destination, campaign, identity and classification match | `synthetic_scope.py` | synthetic/real referral tests |
| Real commerce attribution | Exact trusted classification plus allowlisted event/order | `synthetic_scope.py` | synthetic/real revenue and attribution tests |
| Real commission creation | Allowed only after an allowed upstream synthetic attribution | `synthetic_scope.py` | synthetic/real commission tests |
| Payout execution | Constructor rejects payout gate ON; `payout_allowed()` always false | `synthetic_scope.py` | payout-off test |
| Replay | Unique server idempotency key returns prior decision | `DurableScopeAudit` | duplicate replay test |
| Administrative abuse / repudiation | Append-only allow/deny audit with actor, gate, scope, reason and time | SQLite proof plus PostgreSQL contract | durable denial and immutable-update test |
| Secret leakage | Audit evidence schema excludes raw invitation token, cookies, credentials and secrets | Python allowlist and PostgreSQL check | audit-secret exclusion test |
| Ambiguity | Missing/invalid mapping, classification, identity, or event is DENY | centralized guard | negative suite |

## Deviation and deployment status

No production scope row is created by this change. The WordPress option adapter is inert while the global gate is OFF; the production deployment must populate it only from the authoritative BROS/Supabase scope record. No gate activation, real identity, real order, outreach, or payout is included.
