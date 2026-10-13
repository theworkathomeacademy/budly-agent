# Budly Conversational Runtime Integration Slice 1

This integration is disabled unless WordPress defines
`BUDLY_CONVERSATIONAL_RUNTIME_ENABLED` as `true`. Durable memory must remain
disabled with `BUDLY_DURABLE_MEMORY_ENABLED` unset or `false`.

The Python service requires Python 3.12 and uses the standard library for its
HTTP boundary and OpenAI Responses adapter. Configure server-side values only:

- `BUDLY_RUNTIME_ENV=development` or `staging`
- `BUDLY_RUNTIME_HOST=127.0.0.1`
- `BUDLY_RUNTIME_PORT=8791`
- `BUDLY_RUNTIME_SHARED_SECRET` (at least 32 random characters)
- `BUDLY_MODEL_PROVIDER=openai`
- `BUDLY_MODEL_NAME=gpt-5.6-luna` (initial configurable staging candidate)
- `BUDLY_MODEL_API_KEY`
- `BUDLY_MODEL_TIMEOUT_SECONDS=15`
- `BUDLY_MODEL_RETRY_COUNT=1`
- `BUDLY_KNOWLEDGE_PATH=config` (repository-approved policy/product source directory)

Start with `python -m src.budly_runtime.http_service`. The health path is
`GET /v1/health`; conversation requests require the HMAC server boundary.

For an initial non-production WordPress runtime configuration, provision a separate
`BUDLY_CONVERSATIONAL_RUNTIME_CONFIG_SECRET` constant of at least 32 characters through
the approved staging secret mechanism. Sign the exact `/wp-json/budly-runtime/v1/configure`
request body with that bootstrap secret. After configuration exists, the currently stored
runtime secret may authenticate a rotation. The candidate replacement secret in the request
body never authenticates itself. Never place either secret in source control or command output.

WordPress must define the same secret as
`BUDLY_CONVERSATIONAL_RUNTIME_SECRET` and set
`BUDLY_CONVERSATIONAL_RUNTIME_URL` to the runtime origin (without `/v1`). The
secret is never localized to browser JavaScript.

Approved knowledge is loaded from `config/policies.json` and the bounded
identity/link/format subset of `config/products.json`. WordPress/WooCommerce
remain authoritative for current prices, stock, variants, eligibility and the
selected product. There is currently no approved ECS/terpene corpus; the
runtime returns an honest knowledge limitation for those questions.

Rollback is configuration-only: set
`BUDLY_CONVERSATIONAL_RUNTIME_ENABLED=false`. The original guided JavaScript
flow remains present and requires no database rollback.

No production host, production secret, production model credential, public
endpoint, production deployment, or durable customer-memory migration is
created by this work.
