# Budly v1.4 Packaging Report

`scripts/build_plugin.py` selects regular files only from the Git plugin tree, sorts POSIX paths, applies one fixed ZIP timestamp and permission mode, uses fixed compression settings, and writes an embedded, sorted JSON manifest. Secrets, databases, logs, bytecode, nested ZIPs, and local configuration are excluded.

Two builds from candidate source `584b74403098b7b461b63fb5e1835d192efecf82` produced byte-identical archives:

`B71929A2D7203181E600E6D15A18D4318728CF525E33A420315A4AD353AF76EF`

The archive has one `budly-sales-agent/` root and 44 files including `release-manifest.json`. The checksum sidecar matched a fresh SHA-256 calculation. Generated packages are ignored rather than committed; GitHub retains validated CI artifacts and the release workflow attaches the accepted build to a human-published release.
