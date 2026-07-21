# Sales-agent requirements

## Phase 1 functional requirements

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-01 | Capture prospect identity and source | Name, validated email, source, platform, and niche persist under a unique ID |
| FR-02 | Prevent duplicate prospects | Reusing a normalized email updates the existing record |
| FR-03 | Qualify consistently | Six structured factors produce a deterministic 0-100 score |
| FR-04 | Route by score | 0-39 monitor, 40-69 nurture, 70-100 invite to apply |
| FR-05 | Educate before conversion | Agent explains mission and fit before presenting an application next step |
| FR-06 | Handle common objections | Responses remain transparent, non-pressuring, and do not make income claims |
| FR-07 | Escalate high-risk requests | Legal, medical, compliance, payout, adverse-event, and partnership topics create escalation status |
| FR-08 | Preserve auditability | Intake, scoring, status changes, messages, and escalations are timestamped |
| FR-09 | Keep structured rules authoritative | Model output cannot overwrite score, status, or escalation decisions |
| FR-10 | Operate without model access | Core workflow remains usable when API credentials or network are unavailable |

## Phase 2-4 requirements

- Application intake, duplicate review, approval/rejection, and manual review
- Airtable synchronization and normalized relational tables
- GoAffPro account creation, link generation, attribution, and commission reads
- Welcome sequence, training assignments, checklist, certification, readiness check
- First-campaign assignment and first-confirmed-sale activation event
- Gmail and consent-aware Twilio lifecycle communication
- Performance coaching, badges, milestones, leaderboards, mentor/leadership pipeline
- KPI dashboards for source conversion, activation, retention, revenue, drop-off,
  execution time, retry frequency, and failure rate

## Non-functional requirements

- Idempotent webhook and API processing
- Least-privilege credentials stored outside prompts and source control
- Retry rules with dead-letter/manual-review handling
- Structured logs with correlation IDs
- PII minimization, access control, retention rules, and deletion/export procedures
- Small, independently testable workflows rather than monolithic prompts
- Graceful failure and complete context on human handoff
- Vendor-portable knowledge, records, prompts, and templates

## Human-only decisions

- Legal, medical, tax, and regulatory interpretations
- Commission or payment disputes
- Strategic or negotiated partnerships
- Adverse-event and sensitive safety reports
- Exceptions to eligibility, brand, or compliance policy
- Final approval where company policy requires human authorization

## Inputs still needed from the brand

- Final affiliate eligibility rules and application URL
- Approved product catalog and substantiated product claims
- Commission tiers, cookie duration, payout rules, and GoAffPro configuration
- Approved compliance language by jurisdiction and legal review owner
- Privacy notice, consent language, data retention/deletion policy
- Escalation contacts and service-level targets
- Brand voice examples, objection library, FAQs, and approved marketing assets

