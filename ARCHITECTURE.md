# Architecture

This repository implements the ratified BROS and Budly architecture; it does not define or replace it. Google Drive holds ratified governing documents, while GitHub is the engineering source record for committed code and Markdown mirrors.

The deployable WordPress plugin is under `deploy/wordpress/budly-sales-agent`. The Python reference implementation and tests provide governed behavior and regression evidence. v1.4 adds only release-engineering controls: validation, deterministic packaging, CI, traceability, and rollback evidence. Customer-facing behavior, schema 1.2.0, and the active rule set remain unchanged.
