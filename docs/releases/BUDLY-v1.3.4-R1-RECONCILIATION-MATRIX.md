# Budly v1.3.4-R1 reconciliation matrix

Historical package: `budly-sales-agent-1.3.4.zip`, SHA-256 `DDDEF84BB56DEB133D83C706C4206CD22E2C2531AEB3A5FC20D867B7AAD32C91`.

| Historical ZIP file | Git counterpart | Difference | Decision | Reason | Test evidence |
|---|---|---|---|---|---|
| `budly-sales-agent.php` | same | Historical page repair, dedicated template, and visual markup; Git adds Secure Memory and governed decisions | Integrate selected presentation behavior | Preserve the tested Git bootstrap, REST decision route, and security controls | `test_production_template_and_assets_are_integrated`; inherited package tests |
| `assets/budly-sales.css` | same | Different production layout | Integrate namespaced presentation rules | Restores production-facing layout without weakening functional controls | reconciliation UI contract tests |
| `assets/budly-sales.js` | same | Historical code recommends on the client and calls legacy recall AJAX | Supersede, except hero-starter interaction | Server-authoritative evaluation and secure REST recall are accepted controls | governed decision and legacy recall tests |
| `assets/budly-entry.js` | same | Formatting/content divergence | Preserve Git | Git behavior is deidentified and rate-limited | inherited security tests |
| `includes/tracking.php` | same | Historical public endpoint accepts identity and memory fields | Supersede | Conflicts with accepted consent, identity, and isolation controls | Phase 9 and package security tests |
| `templates/ask-budly-page.php` | none | Drive-only | Integrate | Bounded fix for empty Full Site Editing page templates | reconciliation template test and PHP lint |
| `assets/budly-avatar.png` | none | Drive-only | Integrate unchanged | Production visual asset; no executable behavior | exact SHA-256 test |
| `assets/budly-cutout-v134.png` | none | Drive-only | Integrate unchanged | Production visual asset; no executable behavior | exact SHA-256 test |

All 35 Git-only Secure Memory and governed-decision components are preserved. No historical source file replaces its Git counterpart wholesale.
