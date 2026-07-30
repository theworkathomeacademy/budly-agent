# Budly v1.4 Release Manifest

## Identity

| Field | Value |
|---|---|
| Release | Budly v1.4 Engineering Platform |
| Application | 1.4.0 |
| Schema | 1.2.0 |
| Rules | `bros-rules-1.3.4.1` |
| Starting baseline | `776f4018da7e0b01a05dad4682751a4d40e85a7d` |
| Candidate source | `584b74403098b7b461b63fb5e1835d192efecf82` |
| Design ZIP | `budly-v1.4-engineering-platform-design.zip` |
| Design SHA-256 | `0A4FA03485235E55DB7BD92A6447BEB06E6BA0DE790C412EEDA4CDA8495FA1E0` |
| Handoff | `CODEX_HANDOFF_V1.4.md.docx` |
| Handoff SHA-256 | `1EF733C6CA7B10899D5C91F13222E046C587865149A6CDFE794336E841C935FF` |

The release introduces engineering controls only. It changes no schema, active rule, recommendation behavior, consent behavior, memory behavior, or production environment.

## Git-built artifact

- Candidate ZIP: `budly-sales-agent-1.4.0.zip`
- Candidate SHA-256: `B71929A2D7203181E600E6D15A18D4318728CF525E33A420315A4AD353AF76EF`
- Archive root: `budly-sales-agent/`
- Packaged files including manifest: 44
- Embedded manifest: `budly-sales-agent/release-manifest.json`
- Production deployment: none

The post-merge release workflow must rebuild from the accepted tag target and record the final release hash.
