# Budly v1.4 Release Manifest

## Identity

| Field | Value |
|---|---|
| Release | Budly v1.4 Engineering Platform |
| Application | 1.4.0 |
| Schema | 1.2.0 |
| Rules | `bros-rules-1.3.4.1` |
| Starting baseline | `776f4018da7e0b01a05dad4682751a4d40e85a7d` |
| Staging-tested source | `e9bf0d2b4ee75750fa0696169c16947ab43431d2` |
| Design ZIP | `budly-v1.4-engineering-platform-design.zip` |
| Design SHA-256 | `0A4FA03485235E55DB7BD92A6447BEB06E6BA0DE790C412EEDA4CDA8495FA1E0` |
| Handoff | `CODEX_HANDOFF_V1.4.md.docx` |
| Handoff SHA-256 | `1EF733C6CA7B10899D5C91F13222E046C587865149A6CDFE794336E841C935FF` |

The release introduces engineering controls only. It changes no schema, active rule, recommendation behavior, consent behavior, memory behavior, or production environment.

## Git-built artifact

- Candidate ZIP: `budly-sales-agent-1.4.0.zip`
- Staging candidate SHA-256: `F9066E525047522EC172A696AB7243F2E17E451B8C23782C1FBBA4FBC2536DD9`
- Archive root: `budly-sales-agent/`
- Packaged files including manifest: 44
- Embedded manifest: `budly-sales-agent/release-manifest.json`
- Production deployment: none

Two builds from the staging-tested source were byte-identical. The installed staging tree matched all 44 archive files exactly. The post-merge release workflow must rebuild from the accepted tag target and record the final release hash because the merge commit will differ.

## Runtime closure

- LocalWP: WordPress 7.0.2, PHP 8.2.29, MySQL 8.4.0, nginx 1.26.1
- Theme: Twenty Twenty-Five
- Database prefix: `wp_`
- WP-Cron: enabled; cleanup scheduled
- SMTP: LocalWP Mailpit running and verification delivery passed
- HTTPS: trusted LocalWP certificate; explicit HTTPS page/API requests passed
- Debug: log enabled, browser display disabled
- Fifteen staging subtests: 15 passed
- Rollback: exact v1.3.4-R1 package and file inventory passed
- v1.4 restoration: exact package and file inventory passed
- Production deployment: none
