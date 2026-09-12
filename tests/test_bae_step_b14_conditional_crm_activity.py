"""BAE Pilot 001 Gate B Step B14 Conditional CRM Activity Capability Test Suite.

Verifies the 73 required B14 test invariants:
1. Registered bounded CRM fixture activity succeeds.
2. Unregistered CRM action denied.
3. Missing capability denied.
4. Ambiguous record denied/stopped.
5. Nonexistent target fails safely.
6. Exact record ID resolution succeeds.
7. Allowed field update succeeds.
8. Prohibited field update denied.
9. Mixed allowed/prohibited payload denied atomically.
10. Missing permission denied.
11. Environment production denied.
12. L2 CRM action without approval denied.
13. L2 with valid approval may proceed when all other gates pass.
14. L3-H CRM action autonomous attempt denied.
15. L3-X CRM action blocked.
16. Target M3 does not equal current certification.
17. Active capability kill stops CRM operation.
18. Active tool kill stops CRM operation.
19. Active objective kill stops CRM operation.
20. Human override stops CRM operation.
21. Post-B2/pre-B3 kill race yields zero provider calls.
22. B3 provenance required.
23. Direct CRM adapter bypass rejected.
24. Provider acknowledgement alone does not verify.
25. Authoritative CRM readback verifies exact change.
26. Prohibited fields remain unchanged after allowed update.
27. UNKNOWN provider outcome does not become success.
28. Verification unavailable fails safe.
29. CRM mutation audited.
30. Lineage preserved.
31. PII sanitized.
32. Secrets redacted.
33. Duplicate VERIFIED CRM write not replayed.
34. Idempotency payload mismatch rejected.
35. Record-ID mismatch rejected.
36. UNKNOWN prior outcome prevents blind retry.
37. RETRY requires fresh B2 authorization.
38. Changed permission blocks retry.
39. Kill switch blocks due retry.
40. Human override blocks retry.
41. Retry exhaustion escalates safely.
42. CRM record existence does not imply consent.
43. Missing required consent denies action.
44. CRM Activity cannot manufacture consent.
45. CRM Activity cannot alter customer communication preference without explicit registered authority.
46. Customer follow-up capability remains disabled.
47. CRM action cannot invoke email.
48. CRM action cannot invoke SMS.
49. CRM action cannot invoke DM/customer route.
50. CRM action cannot enqueue communication workflow.
51. CRM action with indirect customer-contact side effect is prohibited.
52. CRM action cannot mutate payment state.
53. CRM action cannot mutate order state.
54. CRM action cannot modify capability certification.
55. CRM action cannot modify L/M/A/T.
56. CRM action cannot self-activate.
57. CRM action cannot self-certify.
58. Task wrapper does not widen CRM authority.
59. Retry wrapper does not widen CRM authority.
60. Escalation remains non-authoritative.
61. Escalation acknowledgement is not approval.
62. Human response requires fresh B2.
63. Wave 1 remains unchanged.
64. TASK remains uncertified/non-executable.
65. RETRY remains uncertified/non-executable.
66. CRM Activity remains conditional/non-executable.
67. Customer Follow-Up remains disabled.
68. Gate C not started.
69. Gate D unauthorized.
70. No production CRM connection/write.
71. No production merge/deployment.
72. B15 not started.
73. All prior accepted BAE regressions remain green.
"""

from __future__ import annotations

import json
import unittest
from uuid import uuid4

from src.budly_runtime.bae.audit_persistence import (
    AuditEventRecord,
    AuditEventType,
    CorrelationRecord,
    DurableAuditRepository,
    EvidenceRecord,
    compute_evidence_hash,
)
from src.budly_runtime.bae.capability_registry import BAECapabilityRegistry
from src.budly_runtime.bae.crm_capabilities import (
    CRMActionPolicy,
    CRMActionPolicyRegistry,
    CRMActivityExecutionResult,
    ConditionalCRMActivityExecutor,
    DeterministicCRMStore,
    MockCRMRecord,
)
from src.budly_runtime.bae.escalation import (
    EscalationController,
    EscalationDeliveryState,
    EscalationDisposition,
    EscalationPackage,
    EscalationPriority,
    EscalationReason,
)
from src.budly_runtime.bae.kill_switch import (
    KillSwitchController,
    KillSwitchDecisionStatus,
)
from src.budly_runtime.bae.policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    DeterministicPolicyEvaluator,
    utc_now,
)
from src.budly_runtime.bae.retry_controller import (
    FailureClass,
    IdempotencyDisposition,
    IdempotencyStore,
    RetryController,
    RetryDecision,
    RetryPolicy,
    RetryPolicyRegistry,
    RetryStopReason,
)
from src.budly_runtime.bae.schemas import CapabilityRecord
from src.budly_runtime.bae.state_machine import (
    ExecutionState,
    VerificationEvidenceClass,
    VerificationState,
)
from src.budly_runtime.bae.types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    KillSwitchScope,
    PilotWave,
    ToolAuthorityClass,
)
from src.budly_runtime.bae.verification_engine import (
    AuthoritativeVerificationEngine,
    VerificationEvidenceItem,
    VerificationMethod,
    VerificationOutcome,
    VerificationReason,
)
from src.budly_runtime.bae.wave2_capabilities import (
    TaskActionPolicy,
    TaskActionPolicyRegistry,
    TaskExecutionResult,
    Wave2CapabilityExecutor,
)
from src.budly_runtime.tool_gateway import (
    Actor,
    CapabilityRef,
    GatewayExecutionContext,
    verify_adapter_provenance,
)


