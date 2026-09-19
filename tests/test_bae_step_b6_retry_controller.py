"""Acceptance and unit test matrix for BAE Pilot 001 Step B6 Retry / Idempotency Controller."""

import unittest
from datetime import datetime, timedelta, timezone
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
from src.budly_runtime.bae.retry_controller import (
    FailureClass,
    IdempotencyDisposition,
    IdempotencyRecord,
    IdempotencyStore,
    RetryAttempt,
    RetryController,
    RetryDecision,
    RetryPolicy,
    RetryPolicyRegistry,
    RetryStopReason,
)
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
    ToolAuthorityClass,
)
from src.budly_runtime.bae.verification_engine import (
    AuthoritativeVerificationEngine,
    EvidenceProvenanceToken,
    VerificationAccessDecision,
    VerificationEvidenceItem,
    VerificationMethod,
    VerificationOutcome,
    VerificationReason,
    VerificationRequest,
)


class TestBAEStepB6RetryController(unittest.TestCase):
    def setUp(self):
        self.objective_id = str(uuid4())
        self.action_id = str(uuid4())
        self.correlation_id = str(uuid4())
        self.capability_id = "BAE-OPS-OBSERVE-001"
        self.capability_version = "1.0"
        self.actor_id = "bae-steward-001"
        self.actor_type = "bae_steward"
        self.environment = "development"
        self.idempotency_key = f"IDEM-KEY-{uuid4()}"
        self.material_payload = {"telemetry_id": "TEL-100", "ingested": True}

        self.kill_switches = BAEKillSwitchRegistry()
        self.policy_registry = RetryPolicyRegistry.default_registry()
        self.idempotency_store = IdempotencyStore()
        self.controller = RetryController(
            policy_registry=self.policy_registry,
            idempotency_store=self.idempotency_store,
            kill_switches=self.kill_switches,
        )

        # Baseline capability registry & evaluator for B2 recheck
        self.cap_registry = BAECapabilityRegistry()
        from src.budly_runtime.bae.schemas import CapabilityRecord
        from src.budly_runtime.bae.types import PilotWave
        self.test_cap = CapabilityRecord(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            capability_name="Ops Observe Governed",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L1,
            current_certified_maturity=AutonomyMaturity.M1,
            target_pilot_entry_maturity=AutonomyMaturity.M1,
            maximum_governable_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT,
            certification_signature="SIG-VALID-TEST",
            certified_at=utc_now(),
            certified_by="sec_admin",
            allowed_environments=frozenset({"development", "automated_test"}),
            allowed_channels=frozenset({"system_internal", "website_chat"}),
            allowed_purposes=frozenset({"internal_test", "customer_education"}),
        )
        self.cap_registry.register(self.test_cap)
        self.evaluator = DeterministicPolicyEvaluator(self.cap_registry, self.kill_switches)

        # Create base state machine advanced to FAILED state
        self.sm = ExecutionStateMachine.create(
            objective_id=self.objective_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            environment=self.environment,
            kill_switches=self.kill_switches,
        )
        self.sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Auth check")
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
        self.sm.transition(ExecutionState.AUTHORIZED, reason="Permitted", authorization_decision=decision)
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Attempted")
        self.sm.transition(ExecutionState.FAILED, reason="Temporary network timeout", error_classification="NETWORK_TIMEOUT")

    # =========================================================================
    # 1. RETRY POLICY & FAILURE CLASSIFICATION TESTS
    # =========================================================================

    def test_b6_01_failed_action_with_retryable_policy_schedules_retry(self):
        """FAILED action with explicitly retryable failure reason transitions to RETRY_SCHEDULED."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.assertTrue(decision.retry_authorized)
        self.assertEqual(decision.failure_class, FailureClass.RETRYABLE)
        self.assertEqual(decision.attempt_number, 2)
        self.assertGreater(decision.delay_seconds, 0)

        self.controller.apply_retry_scheduling(self.sm, decision)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.RETRY_SCHEDULED)

    def test_b6_02_failed_action_without_retry_authorization_cannot_schedule_retry(self):
        """Attempting to transition FAILED to RETRY_SCHEDULED without retry authorization raises StateTransitionError."""
        with self.assertRaises(StateTransitionError) as cm:
            self.sm.transition(ExecutionState.RETRY_SCHEDULED, reason="Direct un-authorized retry attempt", retry_authorized=False)
        self.assertIn("FAILED cannot enter RETRY_SCHEDULED without explicit retry authorization", str(cm.exception))

    def test_b6_03_non_retryable_failure_produces_terminal_no_retry(self):
        """Non-retryable failure reason produces terminal non-retry decision."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="INPUT_VALIDATION_FAILED",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.assertFalse(decision.retry_authorized)
        self.assertEqual(decision.failure_class, FailureClass.NON_RETRYABLE)
        self.assertEqual(decision.stop_reason, RetryStopReason.NON_RETRYABLE_FAILURE)

    def test_b6_04_terminal_failure_class_stops_retry(self):
        """Terminal failure reason immediately produces terminal non-retry decision."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="PERMANENT_CORRUPTION",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.assertFalse(decision.retry_authorized)
        self.assertEqual(decision.failure_class, FailureClass.TERMINAL)
        self.assertEqual(decision.stop_reason, RetryStopReason.TERMINAL_FAILURE)

    def test_b6_05_max_attempts_exceeded_stops_retry(self):
        """When attempt count exceeds max_attempts, retry is terminated."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=3,  # Max is 3
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.assertFalse(decision.retry_authorized)
        self.assertEqual(decision.stop_reason, RetryStopReason.MAX_ATTEMPTS_EXCEEDED)

    def test_b6_06_deterministic_bounded_backoff_calculation(self):
        """Retry delay follows deterministic exponential backoff bounded by max_delay_seconds."""
        policy = RetryPolicy(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            max_attempts=5,
            initial_delay_seconds=10,
            backoff_multiplier=2.0,
            max_delay_seconds=35,
        )
        self.assertEqual(policy.calculate_backoff(1), 10)
        self.assertEqual(policy.calculate_backoff(2), 20)
        self.assertEqual(policy.calculate_backoff(3), 35)  # Capped by max_delay_seconds

    # =========================================================================
    # 2. CONTINUOUS RE-AUTHORIZATION BEFORE RETRY EXECUTION TESTS
    # =========================================================================

    def test_b6_07_due_retry_passes_b2_reauthorization(self):
        """Due retry successfully passes fresh B2 authorization and transitions to AUTHORIZED."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        prior_token = f"TOKEN-{self.objective_id}-1-TEST"
        self.evaluator._issued_tokens[prior_token] = ContinuousAuthorizationToken(
            token_id=prior_token,
            objective_id=self.objective_id,
            step_number=1,
            capability_id=self.capability_id,
            issued_at=utc_now(),
            expires_at=utc_now(),
            actor_id=self.actor_id,
            environment=self.environment,
            checksum="TOKEN-1",
            material_state_fingerprint="fp1",
        )
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=prior_token,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=auth_req, evaluator=self.evaluator,
        )
        self.assertTrue(authorized)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.AUTHORIZED)

    def test_b6_08_permission_revoked_before_retry_denies_execution(self):
        """If actor permission or allowed capability state changes before retry, B2 denies execution."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        # Revoke capability in registry before retry execution
        from src.budly_runtime.bae.schemas import CapabilityRecord
        from src.budly_runtime.bae.types import PilotWave
        revoked_cap = CapabilityRecord(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            capability_name="Activity Record Governed",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L1,
            current_certified_maturity=AutonomyMaturity.M1,
            target_pilot_entry_maturity=AutonomyMaturity.M1,
            maximum_governable_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.RETIRED,  # Retired/revoked
            executable=False,
            allowed_environments=frozenset({"development"}),
            allowed_channels=frozenset({"system_internal"}),
            allowed_purposes=frozenset({"internal_test"}),
        )
        self.cap_registry._records[self.capability_id] = revoked_cap

        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=auth_req, evaluator=self.evaluator,
        )
        self.assertFalse(authorized)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.DENIED)

    def test_b6_09_kill_switch_activated_before_retry_denies_execution(self):
        """If kill switch is activated before scheduled retry execution, retry evaluation halts."""
        from src.budly_runtime.bae.types import KillSwitchScope
        self.kill_switches.trigger(KillSwitchScope.CAPABILITY, self.capability_id, "Security incident")
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.assertFalse(decision.retry_authorized)
        self.assertEqual(decision.stop_reason, RetryStopReason.KILL_SWITCH_ACTIVE)

    def test_b6_10_environment_change_before_retry_denies_execution(self):
        """Attempting to execute retry in unauthorized environment (e.g. production) is denied."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        prod_auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment="production",  # Prohibited environment
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=prod_auth_req, evaluator=self.evaluator,
        )
        self.assertFalse(authorized)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.DENIED)

    def test_b6_11_scheduling_retry_does_not_execute_tool(self):
        """Transitioning to RETRY_SCHEDULED records the schedule without entering ATTEMPTED or EXECUTED."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.RETRY_SCHEDULED)
        self.assertNotEqual(self.sm.record.current_execution_state, ExecutionState.ATTEMPTED)
        self.assertNotEqual(self.sm.record.current_execution_state, ExecutionState.EXECUTED)

    # =========================================================================
    # 3. IDEMPOTENCY RECORD & BINDING TESTS
    # =========================================================================

    def test_b6_12_idempotency_key_first_use_records_state(self):
        """First use of an idempotency key records initial attempt."""
        disp, record, reason = self.controller.evaluate_idempotency(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
        )
        self.assertEqual(disp, IdempotencyDisposition.FIRST_USE)
        self.assertIsNone(record)

        rec = self.idempotency_store.record_first_use(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
            initial_state=ExecutionState.ATTEMPTED,
        )
        self.assertEqual(rec.attempt_count, 1)
        self.assertEqual(rec.idempotency_key, self.idempotency_key)

    def test_b6_13_duplicate_key_after_verified_success_produces_no_op(self):
        """Duplicate idempotency key after a VERIFIED effect produces DUPLICATE_NO_OP_VERIFIED."""
        self.idempotency_store.record_first_use(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
            initial_state=ExecutionState.VERIFIED,
        )
        disp, record, reason = self.controller.evaluate_idempotency(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
        )
        self.assertEqual(disp, IdempotencyDisposition.DUPLICATE_NO_OP_VERIFIED)
        self.assertIn("Action already verified successful", reason)

    def test_b6_14_duplicate_key_after_uncertain_state_preserves_evidence(self):
        """Duplicate key after UNKNOWN or UNVERIFIED state preserves uncertainty without blind replay."""
        self.idempotency_store.record_first_use(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
            initial_state=ExecutionState.UNKNOWN,
        )
        disp, record, reason = self.controller.evaluate_idempotency(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
        )
        self.assertEqual(disp, IdempotencyDisposition.DUPLICATE_UNCERTAIN_PRESERVED)

    def test_b6_15_cross_context_idempotency_key_reuse_rejected(self):
        """Attempting to reuse an idempotency key across different objectives or capabilities is rejected."""
        self.idempotency_store.record_first_use(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
            initial_state=ExecutionState.ATTEMPTED,
        )
        disp, record, reason = self.controller.evaluate_idempotency(
            idempotency_key=self.idempotency_key,
            objective_id=str(uuid4()),  # Unrelated objective
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
        )
        self.assertEqual(disp, IdempotencyDisposition.CROSS_CONTEXT_REUSE_REJECTED)

    def test_b6_16_payload_hash_mismatch_for_idempotency_key_rejected(self):
        """Presenting different material payload with same idempotency key is rejected."""
        self.idempotency_store.record_first_use(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
            initial_state=ExecutionState.ATTEMPTED,
        )
        disp, record, reason = self.controller.evaluate_idempotency(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload={"activity_id": "ACT-999_TAMPERED", "persisted": True},
        )
        self.assertEqual(disp, IdempotencyDisposition.CROSS_CONTEXT_REUSE_REJECTED)

    def test_b6_17_attempt_lineage_and_audit_history_preserved(self):
        """Updating idempotency attempts preserves complete audit trail."""
        self.idempotency_store.record_first_use(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
            initial_state=ExecutionState.FAILED,
        )
        updated = self.idempotency_store.update_attempt(
            idempotency_key=self.idempotency_key,
            new_state=ExecutionState.VERIFIED,
            verification_outcome=VerificationOutcome.VERIFIED,
            error_reason=None,
            failure_class=None,
            auth_decision_ref="AUTH-STEP-2",
        )
        self.assertEqual(updated.attempt_count, 2)
        self.assertTrue(updated.is_verified_success)
        self.assertEqual(len(updated.attempts), 2)
        self.assertEqual(updated.attempts[1].attempt_number, 2)

    def test_b6_18_all_nine_pilot_capabilities_remain_non_executable(self):
        """All 9 seed capabilities evaluate to DENIED under B2 policy evaluator."""
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

    # =========================================================================
    # 4. SECTION 27 NARROW COMPLETION TESTS
    # =========================================================================

    def test_b6_19_approval_revoked_or_expired_before_due_retry_denies_execution(self):
        """Where approval applies (L2/A1+), expired/revoked approval before retry denies execution."""
        from src.budly_runtime.bae.schemas import CapabilityRecord
        from src.budly_runtime.bae.types import PilotWave
        approval_cap = CapabilityRecord(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            capability_name="Ops Observe Governed",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L2,  # Requires human approval
            current_certified_maturity=AutonomyMaturity.M1,
            target_pilot_entry_maturity=AutonomyMaturity.M1,
            maximum_governable_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A1,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT,
            certification_signature="SIG-VALID-TEST",
            certified_at=utc_now(),
            certified_by="sec_admin",
            allowed_environments=frozenset({"development", "automated_test"}),
            allowed_channels=frozenset({"system_internal", "website_chat"}),
            allowed_purposes=frozenset({"internal_test", "customer_education"}),
        )
        self.cap_registry._records[self.capability_id] = approval_cap

        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        # Retry request with missing/expired approval token (approval_token=None)
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=f"TOKEN-{self.objective_id}-1-TEST",
            approval_token=None,  # No valid approval token
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=auth_req, evaluator=self.evaluator,
        )
        self.assertFalse(authorized)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.DENIED)

    def test_b6_20_consent_revoked_before_due_retry_denies_execution(self):
        """Where customer consent applies, consent revocation before retry denies execution."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        # Re-evaluating authorization with is_consent_revoked=True
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=f"TOKEN-{self.objective_id}-1-TEST",
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
            requires_consent=True,
            consent_token="CONSENT-TOKEN-001",
            is_consent_revoked=True,  # Revoked before retry
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=auth_req, evaluator=self.evaluator,
        )
        self.assertFalse(authorized)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.DENIED)

    def test_b6_21_human_override_activated_before_due_retry_stops_execution(self):
        """Human operator override active before due retry halts retry and sets DENIED/STOPPED."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=f"TOKEN-{self.objective_id}-1-TEST",
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
            is_human_override_active=True,  # Operator override
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=auth_req, evaluator=self.evaluator,
        )
        self.assertFalse(authorized)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.DENIED)
        self.sm.transition(ExecutionState.STOPPED, reason="Halted by human override")
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.STOPPED)

    def test_b6_22_capability_suspended_before_retry_denies_execution(self):
        """Capability lifecycle transitioning to SUSPENDED before due retry denies execution."""
        from src.budly_runtime.bae.schemas import CapabilityRecord
        from src.budly_runtime.bae.types import PilotWave
        suspended_cap = CapabilityRecord(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            capability_name="Ops Observe Governed",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L1,
            current_certified_maturity=AutonomyMaturity.M1,
            target_pilot_entry_maturity=AutonomyMaturity.M1,
            maximum_governable_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.SUSPENDED,  # Suspended
            executable=False,
            allowed_environments=frozenset({"development"}),
            allowed_channels=frozenset({"system_internal"}),
            allowed_purposes=frozenset({"internal_test"}),
        )
        self.cap_registry._records[self.capability_id] = suspended_cap

        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=f"TOKEN-{self.objective_id}-1-TEST",
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=auth_req, evaluator=self.evaluator,
        )
        self.assertFalse(authorized)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.DENIED)

    def test_b6_23_capability_restricted_before_retry_denies_execution(self):
        """Capability lifecycle transitioning to RESTRICTED before due retry denies execution."""
        from src.budly_runtime.bae.schemas import CapabilityRecord
        from src.budly_runtime.bae.types import PilotWave
        restricted_cap = CapabilityRecord(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            capability_name="Ops Observe Governed",
            wave=PilotWave.WAVE_1,
            authority_class=AuthorityClass.L1,
            current_certified_maturity=AutonomyMaturity.M1,
            target_pilot_entry_maturity=AutonomyMaturity.M1,
            maximum_governable_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T0,
            lifecycle_state=CapabilityLifecycleState.RESTRICTED,  # Restricted
            executable=False,
            allowed_environments=frozenset({"development"}),
            allowed_channels=frozenset({"system_internal"}),
            allowed_purposes=frozenset({"internal_test"}),
        )
        self.cap_registry._records[self.capability_id] = restricted_cap

        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=f"TOKEN-{self.objective_id}-1-TEST",
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=auth_req, evaluator=self.evaluator,
        )
        self.assertFalse(authorized)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.DENIED)

    def test_b6_24_duplicate_key_after_provider_acknowledgement_alone_preserves_uncertainty(self):
        """Duplicate key where prior attempt only received provider acknowledgement yields DUPLICATE_UNCERTAIN_PRESERVED."""
        self.idempotency_store.record_first_use(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
            initial_state=ExecutionState.UNVERIFIED,
        )
        disp, record, reason = self.controller.evaluate_idempotency(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
        )
        self.assertEqual(disp, IdempotencyDisposition.DUPLICATE_UNCERTAIN_PRESERVED)
        self.assertFalse(record.is_verified_success)

    def test_b6_25_duplicate_key_after_partially_verified_preserves_uncertainty(self):
        """Duplicate key after PARTIALLY_VERIFIED preserves uncertainty without blind replay."""
        self.idempotency_store.record_first_use(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
            initial_state=ExecutionState.PARTIALLY_VERIFIED,
        )
        disp, record, reason = self.controller.evaluate_idempotency(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
        )
        self.assertEqual(disp, IdempotencyDisposition.DUPLICATE_UNCERTAIN_PRESERVED)

    def test_b6_26_full_retry_execution_and_b5_verification_lifecycle(self):
        """Full retry lifecycle: RETRY_SCHEDULED -> AUTHORIZATION_PENDING -> AUTHORIZED -> ATTEMPTED -> TOOL_ACCEPTED -> EXECUTED -> VERIFICATION_PENDING -> VERIFIED."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.RETRY_SCHEDULED)

        # Fresh B2 authorization
        prior_token = f"TOKEN-{self.objective_id}-1-TEST"
        self.evaluator._issued_tokens[prior_token] = ContinuousAuthorizationToken(
            token_id=prior_token,
            objective_id=self.objective_id,
            step_number=1,
            capability_id=self.capability_id,
            issued_at=utc_now(),
            expires_at=utc_now(),
            actor_id=self.actor_id,
            environment=self.environment,
            checksum="TOKEN-1",
            material_state_fingerprint="fp1",
        )
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=prior_token,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=auth_req, evaluator=self.evaluator,
        )
        self.assertTrue(authorized)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.AUTHORIZED)

        # Advance execution
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Retry executed")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted by gateway")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed by adapter")

        # B5 Verification
        engine = AuthoritativeVerificationEngine()
        access = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment=self.environment,
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.ops_telemetry",
        )
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-RETRY-VERIFY",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name="telemetry_ingested",
            source_identifier="postgres_ops_telemetry_db",
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state=self.material_payload,
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-RETRY-VERIFY",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier="postgres_ops_telemetry_db",
            observed_state=self.material_payload,
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="telemetry_ingested",
            provenance_token=prov,
        )
        ver_req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name="telemetry_ingested",
            expected_state=self.material_payload,
            evidence_items=(evidence,),
            access_decision=access,
        )
        ver_res = engine.verify(ver_req)
        engine.apply_to_state_machine(self.sm, ver_res)

        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.VERIFIED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.VERIFIED)

    # =========================================================================
    # 5. SECTION 28 FINAL EVIDENCE COMPLETION TESTS
    # =========================================================================

    def test_b6_27_gate_d_release_state_retry_enforcement(self):
        """Production retry with Gate D inactive / invalid release state is DENIED; DEV/TEST remains eligible."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment="production",
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        # 1. Production retry attempt with invalid release_state -> DENIED
        prod_auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=f"TOKEN-{self.objective_id}-1-TEST",
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment="production",
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
            release_state="UNAUTHORIZED_PROD",
            expected_release_state="PILOT_AUTHORIZED",
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=prod_auth_req, evaluator=self.evaluator,
        )
        self.assertFalse(authorized)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.DENIED)

        # 2. Development retry attempt with valid release_state -> PERMITTED
        dev_auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=f"TOKEN-{self.objective_id}-1-TEST",
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
            release_state="PILOT_AUTHORIZED",
            expected_release_state="PILOT_AUTHORIZED",
        )
        prior_token = f"TOKEN-{self.objective_id}-1-TEST"
        self.evaluator._issued_tokens[prior_token] = ContinuousAuthorizationToken(
            token_id=prior_token,
            objective_id=self.objective_id,
            step_number=1,
            capability_id=self.capability_id,
            issued_at=utc_now(),
            expires_at=utc_now(),
            actor_id=self.actor_id,
            environment=self.environment,
            checksum="TOKEN-1",
            material_state_fingerprint="fp1",
        )
        dev_sm = ExecutionStateMachine.create(
            objective_id=self.objective_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            environment=self.environment,
            kill_switches=self.kill_switches,
            policy_evaluator=self.evaluator,
        )
        dev_sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Initial")
        dev_sm.transition(ExecutionState.AUTHORIZED, reason="Initial authorized")
        dev_sm.transition(ExecutionState.ATTEMPTED, reason="Attempted")
        dev_sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted")
        dev_sm.transition(ExecutionState.EXECUTED, reason="Executed")
        dev_sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Pending")
        dev_sm.transition(ExecutionState.FAILED, reason="Failed")
        self.controller.apply_retry_scheduling(dev_sm, decision)
        dev_authorized, dev_b2_dec = self.controller.authorize_retry_execution(
            sm=dev_sm, auth_request=dev_auth_req, evaluator=self.evaluator,
        )
        self.assertTrue(dev_authorized)
        self.assertEqual(dev_sm.record.current_execution_state, ExecutionState.AUTHORIZED)

    def test_b6_28_due_retry_b3_tool_gateway_positive_path(self):
        """Due retry passes B2, executes via canonical ToolGateway, advances B4 and B5."""
        from src.budly_runtime.tool_gateway import (
            Actor,
            ActorPermission,
            AuditSink,
            CapabilityDefinition,
            CapabilityRef,
            KnowledgeRetrieveInput,
            LocalKnowledgeAdapter,
            ResultStatus,
            ToolGateway,
            ToolRegistry,
            ToolRequest,
        )
        # Setup ToolGateway and Adapter
        fixtures = [
            {
                "knowledge_id": "KB-POLICY-001",
                "title": "Return Policy",
                "version": "1.0",
                "domain": "customer_policy",
                "status": "Active",
                "classification": "Public",
                "source_reference": "POLICY-DOC-001",
                "content": "30-day return policy for unopened items.",
            }
        ]
        adapter = LocalKnowledgeAdapter(fixtures)
        cap_def = CapabilityDefinition(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            bros_level=1,
            tool_class="T0",
            enabled=True,
            allowed_environments=frozenset({"automated_test", "development"}),
            allowed_purposes=frozenset({"customer_education", "internal_test"}),
            allowed_channels=frozenset({"website_chat", "system_internal"}),
        )
        registry = ToolRegistry(cap_def, adapter)
        audit = AuditSink()
        permissions = {
            self.actor_type: ActorPermission(
                self.actor_type,
                frozenset({"customer_policy"}),
                frozenset({"Public", "PUBLIC"}),
                frozenset({"customer_education", "internal_test"}),
                frozenset({"system_internal", "website_chat"}),
            )
        }
        gateway = ToolGateway(registry, audit, {self.capability_id: permissions}, policy_evaluator=self.evaluator)

        # Retry becomes due
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        # Fresh B2 authorization
        prior_token = f"TOKEN-{self.objective_id}-1-TEST"
        self.evaluator._issued_tokens[prior_token] = ContinuousAuthorizationToken(
            token_id=prior_token,
            objective_id=self.objective_id,
            step_number=1,
            capability_id=self.capability_id,
            issued_at=utc_now(),
            expires_at=utc_now(),
            actor_id=self.actor_id,
            environment=self.environment,
            checksum="TOKEN-1",
            material_state_fingerprint="fp1",
        )
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=prior_token,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=auth_req, evaluator=self.evaluator,
        )
        self.assertTrue(authorized)

        # Execute through canonical ToolGateway
        tool_req = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            actor=Actor(actor_id=self.actor_id, actor_type=self.actor_type),
            capability=CapabilityRef(self.capability_id, self.capability_version),
            purpose="internal_test",
            channel="system_internal",
            environment=self.environment,
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=1),
            bae_authorization=b2_dec,
        )
        res = gateway.execute(tool_req)
        self.assertEqual(res.status, ResultStatus.SUCCESS)
        self.assertIsNotNone(res.result)

        # Transition B4 states
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Retry tool executed")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Tool accepted by gateway")
        self.sm.transition(ExecutionState.EXECUTED, reason="Tool executed")

        # B5 Verification
        engine = AuthoritativeVerificationEngine()
        access = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment=self.environment,
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="postgres.read.ops_telemetry",
        )
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-KB-RETRY",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name="telemetry_ingested",
            source_identifier="postgres_ops_telemetry_db",
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            observed_state={"retrieved_count": 1},
        )
        evidence = VerificationEvidenceItem(
            evidence_id="EV-KB-RETRY",
            evidence_class=VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH,
            verification_method=VerificationMethod.POSTGRESQL_DIRECT_QUERY,
            source_identifier="postgres_ops_telemetry_db",
            observed_state={"retrieved_count": 1},
            collected_at=utc_now(),
            collector_actor_id="verification_service",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="telemetry_ingested",
            provenance_token=prov,
        )
        ver_req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name="telemetry_ingested",
            expected_state={"retrieved_count": 1},
            evidence_items=(evidence,),
            access_decision=access,
        )
        ver_res = engine.verify(ver_req)
        engine.apply_to_state_machine(self.sm, ver_res)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.VERIFIED)

    def test_b6_29_due_retry_b3_negative_paths_reject_before_provider_invocation(self):
        """Due retry with missing or forged B3 authorization is rejected with zero provider side-effects."""
        from src.budly_runtime.tool_gateway import (
            Actor,
            ActorPermission,
            AuditSink,
            CapabilityDefinition,
            CapabilityRef,
            KnowledgeRetrieveInput,
            LocalKnowledgeAdapter,
            ToolGateway,
            ToolRegistry,
            ToolRequest,
        )
        fixtures = [
            {
                "knowledge_id": "KB-POLICY-001",
                "title": "Return Policy",
                "version": "1.0",
                "domain": "customer_policy",
                "status": "Active",
                "classification": "Public",
                "source_reference": "POLICY-DOC-001",
                "content": "30-day return policy for unopened items.",
            }
        ]
        adapter = LocalKnowledgeAdapter(fixtures)
        cap_def = CapabilityDefinition(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            bros_level=1,
            tool_class="T0",
            enabled=True,
            allowed_environments=frozenset({"automated_test", "development"}),
            allowed_purposes=frozenset({"customer_education", "internal_test"}),
            allowed_channels=frozenset({"website_chat", "system_internal"}),
        )
        registry = ToolRegistry(cap_def, adapter)
        audit = AuditSink()
        permissions = {
            self.actor_type: ActorPermission(
                self.actor_type,
                frozenset({"customer_policy"}),
                frozenset({"Public", "PUBLIC"}),
                frozenset({"customer_education", "internal_test"}),
                frozenset({"system_internal", "website_chat"}),
            )
        }
        gateway = ToolGateway(registry, audit, {self.capability_id: permissions}, policy_evaluator=self.evaluator)

        # 1. Missing authorization
        req_missing = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            actor=Actor(actor_id=self.actor_id, actor_type=self.actor_type),
            capability=CapabilityRef(self.capability_id, self.capability_version),
            purpose="internal_test",
            channel="system_internal",
            environment=self.environment,
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=1),
            bae_authorization=None,  # Missing
        )
        res_missing = gateway.execute(req_missing)
        self.assertEqual(res_missing.status.value, "DENIED")

        # 2. Forged authorization
        forged_auth = AuthorizationDecision(
            status=AuthorizationDecisionStatus.PERMITTED,
            permitted=True,
            requires_approval=False,
            approval_level=None,
            denial_reason=None,
            reason_detail="Forged authorization object",
            step_token=None,
        )
        req_forged = ToolRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            actor=Actor(actor_id=self.actor_id, actor_type=self.actor_type),
            capability=CapabilityRef(self.capability_id, self.capability_version),
            purpose="internal_test",
            channel="system_internal",
            environment=self.environment,
            input=KnowledgeRetrieveInput(query="return policy", domain="customer_policy", max_results=1),
            bae_authorization=forged_auth,  # Forged
        )
        res_forged = gateway.execute(req_forged)
        self.assertEqual(res_forged.status.value, "DENIED")

    def test_b6_30_provider_acknowledgement_after_retry_remains_unverified(self):
        """Provider acknowledgement alone after retry cannot verify execution without B5 SoR proof."""
        decision = self.controller.evaluate_retry(
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            current_attempt_count=1,
            error_reason="NETWORK_TIMEOUT",
            environment=self.environment,
            actor_id=self.actor_id,
        )
        self.controller.apply_retry_scheduling(self.sm, decision)

        # Authorize and execute retry
        prior_token = f"TOKEN-{self.objective_id}-1-TEST"
        self.evaluator._issued_tokens[prior_token] = ContinuousAuthorizationToken(
            token_id=prior_token,
            objective_id=self.objective_id,
            step_number=1,
            capability_id=self.capability_id,
            issued_at=utc_now(),
            expires_at=utc_now(),
            actor_id=self.actor_id,
            environment=self.environment,
            checksum="TOKEN-1",
            material_state_fingerprint="fp1",
        )
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=2,
            prior_step_token=prior_token,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T0,
        )
        authorized, b2_dec = self.controller.authorize_retry_execution(
            sm=self.sm, auth_request=auth_req, evaluator=self.evaluator,
        )
        self.assertTrue(authorized)

        # Advance execution
        self.sm.transition(ExecutionState.ATTEMPTED, reason="Retry executed")
        self.sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Accepted by gateway")
        self.sm.transition(ExecutionState.EXECUTED, reason="Executed by adapter")

        # Provider acknowledgement only -> evaluated by B5 engine
        engine = AuthoritativeVerificationEngine()
        access = VerificationAccessDecision.issue(
            permitted=True,
            reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
            actor_id=self.actor_id,
            actor_type=self.actor_type,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            environment=self.environment,
            allowed_data_scopes=frozenset({"operational_telemetry"}),
            consent_valid=True,
            permission_valid=True,
            verification_route="provider.ack",
        )
        prov = EvidenceProvenanceToken.issue(
            evidence_id="EV-ACK-ONLY",
            objective_id=self.objective_id,
            action_id=self.action_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            postcondition_name="telemetry_ingested",
            source_identifier="provider_api",
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            observed_state={"status": "200_OK"},
        )
        ack_evidence = VerificationEvidenceItem(
            evidence_id="EV-ACK-ONLY",
            evidence_class=VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT,  # Weak class
            verification_method=VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
            source_identifier="provider_api",
            observed_state={"status": "200_OK"},
            collected_at=utc_now(),
            collector_actor_id="provider",
            objective_id=self.objective_id,
            action_id=self.action_id,
            postcondition_name="telemetry_ingested",
            provenance_token=prov,
        )
        ver_req = VerificationRequest(
            verification_id=str(uuid4()),
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            actor_id=self.actor_id,
            postcondition_name="telemetry_ingested",
            expected_state=self.material_payload,
            evidence_items=(ack_evidence,),
            access_decision=access,
        )
        ver_res = engine.verify(ver_req)
        engine.apply_to_state_machine(self.sm, ver_res)

        # Must NOT be VERIFIED
        self.assertNotEqual(self.sm.record.current_execution_state, ExecutionState.VERIFIED)
        self.assertEqual(self.sm.record.current_execution_state, ExecutionState.UNVERIFIED)
        self.assertEqual(self.sm.record.verification_state, VerificationState.UNVERIFIED)

    def test_b6_31_deterministic_duplicate_test_for_prior_unverified(self):
        """Duplicate idempotency key after UNVERIFIED preserves evidence without inferred success or blind replay."""
        # Record initial UNVERIFIED attempt
        rec = self.idempotency_store.record_first_use(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
            initial_state=ExecutionState.UNVERIFIED,
        )
        self.assertFalse(rec.is_verified_success)
        self.assertEqual(rec.latest_execution_state, ExecutionState.UNVERIFIED)

        # Duplicate evaluation
        disp, retrieved_rec, reason = self.controller.evaluate_idempotency(
            idempotency_key=self.idempotency_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id=self.capability_id,
            capability_version=self.capability_version,
            environment=self.environment,
            material_payload=self.material_payload,
        )
        self.assertEqual(disp, IdempotencyDisposition.DUPLICATE_UNCERTAIN_PRESERVED)
        self.assertFalse(retrieved_rec.is_verified_success)
        self.assertIn("UNVERIFIED", reason)


if __name__ == "__main__":
    unittest.main()
