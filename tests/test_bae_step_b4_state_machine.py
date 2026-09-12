"""Acceptance and unit tests for BAE Pilot 001 Step B4 Execution / Verification State Machine (Section 22 Scope)."""

import unittest
from uuid import uuid4

from src.budly_runtime.bae.capability_registry import BAECapabilityRegistry
from src.budly_runtime.bae.policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    BAEKillSwitchRegistry,
    ContinuousAuthorizationToken,
    DeterministicPolicyEvaluator,
    compute_material_fingerprint,
    utc_now,
)
from src.budly_runtime.bae.schemas import CapabilityRecord
from src.budly_runtime.bae.state_machine import (
    ExecutionState,
    ExecutionStateMachine,
    ExecutionStateRecord,
    StateTransitionError,
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


class TestBAEStepB4ExecutionStateMachine(unittest.TestCase):
    def setUp(self):
        self.objective_id = str(uuid4())
        self.correlation_id = str(uuid4())
        self.capability_id = "BAE-OPS-OBSERVE-001"
        self.actor_id = "bae-steward-001"
        self.actor_type = "bae_steward"
        self.environment = "development"
        self.kill_switches = BAEKillSwitchRegistry()
        self.sm = ExecutionStateMachine.create(
            objective_id=self.objective_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            environment=self.environment,
            kill_switches=self.kill_switches,
        )

    def test_b4_01_requested_to_authorization_pending(self):
        """REQUESTED -> AUTHORIZATION_PENDING transition succeeds."""
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.REQUESTED)
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted for policy evaluation")
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.AUTHORIZATION_PENDING)

    def test_b4_02_authorization_pending_to_authorized(self):
        """AUTHORIZATION_PENDING -> AUTHORIZED transition succeeds with permitted decision."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        decision = AuthorizationDecision(
            status=AuthorizationDecisionStatus.PERMITTED,
            permitted=True,
            requires_approval=False,
            approval_level=ApprovalLevel.A0,
            denial_reason=None,
            reason_detail="Permitted under L1/T0",
            step_token=ContinuousAuthorizationToken(
                token_id=str(uuid4()), objective_id=self.objective_id, step_number=1,
                capability_id=self.capability_id, issued_at=utc_now(), expires_at=utc_now(),
                actor_id=self.actor_id, environment=self.environment,
                checksum="TOKEN-1", material_state_fingerprint="fp1",
            ),
        )
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Policy evaluator permitted", authorization_decision=decision)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.AUTHORIZED)
        self.assertEqual(self.sm.record.authorization_decision, AuthorizationDecisionStatus.PERMITTED)

    def test_b4_03_authorization_pending_to_denied(self):
        """AUTHORIZATION_PENDING -> DENIED transition succeeds with denied decision."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        decision = AuthorizationDecision(
            status=AuthorizationDecisionStatus.DENIED,
            permitted=False,
            requires_approval=False,
            approval_level=ApprovalLevel.A0,
            denial_reason=AuthorizationDenialReason.CAPABILITY_NOT_CERTIFIED,
            reason_detail="Seed capability is not certified",
        )
        self.sm.transition(ExecutionState.DENIED, reason="Policy evaluator denied", authorization_decision=decision)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.DENIED)
        self.assertEqual(self.sm.record.authorization_decision, AuthorizationDecisionStatus.DENIED)
        self.assertEqual(self.sm.record.authorization_reason, "Seed capability is not certified")

    def test_b4_04_denied_cannot_transition_to_attempted(self):
        """DENIED state must never transition to ATTEMPTED (Invariant 1)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.DENIED, reason="Policy denied")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(ExecutionState.ATTEMPTED, reason="Illegal attempt")
        self.assertIn("Invariant violation", str(cm.exception))

    def test_b4_05_authorized_to_attempted(self):
        """AUTHORIZED -> ATTEMPTED transition succeeds."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.ATTEMPTED)

    def test_b4_06_attempted_to_tool_accepted(self):
        """ATTEMPTED -> TOOL_ACCEPTED transition succeeds."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Gateway accepted request", tool_provider_result={"status": "ACCEPTED"})
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.TOOL_ACCEPTED)

    def test_b4_07_attempted_to_executed_fails_directly(self):
        """ATTEMPTED -> EXECUTED directly fails deterministically (Section 22 Correction 1)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(ExecutionState.EXECUTED, reason="Direct execution without tool accepted")
        self.assertIn("must transition to TOOL_ACCEPTED first", str(cm.exception))

    def test_b4_08_tool_accepted_to_executed(self):
        """TOOL_ACCEPTED -> EXECUTED transition succeeds (Section 22 Canonical Path)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Tool execution finished", tool_provider_result={"status": "SUCCESS", "records": 3})
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.EXECUTED)

    def test_b4_09_tool_accepted_does_not_imply_verified(self):
        """TOOL_ACCEPTED must never transition directly to VERIFIED (Invariant 2)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(ExecutionState.VERIFIED, reason="Inferring verification from acceptance")
        self.assertIn("Invariant violation", str(cm.exception))

    def test_b4_10_executed_to_verification_pending(self):
        """EXECUTED -> VERIFICATION_PENDING transition succeeds and synchronizes VerificationState.PENDING."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting verification")
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.VERIFICATION_PENDING)
        self.assertEqual(self.sm.record.verification_state, VerificationState.PENDING)

    def test_b4_11_verification_pending_to_verified_with_authoritative_sot(self):
        """VERIFICATION_PENDING -> VERIFIED succeeds with AUTHORITATIVE_SOURCE_OF_TRUTH evidence."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting verification")
        self.sm.transition(
            ExecutionState.VERIFIED,
            reason="Authoritative ledger verified",
            verification_evidence_ref="EV-SOT-001",
            verification_evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
        )
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.VERIFIED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.VERIFIED)
        self.assertEqual(self.sm.record.verification_evidence_class, VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH)

    def test_b4_12_verification_pending_to_verified_with_deterministic_technical(self):
        """VERIFICATION_PENDING -> VERIFIED succeeds with DETERMINISTIC_DIRECT_TECHNICAL evidence when explicitly sufficient."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting verification")
        self.sm.transition(
            ExecutionState.VERIFIED,
            reason="Technical postcondition hash matched",
            verification_evidence_ref="EV-TECH-001",
            verification_evidence_class=VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL,
            technical_evidence_sufficient=True,
        )
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.VERIFIED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.VERIFIED)

    def test_b4_13_deterministic_technical_without_sufficiency_flag_fails(self):
        """DETERMINISTIC_DIRECT_TECHNICAL without explicit technical sufficiency identification fails."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting verification")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(
                ExecutionState.VERIFIED,
                reason="Technical postcondition check",
                verification_evidence_ref="EV-TECH-002",
                verification_evidence_class=VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL,
                technical_evidence_sufficient=False,
            )
        self.assertIn("requires explicit technical sufficiency identification", str(cm.exception))

    def test_b4_14_provider_acknowledgement_alone_cannot_produce_verified(self):
        """PROVIDER_ACKNOWLEDGEMENT alone cannot produce VERIFIED state (Section 22 Correction 2)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting verification")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(
                ExecutionState.VERIFIED,
                reason="Provider returned 200 OK",
                verification_evidence_ref="EV-ACK-001",
                verification_evidence_class=VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT,
            )
        self.assertIn("cannot produce VERIFIED state", str(cm.exception))

    def test_b4_15_agent_self_report_alone_cannot_produce_verified(self):
        """AGENT_SELF_REPORT alone cannot produce VERIFIED state (Section 22 Correction 2)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting verification")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(
                ExecutionState.VERIFIED,
                reason="Agent asserts task complete",
                verification_evidence_ref="EV-SELF-001",
                verification_evidence_class=VerificationEvidenceClass.AGENT_SELF_REPORT,
            )
        self.assertIn("cannot produce VERIFIED state", str(cm.exception))

    def test_b4_16_verification_pending_to_partially_verified(self):
        """VERIFICATION_PENDING -> PARTIALLY_VERIFIED succeeds and synchronizes VerificationState."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting verification")
        self.sm.transition(
            ExecutionState.PARTIALLY_VERIFIED,
            reason="Partial corroboration found",
            verification_evidence_class=VerificationEvidenceClass.CORROBORATED_SECONDARY_OPERATIONAL,
        )
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.PARTIALLY_VERIFIED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.PARTIALLY_VERIFIED)

    def test_b4_17_partial_verification_reverification_path_succeeds(self):
        """PARTIALLY_VERIFIED -> VERIFICATION_PENDING -> VERIFIED path with authoritative evidence succeeds."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting verification")
        self.sm.transition(ExecutionState.PARTIALLY_VERIFIED, reason="Partial evidence")

        # Direct PARTIALLY_VERIFIED -> VERIFIED is blocked
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(
                ExecutionState.VERIFIED,
                reason="Attempting direct jump",
                verification_evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            )
        self.assertIn("must transition to VERIFICATION_PENDING first", str(cm.exception))

        # Canonical path: PARTIALLY_VERIFIED -> VERIFICATION_PENDING -> VERIFIED
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Re-evaluating with new evidence")
        self.assertEqual(self.sm.record.verification_state, VerificationState.PENDING)

        self.sm.transition(
            ExecutionState.VERIFIED,
            reason="New authoritative evidence confirmed",
            verification_evidence_ref="EV-NEW-SOT",
            verification_evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
        )
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.VERIFIED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.VERIFIED)

    def test_b4_18_partial_verification_reverification_with_weak_evidence_fails(self):
        """PARTIALLY_VERIFIED -> VERIFICATION_PENDING cannot become VERIFIED with weak provider evidence."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting verification")
        self.sm.transition(ExecutionState.PARTIALLY_VERIFIED, reason="Partial evidence")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Re-evaluating")

        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(
                ExecutionState.VERIFIED,
                reason="Provider ack presented as new evidence",
                verification_evidence_class=VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT,
            )
        self.assertIn("cannot produce VERIFIED state", str(cm.exception))

    def test_b4_19_unverified_cannot_become_complete_as_success(self):
        """UNVERIFIED cannot transition directly to COMPLETE as success (Invariant 7)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Pending")
        self.sm.transition(ExecutionState.UNVERIFIED, reason="Unverified")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(ExecutionState.COMPLETE, reason="Assuming success")
        self.assertIn("Invariant violation", str(cm.exception))

    def test_b4_20_unknown_cannot_become_complete_as_success(self):
        """UNKNOWN cannot transition directly to COMPLETE as success (Invariant 7)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Pending")
        self.sm.transition(ExecutionState.UNKNOWN, reason="Unknown")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(ExecutionState.COMPLETE, reason="Assuming success")
        self.assertIn("Invariant violation", str(cm.exception))

    def test_b4_21_failed_to_complete_with_success_disposition_fails(self):
        """FAILED -> COMPLETE with a SUCCESS disposition is prohibited (Section 22 Correction 4)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.FAILED, reason="Execution failed")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(ExecutionState.COMPLETE, reason="Closing execution", explicit_disposition="SUCCESS")
        self.assertIn("cannot produce a SUCCESS disposition", str(cm.exception))

    def test_b4_22_failed_to_complete_with_explicit_failure_closure_succeeds(self):
        """FAILED -> COMPLETE with explicit failure closure succeeds."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.FAILED, reason="Execution failed")
        self.sm.transition(ExecutionState.COMPLETE, reason="Terminal failure closure", explicit_disposition="FAILED_UNRECOVERABLE")
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.COMPLETE)
        self.assertEqual(self.sm.record.final_disposition, "FAILED_UNRECOVERABLE")

    def test_b4_23_escalated_or_waiting_to_complete_cannot_masquerade_as_success(self):
        """ESCALATED or WAITING -> COMPLETE with SUCCESS disposition is prohibited."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.DENIED, reason="Denied")
        self.sm.transition(ExecutionState.ESCALATED, reason="Escalated to human supervisor")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(ExecutionState.COMPLETE, reason="Masquerading success", explicit_disposition="SUCCESS")
        self.assertIn("cannot produce a SUCCESS disposition", str(cm.exception))

        self.sm.transition(ExecutionState.WAITING, reason="Waiting for supervisor")
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(ExecutionState.COMPLETE, reason="Masquerading success", explicit_disposition="SUCCESS")
        self.assertIn("cannot produce a SUCCESS disposition", str(cm.exception))

        # Explicit non-success closure succeeds
        self.sm.transition(ExecutionState.COMPLETE, reason="Closed unresolved", explicit_disposition="RESOLVED_MANUALLY")
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.COMPLETE)
        self.assertEqual(self.sm.record.final_disposition, "RESOLVED_MANUALLY")

    def test_b4_24_failed_cannot_enter_retry_scheduled_without_explicit_retry_authorization(self):
        """FAILED cannot enter RETRY_SCHEDULED without explicit retry authorization (Invariant 9)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Calling Gateway")
        self.sm.transition(ExecutionState.FAILED, reason="Execution failed", retry_authorized=False)
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(ExecutionState.RETRY_SCHEDULED, reason="Scheduling retry", retry_authorized=False)
        self.assertIn("without explicit retry authorization", str(cm.exception))

    def test_b4_25_valid_kill_switch_causes_stopped(self):
        """Active kill switch forces transition to STOPPED before next material step (Invariant 11)."""
        self.kill_switches.trigger(KillSwitchScope.CAPABILITY, self.capability_id, "Emergency stop test")
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.STOPPED)
        self.assertEqual(self.sm.record.final_disposition, "STOPPED")

    def test_b4_26_valid_human_override_causes_stopped(self):
        """Valid human override forces transition to STOPPED immediately (Invariant 11)."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitted")
        self.sm.transition(ExecutionState.STOPPED, reason="Human operator requested stop", human_override_stop=True)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.STOPPED)
        self.assertEqual(self.sm.record.final_disposition, "STOPPED")

    def test_b4_27_approval_or_authorization_change_forces_reauthorization(self):
        """State changes require transitioning back to AUTHORIZATION_PENDING before next material action."""
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Initial check")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted")
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Context updated, reauthorizing")
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.AUTHORIZATION_PENDING)

    def test_b4_28_correlation_objective_action_identifiers_persist_through_transitions(self):
        """All correlation, objective, and action identifiers remain invariant throughout lifecycle."""
        init_obj = self.sm.record.objective_id
        init_act = self.sm.record.action_id
        init_cor = self.sm.record.correlation_id

        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Step 1")
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Step 2")
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Step 3")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Step 4")
        self.sm.transition(ExecutionState.EXECUTED, reason="Step 5")
        self.sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Step 6")
        self.sm.transition(
            ExecutionState.VERIFIED,
            reason="Step 7",
            verification_evidence_ref="EV-1",
            verification_evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
        )
        self.sm.transition(ExecutionState.COMPLETE, reason="Step 8")

        self.assertEqual(self.sm.record.objective_id, init_obj)
        self.assertEqual(self.sm.record.action_id, init_act)
        self.assertEqual(self.sm.record.correlation_id, init_cor)
        self.assertEqual(len(self.sm.record.state_history), 9)  # 1 initial + 8 transitions

    def test_b4_29_all_nine_pilot_seed_capabilities_remain_non_executable(self):
        """All 9 seed capabilities are non-executable in B2 evaluator and transition safely to DENIED."""
        seed_registry = BAECapabilityRegistry.load_seed()
        seed_evaluator = DeterministicPolicyEvaluator(seed_registry, self.kill_switches)

        for seed_cap in seed_registry.list_all():
            sm = ExecutionStateMachine.create(
                objective_id=str(uuid4()),
                correlation_id=str(uuid4()),
                capability_id=seed_cap.capability_id,
                actor_id=self.actor_id,
                actor_type=self.actor_type,
                environment=self.environment,
                kill_switches=self.kill_switches,
                policy_evaluator=seed_evaluator,
            )
            sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Evaluating seed capability")
            auth_req = AuthorizationRequest(
                request_id=str(uuid4()),
                correlation_id=str(uuid4()),
                objective_id=sm.record.objective_id,
                step_number=1,
                actor_id=self.actor_id,
                actor_type=self.actor_type,
                capability_id=seed_cap.capability_id,
                capability_version="1.0",
                environment=self.environment,
                channel="system_internal",
                purpose="internal_test",
                requested_tool_authority=seed_cap.tool_authority or ToolAuthorityClass.T0,
            )
            decision = seed_evaluator.evaluate(auth_req)
            self.assertFalse(decision.permitted)
            sm.transition(ExecutionState.DENIED, reason="Seed capability denied", authorization_decision=decision)
            self.assertEqual(sm.record.current_execution_state, ExecutionState.DENIED)
            self.assertEqual(sm.record.authorization_decision, AuthorizationDecisionStatus.DENIED)


if __name__ == "__main__":
    unittest.main()
