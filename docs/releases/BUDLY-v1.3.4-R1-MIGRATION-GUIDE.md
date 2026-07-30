# Budly v1.3.4-R1 migration guide

R1 introduces no schema or rules migration. Existing application `1.3.4`, schema `1.2.0`, and rules `bros-rules-1.3.4.1` remain authoritative.

Before staging installation, back up the database and current plugin directory and record hashes. Install the Git-built R1 ZIP, activate it, verify schema `1.2.0`, verify the dedicated Ask Budly page and assets, then run Gates A–E. Page repair is bounded to the recorded Ask Budly page and runs once per application version.

Production migration is not authorized.
