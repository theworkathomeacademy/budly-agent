# Budly v1.3.4-R1 build and packaging guide

From a clean checkout of the tagged source:

```powershell
python scripts/build_wordpress_plugin.py --output dist/budly-sales-agent-1.3.4-R1.zip --source-commit <tag-target>
Get-FileHash dist/budly-sales-agent-1.3.4-R1.zip -Algorithm SHA256
```

Run the command twice with different output names. The SHA-256 values must match. The builder fixes timestamps, ordering, permissions, compression, root name, and manifest serialization. It excludes ZIPs, logs, bytecode, operating-system metadata, and cache directories. Credentials and local configuration are outside the plugin source tree and are never selected.
