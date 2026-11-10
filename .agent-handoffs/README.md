# MATT ↔ Antigravity Agent Handoff Mailbox

This branch (`agent-handoffs`) hosts the asynchronous handoff bridge between MATT-006 and Antigravity. It operates in isolation from production and release branches.

## Directory Structure

```text
.agent-handoffs/
├── README.md        # Mailbox contract and protocol definition
├── inbox/           # Inbound handoffs from MATT-006 (<HANDOFF_ID>.md)
├── outbox/          # Completed return reports from Antigravity (<HANDOFF_ID>-RETURN.md)
└── processed/       # Processed state markers (<HANDOFF_ID>.json)
```

## Mailbox Contract

A handoff is executable ONLY when the handoff file contains all of:

- `HANDOFF_ID:`
- `FROM:`
- `TO: ANTIGRAVITY`
- `OWNER: d-mac`
- `STATUS: AUTHORIZED`
- `OBJECTIVE:`
- `PERMITTED:`
- `PROHIBITED:`
- `ACCEPTANCE:`
- `STOP_CONDITIONS:`
- `RETURN_FORMAT:`

**A question is not authorization.**

### STATUS Values

- `DRAFT`
- `OWNER_REVIEW`
- `AUTHORIZED`
- `IN_PROGRESS`
- `RETURNED_TO_MATT`
- `BLOCKED`
- `CLOSED`

**Only `STATUS: AUTHORIZED` + `TO: ANTIGRAVITY` may begin execution.**

## File Conventions

1. **MATT Inbound Handoffs**:
   - Path: `.agent-handoffs/inbox/<HANDOFF_ID>.md`
   - Never modified after receipt.
2. **Antigravity Return Reports**:
   - Path: `.agent-handoffs/outbox/<HANDOFF_ID>-RETURN.md`
3. **Processed Marker**:
   - Path: `.agent-handoffs/processed/<HANDOFF_ID>.json`
   - JSON structure (minimum required):
     ```json
     {
       "handoff_id": "...",
       "processed": true,
       "received_commit": "...",
       "return_commit": "...",
       "completed_at": "...",
       "result": "RETURNED_TO_MATT|BLOCKED"
     }
     ```

## Rules of Engagement

- **Never execute a HANDOFF_ID already present in `processed/`.**
- **Never modify the original handoff file after receipt.**
- **Commit and push ONLY changes on the `agent-handoffs` branch.**
- **Do not merge into `main` or modify release/production branches.**
