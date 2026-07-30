# Budly v1.4 Packaging Report

`scripts/build_plugin.py` selects regular files only from the Git plugin tree, sorts POSIX paths, applies one fixed ZIP timestamp and permission mode, uses fixed compression settings, and writes an embedded, sorted JSON manifest. Secrets, databases, logs, bytecode, nested ZIPs, and local configuration are excluded.

Two builds from staging-tested source `e9bf0d2b4ee75750fa0696169c16947ab43431d2` produced byte-identical archives:

`F9066E525047522EC172A696AB7243F2E17E451B8C23782C1FBBA4FBC2536DD9`

The archive has one `budly-sales-agent/` root and 44 files including `release-manifest.json`. The checksum sidecar matched a fresh SHA-256 calculation. Generated packages are ignored rather than committed; GitHub retains validated CI artifacts and the release workflow attaches the accepted build to a human-published release.

The staging installation matched the archive file-for-file: 44 expected, 44 installed, zero missing, changed, or extra paths. Repository and controlled negative-fixture tests confirmed exclusion of secrets, databases, development files, and nested archives.
