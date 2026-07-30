# Phase 3 API inventory

Base path: `/wp-json/budly-identity/v1`. HTTPS and JSON are required. Customer mutations require the session-bound `X-Budly-CSRF` header. Supported replay-sensitive mutations accept `Idempotency-Key`. Administrator mutations require a logged-in WordPress administrator, `manage_options`, and `X-WP-Nonce`.

| Method | Path | Authorization | Purpose |
|---|---|---|---|
| POST | `/auth/request-code` | Public, rate limited | Request neutral passwordless verification |
| POST | `/auth/verify` | Valid one-time request/code | Consume code and create Secure/HttpOnly session |
| GET | `/auth/session` | Verified session | Read safe session state |
| POST | `/auth/logout` | Session + CSRF | Revoke current session |
| GET | `/identity` | Verified session | Read public customer identifier and safe identity fields |
| GET/PATCH | `/profile` | Session; PATCH adds CSRF/storage consent | Read/update allowlisted profile |
| GET/PATCH | `/preferences` | Session; PATCH adds CSRF/storage consent | Read/update structured preferences |
| GET/PATCH | `/consent` | Session; PATCH adds CSRF | Read/update three independent consent types |
| GET | `/memory/preview` | Verified session | Customer-review allowlist; use approval not required |
| POST | `/memory/use` | Session + CSRF + use consent | Approve memory for one session/agent/conversation/purpose |
| POST | `/memory/start-fresh` | Session + CSRF | Deny memory use for current context without deleting it |
| GET | `/memory/shared` | Session + use consent + approved context + agent scope | Retrieve shared namespace |
| GET | `/memory/agent/{namespace}` | Same plus namespace scope | Retrieve authorized agent memory |
| POST | `/memory/summary` | Session + CSRF + storage consent + agent scope | Store structured, provenance-bound summary |
| PATCH | `/memory/{memory_id}` | Session + CSRF + ownership + storage consent | Correct one remembered item |
| DELETE | `/memory/{memory_id}` | Session + CSRF + ownership + confirmation | Selectively delete one item |
| GET | `/memory/export` | Verified session | Export customer-visible self data |
| DELETE | `/memory` | Session + CSRF + confirmation | Delete all personalization memory and revoke sessions |
| GET | `/admin/health` | `manage_options` | Safe health and aggregate metrics |
| GET | `/admin/audit` | `manage_options` | Filtered, bounded, paginated audit review |
| POST | `/admin/revoke-session` | Administrator + REST nonce | Revoke one session identifier |
| POST | `/admin/revoke-all` | Administrator + REST nonce | Revoke all sessions for public customer ID |
| POST | `/admin/test-email` | Administrator + REST nonce | Send transactional transport test |
| POST | `/admin/run-cleanup` | Administrator + REST nonce | Run bounded cleanup and record summary |

All responses use the approved `success`, `data`/`error`, and `meta` envelope. Raw session tokens, token hashes, verification codes, raw email addresses, restricted memory, and database IDs are not returned.
