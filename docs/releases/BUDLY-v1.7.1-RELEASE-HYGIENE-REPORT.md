# BUDLY v1.7.1 RELEASE HYGIENE REPORT

## v1.6 checksum reconciliation

The published `budly-v1.6` asset and its sidecar agree on SHA-256 `9C94E7A08CFF1453CAA8D36A82748CE194EC4C99D2FA9639C64875870C0691F7`. Its embedded manifest identifies application 1.6.0, schema 1.4.0, and final merge commit `35223477a1e305f53fdf277f13db3d00d95bf457`.

The historical `1FE93F95914C5791701447C137FE3304BA00D3531EBB26F619DC106BFD9B0550` checksum is therefore classified as a **historical packaging difference** rather than the currently published immutable-release artifact. Available evidence does not identify the exact source tree of the `1FE93F...` package, so it must remain preserved as historical acceptance/rollback evidence and must not replace the published final-merge artifact by assumption.

## v1.7 extra asset

The `budly-v1.7` GitHub release contains an extra `budly-sales-agent-1.6.0.zip` with SHA-256 `DBE44171A79A7CD51DB346B707A431A3BD21635123E17C6F2109E19802DC1372`. Its embedded manifest claims application 1.6.0/schema 1.4.0 while naming source commit `79b6752699fe30e42a321008bf62ce5b82c8f858` (the v1.7 merge). It is internally inconsistent and is not the correct v1.7 artifact.

Recommendation: preserve this report and asset hash as evidence, then remove the accidentally attached ZIP and its sidecar under separate release-history authorization. No historical tag or correct `budly-sales-agent-1.7.0.zip` should change.

## Bootstrap provenance

Git source `Bootstrap.php` at `ae9ed566` hashes to `4C78ED4FD4AAA37FDE5FF78641A435DCE260E96C7CB8782C63F4291AE3E56587`; prior production evidence reports `5183DD818A07C49CB56CB82BADFF2FD51FF3625B00036ACBABC344974D35BB19`. Production bytes were not accessed during patch implementation. Exact source, package, and installed-file hashes remain a required separately authorized deployment gate.
