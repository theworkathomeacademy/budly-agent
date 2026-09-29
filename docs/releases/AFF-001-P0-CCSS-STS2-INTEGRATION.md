# AFF-001 P0 CCSS + STS-2 integration evidence

## Baselines

- Accepted CCSS/Budly parent: `a4f24088268a2b30a3f69e2a433d59db60394fdf`
- Verified STS-2 tip: `5562b940a958544bf5c3e1834b558db0ecceb117`
- Integration branch: `aff-001-p0-ccss-sts2-integration`
- Scope: non-production reconciliation only

## Conflict resolutions

1. `CHANGELOG.md`: retained the accepted CCSS runtime-recovery history and added an explicit P0 integration entry describing the STS-2 correlation capability; no historical entry was discarded.
2. `assets/budly-sales.js`: retained the accepted CCSS conversational journey, output escaping, approved-link validation, and fallback behavior; added only attribution forwarding, the signed correlation query parameter, and correlation-aware recommendation rendering.
3. `budly-sales-agent.php`: retained the accepted `1.8.8` plugin identity and bootstrap. STS-2 commerce loading remains supplied by the merged Secure Memory bootstrap, avoiding duplicate registration.
4. `includes/Runtime/ConversationProxy.php`: retained CCSS stored runtime configuration, authenticated configure route, URL validation fallback, outbound DNS recovery, response-link validation, and `1.8.8` user agent; added bounded attribution input, deterministic decision reuse, and signed correlation-token issuance.
5. `scripts/build_plugin.py`: retained application `1.8.8` and changed only the commerce configuration manifest value to the merged STS-2 `commerce-correlation-1.8.2.0` value used by runtime configuration.
6. `src/sales_agent.py`: reconciled the stale CCSS source declaration from `1.8.4` to the accepted plugin/package version `1.8.8`; STS-2 does not cause a version downgrade.
7. `tests/test_bros_v1_3_4.py`: reconciled application/plugin version assertions to the accepted `1.8.8` baseline and retained the narrower sensitive-field response boundary.
8. `tests/test_conversation_intelligence_v17.py`: reconciled the stale Python runtime assertion to the accepted `1.8.8` baseline.
9. `tests/test_engineering_platform_v14.py`: retained CCSS version and deterministic-manifest assertions; imported STS-2 tests separately validate correlation artifacts.
10. `tests/test_reconciliation_release.py`: retained the accepted `1.8.8` package-manifest assertion.

## Governance assessment

No conflict required changing Affiliate business rules, production Affiliate behavior, public registration, commission calculation, payout behavior, customer identity authority, or the governed revenue-event contract. The resolution is additive and confined to the non-production integration branch.

The accepted CCSS parent also contained governed, tracked SQL migrations while its repository validator rejected every tracked `.sql` file. The integration reconciles that internal contradiction by allowing SQL only beneath `migrations/`; database files, SQL elsewhere, secrets, archives, and other forbidden artifacts remain blocked. A regression test covers the narrow exception.

## Verification requirement

This document records resolution intent only. The combined baseline is not verified until repository, Python, PHP, Node, CCSS, STS-1, STS-2, and packaging checks pass and the merge commit is created.
