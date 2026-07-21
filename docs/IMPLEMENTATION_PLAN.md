# Implementation plan

## Phase 1 - runnable recruiting slice (included here)

Intake, email validation, deduplication, qualification, route selection, local
education-first responses, optional OpenAI response drafting, SQLite persistence,
audit events, and risk-topic escalation.

Exit gate: all automated tests pass; brand supplies the missing policy inputs;
compliance owner approves the system prompt and escalation triggers.

## Phase 2 - Botpress and Airtable

Build these Botpress flows first:

1. `FLOW_InitializeSession`
2. `FLOW_ContextLoader`
3. `FLOW_RecruitProspect`
4. `FLOW_ProspectQualification`
5. `FLOW_InvitationWorkflow`
6. `FLOW_ApplicationIntake`
7. `FLOW_HumanEscalation`
8. `FLOW_ConversationLogger`
9. `FLOW_ErrorHandler`

Create initial Airtable tables: Prospects, Applications, Affiliates, Conversations,
Qualification Assessments, Escalations, Workflow Runs, Audit Events, Knowledge
Articles, Campaigns, Products, and System Settings. Use stable external IDs and
upsert on normalized email/external event ID.

Exit gate: successful-path, validation, missing-data, duplicate-event, permission,
API-failure, logging, notification, and recovery tests pass for every flow.

## Phase 3 - enrollment and activation

Connect GoAffPro behind isolated API actions. Add application review, account and
tracking-link creation, welcome workflow, training checklist, readiness assessment,
campaign assignment, first-sale webhook, and activation celebration. Add Gmail;
add Twilio only after explicit SMS consent and opt-out handling are approved.

Exit gate: a sandbox prospect can travel from first chat to a test attributed sale
without duplicate accounts, messages, or activation events.

## Phase 4 - performance and scale

Add coaching, recognition, leadership, analytics, dashboards, alerting, data
retention automation, load testing, backup/restore drills, and quarterly prompt,
knowledge, security, and compliance reviews.

## Production controls

- Separate development, staging, and production credentials and data.
- Validate webhook signatures and timestamps; reject replayed events.
- Use an idempotency key for every write-producing integration call.
- Apply blueprint retry guidance: network 3, timeout 2, webhook 5, database lock 3,
  authentication 0 with immediate alert.
- Keep message templates and knowledge outside flow logic.
- Require explicit human approval for risk-sensitive or irreversible actions.

