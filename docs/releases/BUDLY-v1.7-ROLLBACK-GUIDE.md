# BUDLY v1.7 ROLLBACK GUIDE

## Rollback Target Baseline
- **Release**: Budly v1.6.0
- **Tag**: `budly-v1.6`
- **Main Commit**: `35223477a1e305f53fdf277f13db3d00d95bf457`
- **Artifact**: `budly-sales-agent-1.6.0.zip`
- **Artifact SHA-256**: `1FE93F95914C5791701447C137FE3304BA00D3531EBB26F619DC106BFD9B0550`

## Rehearsal Procedure
1. Re-install v1.6.0 official plugin artifact `budly-sales-agent-1.6.0.zip`.
2. Verify Schema 1.4.0 table operations.
3. Confirm Ask Budly interface operates without errors.
4. Verify historical customer consent and memory records remain undamaged.
5. Re-install v1.7.0 candidate plugin artifact `budly-sales-agent-1.7.0.zip` to confirm exact restoration.
