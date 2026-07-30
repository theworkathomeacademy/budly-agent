# Budly v1.3.4-R1 rollback guide

Preserve both immutable historical artifacts:

- Git release `4b46174c950b24080441cbc25388e17207a0b772`, tag `budly-v1.3.4`.
- Drive package SHA-256 `DDDEF84BB56DEB133D83C706C4206CD22E2C2531AEB3A5FC20D867B7AAD32C91`.

For staging rollback, deactivate R1, restore the pre-install plugin directory and database backup as one recovery point, reactivate, verify application `1.3.4` and schema `1.2.0`, and rerun the inherited regression and staging smoke suite. Do not install the eight-file Drive package over the accepted Git database without an explicit lineage decision. No destructive down-migration is required because R1 adds no tables or columns.

Production rollback is outside this authorization.
