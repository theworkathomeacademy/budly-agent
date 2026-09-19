# Budly v1.8.0 Production Configuration Names

No values or secrets are included here.

| Name | Component | Requirement | Secret | Safe default |
|---|---|---|---|---|
| `BUDLY_CONVERSATIONAL_RUNTIME_ENABLED` | WordPress | Required activation control | No | `false` |
| `BUDLY_DURABLE_MEMORY_ENABLED` | WordPress | Required safety control | No | `false` |
| `BUDLY_CONVERSATIONAL_RUNTIME_URL` | WordPress | Required before activation | No | unset |
| `BUDLY_CONVERSATIONAL_RUNTIME_SECRET` | WordPress | Required before activation | Yes | unset |
| `BUDLY_RUNTIME_ENV` | Runtime | Required | No | `development` |
| `BUDLY_RUNTIME_HOST` | Runtime | Required | No | `127.0.0.1` |
| `BUDLY_RUNTIME_PORT` | Runtime | Optional | No | `8791` |
| `BUDLY_RUNTIME_SHARED_SECRET` | Runtime | Required | Yes | unset |
| `BUDLY_MODEL_PROVIDER` | Runtime | Required | No | unset; approved value `openai` |
| `BUDLY_MODEL_NAME` | Runtime | Required | No | unset |
| `BUDLY_MODEL_API_KEY` | Runtime | Required | Yes | unset |
| `BUDLY_MODEL_TIMEOUT_SECONDS` | Runtime | Optional | No | `15` |
| `BUDLY_MODEL_RETRY_COUNT` | Runtime | Optional | No | `1` |
| `BUDLY_KNOWLEDGE_PATH` | Runtime | Required | No | `config` |

The runtime rejects missing critical configuration, unsupported providers, excessive timeouts/retries, short HMAC secrets, and unrestricted production binding. Durable memory cannot be enabled through the browser request contract.
