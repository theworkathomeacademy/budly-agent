# MX-5C Antigravity Verification Handoff

TO: Antigravity  
FROM: Codex / MWB-005  
WORKSTREAM: Wake'n'Bake Lounge Unified Budly Integration  
STATUS: Development complete; independent verification required; staging proof blocked by unavailable non-production credentials

## Repository identity

- Repository: `theworkathomeacademy/budly-agent`
- Branch: `feature/mx-5c-budly-lounge-home-proof`
- Verified starting baseline: `1415640c1641e57711b2cb98203557e6ac9b324f`
- MX-5C implementation commit: `8743f54a82ce48960bc3861d286ef80767362abf`
- Production deployment: not performed and not authorized

## Development changes

1. Replaced the unsupported `eligible Lounge Collection purchases` wording with
   `eligible purchases, subject to the governed exclusions`. Prices, percentages,
   tier benefits, and the authoritative exclusion list were not changed.
2. Added a genuine local HTTP round trip through the runtime service using the same
   exact-body HMAC contract produced by the WordPress proxy.
3. Extended the executable PHP proxy test to prove Lounge Home page-context forwarding,
   exact-body HMAC generation, header/body correlation identity, and rejection of
   privilege fields, untrusted hosts, correlation mismatches, and untrusted links.
4. Prevented a candidate replacement runtime secret from authenticating its own
   configuration request. Initial configuration now requires a separately provisioned
   `BUDLY_CONVERSATIONAL_RUNTIME_CONFIG_SECRET`; an existing stored runtime secret may
   authenticate later rotation. Neither secret is returned to the client.
5. Aligned the actual OpenAI adapter proof with the configured Budly staging model,
   `gpt-5.6-luna`.

## Evidence classification

### Actual executable evidence

- Focused Python suite: 45 tests passed.
- PHP proxy integration harness: 20 assertions passed, 0 failed.
- PHP syntax validation: `ConversationProxy.php` passed.
- Local runtime proof used a real loopback HTTP server, real request serialization,
  real HMAC authentication, replay tracking, correlation checking, and response JSON.
- WordPress proxy behavior was executed under the repository's WordPress-function
  harness; only the network transport and WordPress host services were simulated.

### Simulated or intercepted evidence

- The adapter payload test executed the real `OpenAIResponsesAdapter` code but intercepted
  outbound transport. It proves governed prompt/schema/model payload construction, not a
  live model response.
- The PHP proxy harness uses deterministic WordPress and HTTP response doubles. It proves
  proxy contract behavior, not a deployed WordPress-to-staging-runtime request.

### Previously reported evidence, not rerun here

- The baseline command reports a genuine direct `gpt-5.6-luna` Lounge Home response.
  This run did not independently recreate that credentialed call.

## Full regression result

`py -m unittest discover -s tests` ran 996 tests and ended with 5 failures and 11
errors. The MX-5C-focused suite is green. The discovery failures are unrelated baseline
or infrastructure conditions and were not repaired under this workstream:

- missing `budly_runtime` import-path setup in three commercial tests;
- missing `TG_P04_DATABASE_URL`, `TG_P05A_DATABASE_URL`, and `TG_P05B_DATABASE_URL`
  database fixtures for five acceptance classes;
- repository validator rejects pre-existing tracked migration files;
- pre-existing plugin/application/changelog version drift (`1.8.8` versus `1.8.4`);
- older release tests expect versions `1.5.0` or `1.8.4`;
- `dist/budly-sales-agent-1.8.8.zip` is absent;
- viewport module calls `sys.exit(0)` during unittest discovery, although its own 72
  viewport assertions reported pass.

## Staging proof blocker

No live model API credential was available to the test process, and this checkout contains
no authorized staging WordPress session, staging runtime endpoint credential, or securely
injected runtime configuration/provisioning secret. Production credentials were neither
accessed nor reused. Therefore a genuine deployed WordPress proxy-to-runtime proof was not
attempted.

Credential-custodian action required: make an approved non-production staging execution
context available to the verifier with (a) the staging WordPress access/session, (b) the
staging runtime URL, (c) a staging-only runtime HMAC secret, (d) a distinct staging-only
configuration bootstrap secret, and (e) the staging model credential injected through the
approved secret manager. Do not place values in chat, Git, test fixtures, or terminal logs.

## Independent Antigravity verification steps

1. Fetch the branch and verify the baseline-to-implementation diff.
2. Confirm the governed JSON contains `eligible purchases, subject to the governed exclusions`
   and that the five exclusion categories remain unchanged.
3. Run the 45-test focused Python command documented in the completion report.
4. Run `php tests/php/test_proxy_page_context.php` and confirm 20/20.
5. Confirm configuration signed with the candidate replacement secret is rejected when no
   independent bootstrap/current secret exists.
6. In approved non-production staging, configure secrets through the secret manager, send
   the Lounge Home question through the actual WordPress REST route, and correlate the same
   request ID through WordPress and runtime evidence.
7. Verify the live staging response uses governed membership wording and only approved links.
8. Independently report PASS, PARTIAL, or FAIL. Do not recommend owner acceptance without
   the genuine deployed staging round trip.
