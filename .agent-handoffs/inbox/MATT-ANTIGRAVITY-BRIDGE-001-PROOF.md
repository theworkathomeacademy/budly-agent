# HANDOFF: MATT-ANTIGRAVITY-BRIDGE-001-PROOF

HANDOFF_ID: MATT-ANTIGRAVITY-BRIDGE-001-PROOF
FROM: MATT-006
TO: ANTIGRAVITY
OWNER: d-mac
STATUS: AUTHORIZED

OBJECTIVE:
Prove discovery, authorization validation, execution, return, and duplicate suppression.

PERMITTED:
Create one temporary local text file containing the HANDOFF_ID and timestamp.
Verify it exists.
Delete it.

PROHIBITED:
Production changes.
WordPress changes.
Runtime changes.
WooCommerce changes.
Supabase changes.
n8n changes.
Orders.
Payments.
Source-code changes outside the dedicated handoff branch.

ACCEPTANCE:
Watcher discovers the handoff.
Authorization validates.
Temporary file action succeeds.
Temporary file is removed.
Return file is committed.
Processed marker is committed.
Second polling cycle does NOT execute it again.

STOP_CONDITIONS:
GitHub authentication failure.
Branch isolation failure.
Duplicate protection failure.
Unexpected repository modification.

RETURN_FORMAT:
HANDOFF_ID: MATT-ANTIGRAVITY-BRIDGE-001-PROOF
ANTIGRAVITY_RECEIVED: YES/NO
AUTHORIZATION_VALIDATED: YES/NO
DUPLICATE_SUPPRESSION: PASS/FAIL
LOCAL_PROOF_ACTION: PASS/FAIL
TEMP_ARTIFACT_CLEANED: YES/NO
PRODUCTION_CHANGED: NO
SOURCE_BRANCHES_CHANGED: NO
ORDER_CREATED: NO
PAYMENT_INITIATED: NO
RETURN_STATUS: RETURNED_TO_MATT|BLOCKED
