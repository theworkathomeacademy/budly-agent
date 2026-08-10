# BUDLY v1.7.1 ACCEPTANCE REPORT

**Status:** Implementation and reconstructed LocalWP acceptance passed; ready for Project Owner review.
**Application:** 1.7.1
**Schema:** 1.5.0
**Rules:** `bros-rules-1.5.0.0`
**Commerce configuration:** `commerce-attribution-1.6.0.0`
**Candidate source:** `9c5a21fe3229ff338d45e169792ee1d66458eb26`
**Candidate ZIP:** `budly-sales-agent-1.7.1.zip`
**Candidate SHA-256:** `509C09E5E5FCD5C6A98C22E502D35BB7C7A561402D27837A28B16B7EEB629248`

## Automated evidence

- Full repository suite: 179 passed, 0 failed, 0 skipped.
- Executable PHP stabilization and Bootstrap harnesses: passed.
- PHP syntax validation: 47 files passed.
- JavaScript syntax validation: 4 files passed.
- Version validation: application 1.7.1, schema 1.5.0, rules and commerce configuration unchanged.
- Repository validation: 200 tracked files passed.
- Deterministic packaging: two independent builds and the installed candidate were byte-identical at SHA-256 `509C09E5E5FCD5C6A98C22E502D35BB7C7A561402D27837A28B16B7EEB629248` (737,106 bytes).

## Reconstructed LocalWP lineage

The missing LocalWP registry/database state was reconstructed under explicit authorization as the separate non-production site `budly-phase-3-runtime-reconstructed.local`. The selected source backup was `budly-v16-pre-migration-20260806-202714.sql` (3,035,956 bytes; SHA-256 `18EF32AA987D39E48EEEABFDE91A013F72AFC6210326AA9D8E839A66B7F159EC`). It verified as Budly 1.5.0/schema 1.3.0 with migrations 1.1.0, 1.2.0, and 1.3.0 and complete Secure Memory data.

The controlled lineage was:

1. Immutable v1.5 artifact and schema 1.3.0.
2. Published v1.6 artifact SHA-256 `9C94E7A08CFF1453CAA8D36A82748CE194EC4C99D2FA9639C64875870C0691F7`, producing schema 1.4.0 and the four additive commerce tables.
3. Deterministic package built from production-source commit `ae9ed56650adc50d6b22d11d643fc5631d80cb71`, SHA-256 `02C319EE2925661AE3744370247D1744EDD0AEC9B514FB4B9AE2445EBB5E06CD`, producing application 1.7.0/schema 1.5.0 with both Bootstrap module loaders.
4. Exact v1.7.1 candidate at SHA-256 `509C09E5E5FCD5C6A98C22E502D35BB7C7A561402D27837A28B16B7EEB629248`.

Environment: WordPress 7.0.3, PHP 8.2.29, nginx 1.26.1, MySQL 8.4.0, WooCommerce 11.0.0, HTTPS, prefix `wp_`, non-production LocalWP.

The imported Ask Budly page was published but referenced missing parent post 48. The reconstructed staging relationship was repaired by setting page 52's `post_parent` to 0; no source or production data changed. `/ask-budly/` then returned HTTP 200.

## Backup and restore verification

Fresh pre-patch backups were stored outside Git. The database dump SHA-256 is `87F8F6853E4158C2B11BC9900312893892271A9D1C1FD44EC5569646FCAAA759`; plugin backup SHA-256 is `28A245A4752B61D3B8FC1E04C6C84F48D9597F27CBEBD250993B9CD9A7C3822D`; configuration backup SHA-256 is `F1416B235EB0FD00C85B35FA42D3A7E802EF487439A9C2E39DC5206D0E520DA6`.

The database dump restored successfully into the disposable database `budly_v171_restorecheck`: three representative WordPress core tables, 27 Budly tables, schema 1.5.0, two customers, three consent rows, and 1,297 audit rows were verified. The disposable database was then removed.

## Runtime acceptance

The executable WordPress/MySQL matrix passed 67 of 67 checks before rollback and again passed 67 of 67 after restoration. Coverage included:

- application/schema/rules/configuration identity;
- activation, additive tables, migration uniqueness, and Bootstrap loader completeness;
- all ten canonical patterns;
- missing, invalid, and expired session rejection;
- verified-customer resolution, CSRF enforcement, no customer-1 fallback, and cross-customer read/write isolation;
- conversation persistence and authoritative active/average-confidence aggregates;
- adaptive known-information reuse, journey priority, confidence stopping, recovery, returning-member, and human-handoff behavior;
- all six canonical forward lifecycle transitions, same-state behavior, invalid-jump rejection, persistence, and authoritative distribution;
- unauthorized administrator rejection and authorized aggregate access;
- Secure Memory, consent, commerce tables, REST routes, WooCommerce activation, and Ask Budly HTTP 200.

Synthetic fixtures were removed by the runner. Durable counts returned to two customers, three consent rows, 111 sessions, 13 conversation-memory rows, 23 decision-evidence rows, zero commerce events, zero conversation-state rows, and zero relationship-health rows.

## Rollback and restoration

Rollback used the deterministic `ae9ed566` operational baseline rather than the immutable but loader-incomplete `budly-v1.7` artifact. It completed in 17.71 seconds: application 1.7.0, schema 1.5.0, Ask Budly HTTP 200, and all recorded durable counts remained intact.

Restoration reinstated the exact v1.7.1 candidate in 11.79 seconds. Application 1.7.1/schema 1.5.0, Ask Budly HTTP 200, and the complete 67-check runtime matrix passed again.

## Environment notes and gates

LocalWP's PHP configuration emits a non-blocking startup warning for an unavailable optional `php_imagick.dll`. One initial WP-CLI harness invocation produced a `strict_types` placement fatal inside WP-CLI's eval wrapper; the local-only runner was corrected and both complete 67-check runs passed without an application fatal. Neither condition originates in the deployable Budly package.

Gates A-E: Pass. Gate F for the already-live v1.7 lineage remains historical production evidence; v1.7.1 production deployment and production provenance verification require separate authorization. No production system was accessed or modified.

## Release status

The candidate source commit is the accepted implementation head. This evidence-only documentation update does not alter the deployable plugin tree. The branch is suitable to mark ready for Project Owner review after CI passes. No merge, tag, GitHub release, or production deployment is included.
