# Budly v1.6 Release Manifest

- Application: `1.6.0`
- Schema: `1.4.0`
- Customer-facing rules: `bros-rules-1.5.0.0`
- Commerce configuration: `commerce-attribution-1.6.0.0`
- Starting tag: `budly-v1.5`
- Starting commit: `b988027ecbb193e99135af10787de718458c6338`
- Branch: `release/budly-v1.6`
- Design package SHA-256: `6E2658740D8F3CFDC680B5803CB404B712B1BEBFD275D673C9412FC109BE0978`
- Handoff SHA-256: `A25342D714F276206BBA914A84EE5C37E6A742483E83B86EEB850757F93CE69E`
- Production deployment: prohibited
- Gate F: blocked
- CI run: `31127453712` passed
- Runtime-accepted code commit: `edd567d9fc4f5c23074f9178ee272b8e1f564cad`
- Runtime candidate SHA-256: `1BBFFD4640440602A4723A98E8D6E53673DFB7E40B855490E2CEE84E81EFAD0C`
- Automated tests: `166 passed, 0 failed, 0 skipped`
- Synthetic staging: `23/23 passed`
- Backup SHA-256: `18EF32AA987D39E48EEEABFDE91A013F72AFC6210326AA9D8E839A66B7F159EC`
- Rollback/restoration: passed (LocalWP opcode-cache reset required after atomic plugin swaps)

The deterministic ZIP manifest supplies the final source commit, per-file SHA-256 values, and package inventory. The final merge-ready build is produced after these acceptance records are committed and is verified twice before PR readiness.
