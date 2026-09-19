# Budly v1.8.0 Release Candidate Deployment Plan

This is a plan only. Production deployment is not authorized.

1. Approve a permanent Python 3.12/container host with managed restart, bounded logs, health monitoring, restricted TLS ingress from WordPress, and outbound HTTPS to OpenAI.
2. Inject the runtime HMAC secret and model credential through the approved production secret mechanism.
3. Establish a stable protected runtime hostname/route without changing unrelated production ingress.
4. Start the runtime with durable memory disabled and verify `/v1/health` before WordPress configuration.
5. Back up the installed WordPress plugin tree/package and record its version and SHA-256.
6. Install the reviewed v1.8.0 plugin artifact with the conversational feature still off.
7. Verify the existing Ask Budly page and guided flow.
8. Configure the server-side runtime URL and shared secret; do not expose either secret to JavaScript.
9. Run nonce, HMAC, ECS, multi-turn, deterministic product, human-handoff, failure-fallback, reset, and isolation smoke checks.
10. After explicit Owner authorization, enable the conversational flag for a bounded production verification window.
11. Disable the flag immediately if any rollback criterion in the rollback guide occurs.

The staging Windows/Docker host is not approved as permanent production hosting.
