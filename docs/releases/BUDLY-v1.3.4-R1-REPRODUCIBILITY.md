# Budly v1.3.4-R1 reproducibility report

The deterministic builder is `scripts/build_wordpress_plugin.py`. Automated acceptance builds twice from the same tree and asserts byte-for-byte identity, validates the embedded source/version manifest, and verifies development ZIPs are excluded.

Pre-merge validation uses an explicit candidate source identifier. Final reproducibility must be repeated from the merged tag target; the two final hashes and resulting ZIP SHA-256 must be appended to release evidence before the tag is declared verified.

Pre-merge result: two independent builds were byte-identical at SHA-256 `6F002182E01D93A752B901AD9F44F47264E2F670BE7CB20CD00610A9D1CFA681` using source identifier `CANDIDATE`.