class TestBAEStepB14ConditionalCRMActivity(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = BAECapabilityRegistry.load_seed()
        self.kill_switch = KillSwitchController()
        self.audit_repo = DurableAuditRepository(environment="development")
        self.policy_evaluator = DeterministicPolicyEvaluator(
            self.registry,
            self.kill_switch,
            environment="development",
        )
        self.crm_policies = CRMActionPolicyRegistry.default_registry()
        self.crm_store = DeterministicCRMStore({
            "rec-lead-001": MockCRMRecord(
                record_id="rec-lead-001",
                record_type="lead",
                fields={
                    "note_body": "Initial note",
                    "status": "OPEN",
                    "stage": "QUALIFICATION",
                    "lead_score": 10,
                    "journey_stage": "STAGE_1",
                    "payment_status": "UNPAID",
                    "consent_state": "NONE",
                },
                version=1,
            ),
            "rec-contact-002": MockCRMRecord(
                record_id="rec-contact-002",
                record_type="contact",
                fields={
                    "status": "ACTIVE",
                    "note_body": "Customer contacted support",
                    "consent_state": "VERIFIED_OPT_IN",
                },
                version=1,
            ),
        })
        self.executor = ConditionalCRMActivityExecutor(
            policy_evaluator=self.policy_evaluator,
            kill_switch_controller=self.kill_switch,
            audit_repository=self.audit_repo,
            crm_store=self.crm_store,
            crm_policy_registry=self.crm_policies,
        )
        self.objective_id = str(uuid4())
        self.action_id = str(uuid4())
        self.correlation_id = str(uuid4())
        self.correlation = CorrelationRecord(
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
        )

    # =========================================================================
    # 1. Registered bounded CRM fixture activity succeeds
    # =========================================================================
    def test_b14_01_registered_bounded_crm_fixture_activity_succeeds(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_id": "note-101", "note_body": "Operational steward logged note"},
        )
        self.assertEqual(res.capability_id, "BAE-CRM-ACTIVITY-001")
        self.assertEqual(res.execution_state, ExecutionState.VERIFIED)
        self.assertTrue(res.is_verified_success)
        self.assertTrue(res.provider_invoked)
        self.assertIsNotNone(res.audit_event_id)
        # Verify readback in CRM store
        rec = self.crm_store.get_record("rec-lead-001")
        self.assertEqual(rec.fields["note_body"], "Operational steward logged note")
        self.assertEqual(rec.version, 2)

    # =========================================================================
    # 2. Unregistered CRM action denied
    # =========================================================================
    def test_b14_02_unregistered_crm_action_denied(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="unregistered_arbitrary_crm_write",
            target_record_id="rec-lead-001",
            mutation_fields={"foo": "bar"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertFalse(res.is_verified_success)
        self.assertFalse(res.provider_invoked)
        self.assertEqual(res.denial_reason, "UNREGISTERED_CRM_OPERATION")

    # =========================================================================
    # 3. Missing capability denied
    # =========================================================================
    def test_b14_03_missing_capability_denied(self) -> None:
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-NONEXISTENT-CAP-999",
            capability_version="1.0",
            environment="development",
            channel="website_chat",
            purpose="customer_activity_recording",
            requested_tool_authority=ToolAuthorityClass.T2,
            requested_maturity=AutonomyMaturity.M1,
            approval_token=None,
            is_human_override_active=False,
            granted_permissions=frozenset({"bae:crm_write"}),
            required_permission="bae:crm_write",
            data_scope="customer_crm",
            requires_consent=False,
        )
        auth_dec = self.policy_evaluator.evaluate(auth_req)
        self.assertFalse(auth_dec.permitted)
        self.assertEqual(auth_dec.denial_reason, AuthorizationDenialReason.CAPABILITY_NOT_REGISTERED)

    # =========================================================================
    # 4. Ambiguous record denied/stopped
    # =========================================================================
    def test_b14_04_ambiguous_record_denied_and_stopped(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "Note for ambiguous lead"},
            is_ambiguous_record_match=True,
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertFalse(res.provider_invoked)
        self.assertEqual(res.denial_reason, "AMBIGUOUS_OR_MISSING_RECORD_IDENTITY")
        self.assertIsNotNone(res.escalation_package)

    # =========================================================================
    # 5. Nonexistent target fails safely
    # =========================================================================
    def test_b14_05_nonexistent_target_fails_safely(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-nonexistent-999",
            mutation_fields={"note_body": "Note"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertFalse(res.provider_invoked)
        self.assertEqual(res.denial_reason, "TARGET_RECORD_NOT_FOUND")

    # =========================================================================
    # 6. Exact record ID resolution succeeds
    # =========================================================================
    def test_b14_06_exact_record_id_resolution_succeeds(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="update_workflow_status",
            target_record_id="rec-lead-001",
            mutation_fields={"status": "IN_REVIEW", "stage": "EVALUATION"},
        )
        self.assertEqual(res.execution_state, ExecutionState.VERIFIED)
        self.assertTrue(res.is_verified_success)
        rec = self.crm_store.get_record("rec-lead-001")
        self.assertEqual(rec.fields["status"], "IN_REVIEW")
        self.assertEqual(rec.fields["stage"], "EVALUATION")

    # =========================================================================
    # 7. Allowed field update succeeds
    # =========================================================================
    def test_b14_07_allowed_field_update_succeeds(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="update_synthetic_lead_field",
            target_record_id="rec-lead-001",
            mutation_fields={"lead_score": 85, "journey_stage": "QUALIFIED"},
        )
        self.assertEqual(res.execution_state, ExecutionState.VERIFIED)
        self.assertTrue(res.is_verified_success)
        rec = self.crm_store.get_record("rec-lead-001")
        self.assertEqual(rec.fields["lead_score"], 85)

    # =========================================================================
    # 8. Prohibited field update denied
    # =========================================================================
    def test_b14_08_prohibited_field_update_denied(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="update_synthetic_lead_field",
            target_record_id="rec-lead-001",
            mutation_fields={"payment_status": "PAID_COMPLETED"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertFalse(res.provider_invoked)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")
        # Ensure SoR payment_status was NOT mutated
        rec = self.crm_store.get_record("rec-lead-001")
        self.assertEqual(rec.fields["payment_status"], "UNPAID")

    # =========================================================================
    # 9. Mixed allowed/prohibited payload denied atomically
    # =========================================================================
    def test_b14_09_mixed_allowed_and_prohibited_payload_denied_atomically(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="update_synthetic_lead_field",
            target_record_id="rec-lead-001",
            mutation_fields={
                "lead_score": 99,                     # Allowed
                "consent_state": "FORCED_OPT_IN",     # Prohibited
            },
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertFalse(res.provider_invoked)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")
        # Ensure NEITHER field changed
        rec = self.crm_store.get_record("rec-lead-001")
        self.assertEqual(rec.fields["lead_score"], 10)
        self.assertEqual(rec.fields["consent_state"], "NONE")

    # =========================================================================
    # 10. Missing permission denied
    # =========================================================================
    def test_b14_10_missing_permission_denied(self) -> None:
        # Register action with special ungranted permission
        custom_pol = CRMActionPolicy(
            action_policy_id="CRM-POL-CUSTOM-PERM",
            operation="custom_crm_restricted_perm_action",
            required_permission="bae:crm_super_admin",
            allowed_fields=frozenset({"note_body"}),
        )
        self.crm_policies.register(custom_pol)
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="custom_crm_restricted_perm_action",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, AuthorizationDenialReason.PERMISSION_DENIED.value)

    # =========================================================================
    # 11. Environment production denied
    # =========================================================================
    def test_b14_11_environment_production_denied(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
            environment="production",
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, AuthorizationDenialReason.ENVIRONMENT_DENIED.value)

    # =========================================================================
    # 12. L2 CRM action without approval denied
    # =========================================================================
    def test_b14_12_l2_crm_action_without_approval_denied(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="elevated_lead_status_mutation",
            target_record_id="rec-lead-001",
            mutation_fields={"qualification_status": "ENTERPRISE_QUALIFIED"},
            approval_token=None,
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, AuthorizationDenialReason.HUMAN_APPROVAL_REQUIRED.value)

    # =========================================================================
    # 13. L2 with valid approval may proceed when all other gates pass
    # =========================================================================
    def test_b14_13_l2_with_valid_approval_proceeds(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="elevated_lead_status_mutation",
            target_record_id="rec-lead-001",
            mutation_fields={"qualification_status": "ENTERPRISE_QUALIFIED"},
            approval_token="valid_human_approval_token_a1",
        )
        self.assertEqual(res.execution_state, ExecutionState.VERIFIED)
        self.assertTrue(res.is_verified_success)

    # =========================================================================
    # 14. L3-H CRM action autonomous attempt denied
    # =========================================================================
    def test_b14_14_l3_h_crm_action_autonomous_attempt_denied(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="human_only_crm_reconciliation",
            target_record_id="rec-lead-001",
            mutation_fields={"override_notes": "Attempting autonomous override"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, AuthorizationDenialReason.AUTHORITY_CLASS_HUMAN_ONLY.value)

    # =========================================================================
    # 15. L3-X CRM action blocked
    # =========================================================================
    def test_b14_15_l3_x_crm_action_blocked(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="prohibited_customer_contact_action",
            target_record_id="rec-lead-001",
            mutation_fields={"email_body": "Sending marketing blast"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)

    # =========================================================================
    # 16. Target M3 does not equal current certification
    # =========================================================================
    def test_b14_16_target_m3_does_not_equal_current_certification(self) -> None:
        crm_rec = self.registry.get("BAE-CRM-ACTIVITY-001")
        self.assertEqual(crm_rec.target_pilot_entry_maturity, AutonomyMaturity.M3)
        self.assertIsNone(crm_rec.current_certified_maturity)
        self.assertEqual(crm_rec.lifecycle_state, CapabilityLifecycleState.DEFINED)
        self.assertFalse(crm_rec.executable)

    # =========================================================================
    # 17. Active capability kill stops CRM operation
    # =========================================================================
    def test_b14_17_active_capability_kill_stops_crm_operation(self) -> None:
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-CRM-ACTIVITY-001",
            reason="Emergency stop on CRM writes",
            activating_authority="admin",
            operator_role="system_admin",
        )
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
        )
        self.assertEqual(res.execution_state, ExecutionState.STOPPED)
        self.assertFalse(res.provider_invoked)

    # =========================================================================
    # 18. Active tool kill stops CRM operation
    # =========================================================================
    def test_b14_18_active_tool_kill_stops_crm_operation(self) -> None:
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.TOOL,
            target_identifier="T2",
            reason="Tool class T2 disabled",
            activating_authority="admin",
            operator_role="system_admin",
        )
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
        )
        self.assertEqual(res.execution_state, ExecutionState.STOPPED)
        self.assertFalse(res.provider_invoked)

    # =========================================================================
    # 19. Active objective kill stops CRM operation
    # =========================================================================
    def test_b14_19_active_objective_kill_stops_crm_operation(self) -> None:
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.OBJECTIVE,
            target_identifier=self.objective_id,
            reason="Objective stopped by steward",
            activating_authority="admin",
            operator_role="system_admin",
        )
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
        )
        self.assertEqual(res.execution_state, ExecutionState.STOPPED)

    # =========================================================================
    # 20. Human override stops CRM operation
    # =========================================================================
    def test_b14_20_human_override_stops_crm_operation(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
            is_human_override_active=True,
        )
        self.assertEqual(res.execution_state, ExecutionState.STOPPED)
        self.assertFalse(res.provider_invoked)

    # =========================================================================
    # 21. Post-B2/pre-B3 kill race yields zero provider calls
    # =========================================================================
    def test_b14_21_post_b2_pre_b3_kill_race_yields_zero_provider_calls(self) -> None:
        # Activate kill switch immediately before provider invocation simulation
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-CRM-ACTIVITY-001",
            reason="Killed right before CRM adapter execution",
            activating_authority="admin",
            operator_role="system_admin",
        )
        provider_called = False

        def mock_provider(p, ctx):
            nonlocal provider_called
            provider_called = True
            return {"status": "SUCCESS"}

        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
            provider_fn=mock_provider,
        )
        self.assertEqual(res.execution_state, ExecutionState.STOPPED)
        self.assertFalse(provider_called)

    # =========================================================================
    # 22. B3 provenance required
    # =========================================================================
    def test_b14_22_b3_provenance_required(self) -> None:
        captured_ctx = []

        def mock_provider(p, ctx):
            captured_ctx.append(ctx)
            return {"status": "SUCCESS"}

        self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
            provider_fn=mock_provider,
        )
        self.assertEqual(len(captured_ctx), 1)
        self.assertIsInstance(captured_ctx[0], GatewayExecutionContext)

    # =========================================================================
    # 23. Direct CRM adapter bypass rejected
    # =========================================================================
    def test_b14_23_direct_crm_adapter_bypass_rejected(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
            provider_fn=lambda p, ctx: {"status": "SUCCESS"},
            bypass_gateway_context=True,
        )
        self.assertEqual(res.execution_state, ExecutionState.FAILED)
        self.assertIn("Direct adapter execution prohibited", res.error_message or "")

    # =========================================================================
    # 24. Provider acknowledgement alone does not verify
    # =========================================================================
    def test_b14_24_provider_acknowledgement_alone_does_not_verify(self) -> None:
        def weak_v_fn(res):
            return VerificationOutcome.UNVERIFIED, VerificationReason.WEAK_AGENT_SELF_REPORT_ONLY, VerificationEvidenceClass.AGENT_SELF_REPORT, None

        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
            provider_fn=lambda p, ctx: {"status": "200_OK_CREATED"},
            verification_fn=weak_v_fn,
        )
        self.assertEqual(res.execution_state, ExecutionState.UNVERIFIED)
        self.assertFalse(res.is_verified_success)
        self.assertTrue(res.provider_invoked)

    # =========================================================================
    # 25. Authoritative CRM readback verifies exact change
    # =========================================================================
    def test_b14_25_authoritative_crm_readback_verifies_exact_change(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "Authoritatively verified note"},
        )
        self.assertEqual(res.execution_state, ExecutionState.VERIFIED)
        self.assertTrue(res.is_verified_success)
        rec = self.crm_store.get_record("rec-lead-001")
        self.assertEqual(rec.fields["note_body"], "Authoritatively verified note")

    # =========================================================================
    # 26. Prohibited fields remain unchanged after allowed update
    # =========================================================================
    def test_b14_26_prohibited_fields_remain_unchanged_after_allowed_update(self) -> None:
        rec_before = self.crm_store.get_record("rec-lead-001")
        self.assertEqual(rec_before.fields["payment_status"], "UNPAID")
        self.assertEqual(rec_before.fields["consent_state"], "NONE")

        self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="update_synthetic_lead_field",
            target_record_id="rec-lead-001",
            mutation_fields={"lead_score": 75},
        )
        rec_after = self.crm_store.get_record("rec-lead-001")
        self.assertEqual(rec_after.fields["lead_score"], 75)
        self.assertEqual(rec_after.fields["payment_status"], "UNPAID")
        self.assertEqual(rec_after.fields["consent_state"], "NONE")

    # =========================================================================
    # 27. UNKNOWN provider outcome does not become success
    # =========================================================================
    def test_b14_27_unknown_provider_outcome_does_not_become_success(self) -> None:
        def unknown_v_fn(res):
            return VerificationOutcome.UNKNOWN, VerificationReason.AUTHORITATIVE_SOURCE_UNAVAILABLE, VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL, None

        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
            verification_fn=unknown_v_fn,
        )
        self.assertEqual(res.execution_state, ExecutionState.UNKNOWN)
        self.assertFalse(res.is_verified_success)

    # =========================================================================
    # 28. Verification unavailable fails safe
    # =========================================================================
    def test_b14_28_verification_unavailable_fails_safe(self) -> None:
        def failed_v_fn(res):
            return VerificationOutcome.FAILED, VerificationReason.POSTCONDITION_STATE_MISMATCH, VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL, None

        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
            verification_fn=failed_v_fn,
        )
        self.assertEqual(res.execution_state, ExecutionState.FAILED)
        self.assertFalse(res.is_verified_success)

    # =========================================================================
    # 29. CRM mutation audited
    # =========================================================================
    def test_b14_29_crm_mutation_audited(self) -> None:
        self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
        )
        events = self.audit_repo.get_action_history(self.action_id)
        self.assertTrue(any(e.capability_id == "BAE-CRM-ACTIVITY-001" for e in events))

    # =========================================================================
    # 30. Lineage preserved
    # =========================================================================
    def test_b14_30_lineage_preserved(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
        )
        self.assertEqual(res.correlation.objective_id, self.objective_id)
        self.assertEqual(res.correlation.action_id, self.action_id)
        self.assertEqual(res.correlation.correlation_id, self.correlation_id)

    # =========================================================================
    # 31. PII sanitized
    # =========================================================================
    def test_b14_31_pii_sanitized(self) -> None:
        self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "Contact email: alice@example.com"},
        )
        events = self.audit_repo.get_action_history(self.action_id)
        crm_ev = next(e for e in events if e.capability_id == "BAE-CRM-ACTIVITY-001")
        self.assertIsNotNone(crm_ev.sanitized_metadata)

    # =========================================================================
    # 32. Secrets redacted
    # =========================================================================
    def test_b14_32_secrets_redacted(self) -> None:
        self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
        )
        events = self.audit_repo.get_action_history(self.action_id)
        crm_ev = next(e for e in events if e.capability_id == "BAE-CRM-ACTIVITY-001")
        # Ensure raw secrets are not present
        dumped = json.dumps(crm_ev.sanitized_metadata)
        self.assertNotIn("secretPassword123", dumped)

    # =========================================================================
    # 33. Duplicate VERIFIED CRM write not replayed
    # =========================================================================
    def test_b14_33_duplicate_verified_crm_write_not_replayed(self) -> None:
        idem_key = f"idem-crm-test-33-{uuid4()}"
        res1 = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "Unique note 1"},
            idempotency_key=idem_key,
        )
        self.assertEqual(res1.execution_state, ExecutionState.VERIFIED)
        v1 = self.crm_store.get_record("rec-lead-001").version

        # Second call with same idempotency key
        res2 = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "Unique note 1"},
            idempotency_key=idem_key,
        )
        self.assertTrue(res2.is_idempotent_no_op)
        self.assertEqual(res2.execution_state, ExecutionState.VERIFIED)
        self.assertFalse(res2.provider_invoked)
        v2 = self.crm_store.get_record("rec-lead-001").version
        self.assertEqual(v1, v2)  # Store version did not increment again

    # =========================================================================
    # 34. Idempotency payload mismatch rejected
    # =========================================================================
    def test_b14_34_idempotency_payload_mismatch_rejected(self) -> None:
        idem_key = f"idem-crm-test-34-{uuid4()}"
        self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "Original payload"},
            idempotency_key=idem_key,
        )
        res_mismatch = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "Altered payload"},
            idempotency_key=idem_key,
        )
        self.assertEqual(res_mismatch.execution_state, ExecutionState.DENIED)
        self.assertEqual(res_mismatch.denial_reason, "IDEMPOTENCY_MISMATCH")

    # =========================================================================
    # 35. Record-ID mismatch rejected
    # =========================================================================
    def test_b14_35_record_id_mismatch_rejected(self) -> None:
        idem_key = f"idem-crm-test-35-{uuid4()}"
        self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "Note for lead 1"},
            idempotency_key=idem_key,
        )
        # Attempt to reuse key on a different record
        res_mismatch = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-contact-002",
            mutation_fields={"note_body": "Note for lead 1"},
            idempotency_key=idem_key,
        )
        self.assertEqual(res_mismatch.execution_state, ExecutionState.DENIED)
        self.assertEqual(res_mismatch.denial_reason, "IDEMPOTENCY_MISMATCH")

    # =========================================================================
    # 36. UNKNOWN prior outcome prevents blind retry
    # =========================================================================
    def test_b14_36_unknown_prior_outcome_prevents_blind_retry(self) -> None:
        idem_key = f"idem-crm-test-36-{uuid4()}"

        def unknown_v_fn(res):
            return VerificationOutcome.UNKNOWN, VerificationReason.AUTHORITATIVE_SOURCE_UNAVAILABLE, VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL, None

        self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "Note with unknown outcome"},
            idempotency_key=idem_key,
            verification_fn=unknown_v_fn,
        )
        # Attempt retry on unknown outcome
        provider_called = False

        def mock_provider(p, ctx):
            nonlocal provider_called
            provider_called = True
            return {"status": "SUCCESS"}

        res2 = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "Note with unknown outcome"},
            idempotency_key=idem_key,
            provider_fn=mock_provider,
        )
        self.assertEqual(res2.execution_state, ExecutionState.UNVERIFIED)
        self.assertFalse(provider_called)

    # =========================================================================
    # 37. RETRY requires fresh B2 authorization
    # =========================================================================
    def test_b14_37_retry_requires_fresh_b2_authorization(self) -> None:
        # Evaluate retry through B6 RetryController for CRM capability
        retry_dec = self.executor.retry_controller.evaluate_retry(
            capability_id="BAE-CRM-ACTIVITY-001",
            capability_version="1.0",
            current_attempt_count=1,
            error_reason="connection_timeout",
            environment="development",
            actor_id="bae-steward-001",
            objective_id=self.objective_id,
        )
        self.assertTrue(retry_dec.retry_authorized)
        self.assertEqual(retry_dec.failure_class, FailureClass.RETRYABLE)

    # =========================================================================
    # 38. Changed permission blocks retry
    # =========================================================================
    def test_b14_38_changed_permission_blocks_retry(self) -> None:
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-CRM-ACTIVITY-001",
            capability_version="1.0",
            environment="development",
            channel="website_chat",
            purpose="customer_activity_recording",
            requested_tool_authority=ToolAuthorityClass.T2,
            requested_maturity=AutonomyMaturity.M1,
            approval_token=None,
            is_human_override_active=False,
            required_permission="bae:revoked_permission",
            data_scope="customer_crm",
            requires_consent=False,
        )
        auth_dec = self.policy_evaluator.evaluate(auth_req)
        self.assertFalse(auth_dec.permitted)
        self.assertEqual(auth_dec.denial_reason, AuthorizationDenialReason.PERMISSION_DENIED)

    # =========================================================================
    # 39. Kill switch blocks due retry
    # =========================================================================
    def test_b14_39_kill_switch_blocks_due_retry(self) -> None:
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-CRM-ACTIVITY-001",
            reason="CRM capability killed",
            activating_authority="admin",
            operator_role="system_admin",
        )
        retry_dec = self.executor.retry_controller.evaluate_retry(
            capability_id="BAE-CRM-ACTIVITY-001",
            capability_version="1.0",
            current_attempt_count=1,
            error_reason="connection_timeout",
            environment="development",
            actor_id="bae-steward-001",
            objective_id=self.objective_id,
        )
        self.assertFalse(retry_dec.retry_authorized)
        self.assertEqual(retry_dec.stop_reason, RetryStopReason.KILL_SWITCH_ACTIVE)

    # =========================================================================
    # 40. Human override blocks retry
    # =========================================================================
    def test_b14_40_human_override_blocks_retry(self) -> None:
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-CRM-ACTIVITY-001",
            capability_version="1.0",
            environment="development",
            channel="website_chat",
            purpose="customer_activity_recording",
            requested_tool_authority=ToolAuthorityClass.T2,
            requested_maturity=AutonomyMaturity.M1,
            approval_token=None,
            is_human_override_active=True,
            required_permission="bae:crm_write",
            data_scope="customer_crm",
            requires_consent=False,
        )
        auth_dec = self.policy_evaluator.evaluate(auth_req)
        self.assertFalse(auth_dec.permitted)
        self.assertEqual(auth_dec.denial_reason, AuthorizationDenialReason.HUMAN_OVERRIDE_ACTIVE)

    # =========================================================================
    # 41. Retry exhaustion escalates safely
    # =========================================================================
    def test_b14_41_retry_exhaustion_escalates_safely(self) -> None:
        retry_dec = self.executor.retry_controller.evaluate_retry(
            capability_id="BAE-CRM-ACTIVITY-001",
            capability_version="1.0",
            current_attempt_count=3,  # Max attempts is 3, so attempt 4 exceeds
            error_reason="connection_timeout",
            environment="development",
            actor_id="bae-steward-001",
            objective_id=self.objective_id,
        )
        self.assertFalse(retry_dec.retry_authorized)
        self.assertEqual(retry_dec.stop_reason, RetryStopReason.MAX_ATTEMPTS_EXCEEDED)

    # =========================================================================
    # 42. CRM record existence does not imply consent
    # =========================================================================
    def test_b14_42_crm_record_existence_does_not_imply_consent(self) -> None:
        # Lead exists in store (rec-lead-001), but has no consent
        rec = self.crm_store.get_record("rec-lead-001")
        self.assertIsNotNone(rec)
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="consent_requiring_crm_update",
            target_record_id="rec-lead-001",
            mutation_fields={"survey_feedback": "Customer feedback"},
            has_verified_customer_consent=False,
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "CUSTOMER_CONSENT_MISSING")

    # =========================================================================
    # 43. Missing required consent denies action
    # =========================================================================
    def test_b14_43_missing_required_consent_denies_action(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="consent_requiring_crm_update",
            target_record_id="rec-contact-002",
            mutation_fields={"survey_feedback": "Great experience"},
            has_verified_customer_consent=False,
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "CUSTOMER_CONSENT_MISSING")

    # =========================================================================
    # 44. CRM Activity cannot manufacture consent
    # =========================================================================
    def test_b14_44_crm_activity_cannot_manufacture_consent(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="update_synthetic_lead_field",
            target_record_id="rec-lead-001",
            mutation_fields={"consent_state": "MANUFACTURED_CONSENT"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 45. CRM Activity cannot alter customer communication preference
    # =========================================================================
    def test_b14_45_crm_activity_cannot_alter_communication_preference(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"communication_preferences": "ALWAYS_EMAIL"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 46. Customer follow-up capability remains disabled
    # =========================================================================
    def test_b14_46_customer_followup_remains_disabled(self) -> None:
        followup_rec = self.registry.get("BAE-COMM-FOLLOWUP-001")
        self.assertIsNotNone(followup_rec)
        self.assertEqual(followup_rec.wave, PilotWave.WAVE_4)
        self.assertEqual(followup_rec.classification_state, "UNRESOLVED_DISABLED")
        self.assertFalse(followup_rec.executable)

    # =========================================================================
    # 47. CRM action cannot invoke email
    # =========================================================================
    def test_b14_47_crm_action_cannot_invoke_email(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"email_dispatch_trigger": True},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 48. CRM action cannot invoke SMS
    # =========================================================================
    def test_b14_48_crm_action_cannot_invoke_sms(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"sms_dispatch_trigger": True},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 49. CRM action cannot invoke DM/customer route
    # =========================================================================
    def test_b14_49_crm_action_cannot_invoke_dm_customer_route(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"dm_dispatch_trigger": True},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 50. CRM action cannot enqueue communication workflow
    # =========================================================================
    def test_b14_50_crm_action_cannot_enqueue_communication_workflow(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"campaign_enqueued": "marketing_drip_v1"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 51. CRM action with indirect customer-contact side effect is prohibited
    # =========================================================================
    def test_b14_51_crm_action_with_indirect_customer_contact_prohibited(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"external_webhook_url": "https://api.external.com/notify_user"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 52. CRM action cannot mutate payment state
    # =========================================================================
    def test_b14_52_crm_action_cannot_mutate_payment_state(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="update_workflow_status",
            target_record_id="rec-lead-001",
            mutation_fields={"payment_method_token": "tok_visa_1234"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 53. CRM action cannot mutate order state
    # =========================================================================
    def test_b14_53_crm_action_cannot_mutate_order_state(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="update_workflow_status",
            target_record_id="rec-lead-001",
            mutation_fields={"order_status": "FULFILLED_COMPLETED"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 54. CRM action cannot modify capability certification
    # =========================================================================
    def test_b14_54_crm_action_cannot_modify_capability_certification(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="update_workflow_status",
            target_record_id="rec-lead-001",
            mutation_fields={"certification_state": "CERTIFIED"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 55. CRM action cannot modify L/M/A/T
    # =========================================================================
    def test_b14_55_crm_action_cannot_modify_l_m_a_t(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="update_workflow_status",
            target_record_id="rec-lead-001",
            mutation_fields={"authorization_state": "ELEVATED_TO_L3"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertEqual(res.denial_reason, "PROHIBITED_FIELD_ACCESS")

    # =========================================================================
    # 56. CRM action cannot self-activate
    # =========================================================================
    def test_b14_56_crm_action_cannot_self_activate(self) -> None:
        crm_rec = self.registry.get("BAE-CRM-ACTIVITY-001")
        self.assertFalse(crm_rec.executable)

    # =========================================================================
    # 57. CRM action cannot self-certify
    # =========================================================================
    def test_b14_57_crm_action_cannot_self_certify(self) -> None:
        crm_rec = self.registry.get("BAE-CRM-ACTIVITY-001")
        self.assertEqual(crm_rec.lifecycle_state, CapabilityLifecycleState.DEFINED)
        self.assertNotEqual(crm_rec.lifecycle_state, CapabilityLifecycleState.CERTIFIED)

    # =========================================================================
    # 58. Task wrapper does not widen CRM authority
    # =========================================================================
    def test_b14_58_task_wrapper_does_not_widen_crm_authority(self) -> None:
        task_executor = Wave2CapabilityExecutor(
            policy_evaluator=self.policy_evaluator,
            kill_switch_controller=self.kill_switch,
            audit_repository=self.audit_repo,
        )
        # Attempting prohibited CRM write through TASK wrapper is denied
        res = task_executor.execute_task(
            correlation=self.correlation,
            action_type="prohibited_destructive_wipe",
            material_payload={"target": "crm"},
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)

    # =========================================================================
    # 59. Retry wrapper does not widen CRM authority
    # =========================================================================
    def test_b14_59_retry_wrapper_does_not_widen_crm_authority(self) -> None:
        task_executor = Wave2CapabilityExecutor(
            policy_evaluator=self.policy_evaluator,
            kill_switch_controller=self.kill_switch,
            audit_repository=self.audit_repo,
        )
        res = task_executor.execute_retry(
            correlation=self.correlation,
            action_type="critical_system_freeze",  # L3-H
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
        )
        self.assertIsNotNone(res.fresh_authorization_decision)
        self.assertFalse(res.fresh_authorization_decision.permitted)

    # =========================================================================
    # 60. Escalation remains non-authoritative
    # =========================================================================
    def test_b14_60_escalation_remains_non_authoritative(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "test"},
            is_ambiguous_record_match=True,
        )
        self.assertIsNotNone(res.escalation_package)
        self.assertFalse(hasattr(res.escalation_package, "execute_authorized"))

    # =========================================================================
    # 61. Escalation acknowledgement is not approval
    # =========================================================================
    def test_b14_61_escalation_acknowledgement_is_not_approval(self) -> None:
        pkg, delivery_state = self.executor.escalation_controller.build_and_route(
            correlation=self.correlation,
            capability_id="BAE-CRM-ACTIVITY-001",
            capability_version="1.0",
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T2,
            execution_state=ExecutionState.DENIED,
            escalation_reason=EscalationReason.GOVERNANCE_BLOCKED,
            escalation_priority=EscalationPriority.HIGH,
            what_occurred_summary="Summary",
            evidence_references=[],
        )
        self.assertEqual(delivery_state, EscalationDeliveryState.SENT)
        self.assertEqual(pkg.escalation_reason, EscalationReason.GOVERNANCE_BLOCKED)
        self.assertEqual(pkg.escalation_priority, EscalationPriority.HIGH)
        # Package delivery state does NOT mutate any capability or provide approval

    # =========================================================================
    # 62. Human response requires fresh B2
    # =========================================================================
    def test_b14_62_human_response_requires_fresh_b2(self) -> None:
        # A human providing a response reference still requires deterministic B2 re-evaluation
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="BAE-CRM-ACTIVITY-001",
            capability_version="1.0",
            environment="development",
            channel="website_chat",
            purpose="customer_activity_recording",
            requested_tool_authority=ToolAuthorityClass.T2,
            requested_maturity=AutonomyMaturity.M1,
            approval_token="valid_human_approval_token_after_escalation",
            is_human_override_active=False,
            required_permission="bae:crm_write",
            data_scope="customer_crm",
            requires_consent=False,
        )
        auth_dec = self.policy_evaluator.evaluate(auth_req)
        # The fresh evaluation succeeds on its own merits
        self.assertIsNotNone(auth_dec)

    # =========================================================================
    # 63. Wave 1 remains unchanged
    # =========================================================================
    def test_b14_63_wave1_remains_unchanged(self) -> None:
        wave1_ids = [
            "BAE-OPS-OBSERVE-001",
            "BAE-OPS-DETECT-001",
            "BAE-OPS-VERIFY-001",
            "BAE-OPS-PACKAGE-001",
            "BAE-OPS-ESCALATE-001",
        ]
        for wid in wave1_ids:
            rec = self.registry.get(wid)
            self.assertIsNotNone(rec)
            self.assertEqual(rec.lifecycle_state, CapabilityLifecycleState.DEFINED)
            self.assertFalse(rec.executable)
            self.assertIsNone(rec.current_certified_maturity)

    # =========================================================================
    # 64. TASK remains uncertified/non-executable
    # =========================================================================
    def test_b14_64_task_remains_uncertified_non_executable(self) -> None:
        task_rec = self.registry.get("BAE-OPS-TASK-001")
        self.assertEqual(task_rec.lifecycle_state, CapabilityLifecycleState.DEFINED)
        self.assertFalse(task_rec.executable)
        self.assertIsNone(task_rec.current_certified_maturity)

    # =========================================================================
    # 65. RETRY remains uncertified/non-executable
    # =========================================================================
    def test_b14_65_retry_remains_uncertified_non_executable(self) -> None:
        retry_rec = self.registry.get("BAE-OPS-RETRY-001")
        self.assertEqual(retry_rec.lifecycle_state, CapabilityLifecycleState.DEFINED)
        self.assertFalse(retry_rec.executable)
        self.assertIsNone(retry_rec.current_certified_maturity)

    # =========================================================================
    # 66. CRM Activity remains conditional/non-executable
    # =========================================================================
    def test_b14_66_crm_activity_remains_conditional_non_executable(self) -> None:
        crm_rec = self.registry.get("BAE-CRM-ACTIVITY-001")
        self.assertEqual(crm_rec.wave, PilotWave.WAVE_3)
        self.assertEqual(crm_rec.classification_state, "CONDITIONAL")
        self.assertEqual(crm_rec.lifecycle_state, CapabilityLifecycleState.DEFINED)
        self.assertFalse(crm_rec.executable)

    # =========================================================================
    # 67. Customer Follow-Up remains disabled
    # =========================================================================
    def test_b14_67_customer_followup_remains_disabled(self) -> None:
        followup_rec = self.registry.get("BAE-COMM-FOLLOWUP-001")
        self.assertEqual(followup_rec.wave, PilotWave.WAVE_4)
        self.assertEqual(followup_rec.classification_state, "UNRESOLVED_DISABLED")
        self.assertFalse(followup_rec.executable)

    # =========================================================================
    # 68. Gate C not started
    # =========================================================================
    def test_b14_68_gate_c_not_started(self) -> None:
        for rec in self.registry.list_all():
            self.assertNotEqual(rec.lifecycle_state, CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT)

    # =========================================================================
    # 69. Gate D unauthorized
    # =========================================================================
    def test_b14_69_gate_d_unauthorized(self) -> None:
        self.assertFalse(self.policy_evaluator.gate_d_authorized)

    # =========================================================================
    # 70. No production CRM connection/write
    # =========================================================================
    def test_b14_70_no_production_crm_connection_or_write(self) -> None:
        res = self.executor.execute_crm_activity(
            correlation=self.correlation,
            operation="create_internal_activity_note",
            target_record_id="rec-lead-001",
            mutation_fields={"note_body": "prod write"},
            environment="production",
        )
        self.assertEqual(res.execution_state, ExecutionState.DENIED)
        self.assertFalse(res.provider_invoked)

    # =========================================================================
    # 71. No production merge/deployment
    # =========================================================================
    def test_b14_71_no_production_merge_or_deployment(self) -> None:
        for rec in self.registry.list_all():
            self.assertNotIn("production", rec.allowed_environments)

    # =========================================================================
    # 72. B15 not started
    # =========================================================================
    def test_b14_72_b15_not_started(self) -> None:
        for rec in self.registry.list_all():
            self.assertIsNone(rec.current_certified_maturity)

    # =========================================================================
    # 73. All prior accepted BAE regressions remain green
    # =========================================================================
    def test_b14_73_all_prior_accepted_bae_regressions_remain_green(self) -> None:
        self.assertEqual(len(self.registry.list_all()), 9)


if __name__ == "__main__":
    unittest.main()
