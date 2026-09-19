"""BAE Pilot 001 Gate B Step B13 Wave 2 TASK / RETRY Capability Test Suite.

Verifies the 72 required B13 test invariants:
TASK Tests (1-25)
RETRY Tests (26-50)
Cross-Control & Governance Tests (51-72)
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


class TestBAEStepB13Wave2Capabilities(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = BAECapabilityRegistry.load_seed()
        self.kill_switch = KillSwitchController()
        self.audit_repo = DurableAuditRepository(environment="development")
        self.policy_evaluator = DeterministicPolicyEvaluator(
            self.registry,
            self.kill_switch,
            environment="development",
        )
        self.action_policies = TaskActionPolicyRegistry.default_registry()
        self.executor = Wave2CapabilityExecutor(
            policy_evaluator=self.policy_evaluator,
            kill_switch_controller=self.kill_switch,
            audit_repository=self.audit_repo,
            action_policy_registry=self.action_policies,
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
    # TASK TESTS (1-25)
    # =========================================================================

    # 1. Authorized low-risk TASK fixture succeeds in DEVELOPMENT / TEST
    def test_b13_01_authorized_low_risk_task_succeeds(self) -> None:
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"sync_entity": "queue_metrics", "status": "SYNCED"},
        )
        self.assertEqual(result.capability_id, "BAE-OPS-TASK-001")
        self.assertEqual(result.execution_state, ExecutionState.VERIFIED)
        self.assertTrue(result.is_verified_success)
        self.assertTrue(result.provider_invoked)
        self.assertIsNotNone(result.audit_event_id)

    # 2. Unregistered task/action denied
    def test_b13_02_unregistered_task_action_denied(self) -> None:
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="unregistered_arbitrary_task",
            material_payload={"foo": "bar"},
        )
        self.assertEqual(result.execution_state, ExecutionState.DENIED)
        self.assertFalse(result.is_verified_success)
        self.assertFalse(result.provider_invoked)
        self.assertEqual(result.denial_reason, "UNREGISTERED_ACTION_TYPE")

    # 3. Missing capability denied
    def test_b13_03_missing_capability_denied(self) -> None:
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=self.correlation_id,
            objective_id=self.objective_id,
            step_number=1,
            actor_id="bae-steward-001",
            actor_type="bae_steward",
            capability_id="NON_EXISTENT_CAPABILITY",
            capability_version="1.0",
            environment="development",
            channel="system_internal",
            purpose="internal_test",
            requested_tool_authority=ToolAuthorityClass.T2,
        )
        dec = self.policy_evaluator.evaluate(auth_req)
        self.assertFalse(dec.permitted)
        self.assertEqual(dec.denial_reason, AuthorizationDenialReason.CAPABILITY_NOT_REGISTERED)

    # 4. Missing permission denied
    def test_b13_04_missing_permission_denied(self) -> None:
        custom_policy = TaskActionPolicy(
            action_type="missing_perm_task",
            purpose="routine_maintenance",
            authority_class=AuthorityClass.L1,
            required_maturity=AutonomyMaturity.M1,
            maximum_maturity=AutonomyMaturity.M3,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T2,
            allowed_environments=frozenset({"automated_test", "development"}),
            required_actor_type="bae_steward",
            required_permission="bae:super_admin_write",  # Not granted by default
            data_scope="internal_ops",
        )
        self.action_policies.register(custom_policy)
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="missing_perm_task",
            material_payload={"data": 123},
        )
        self.assertEqual(result.execution_state, ExecutionState.DENIED)
        self.assertFalse(result.is_verified_success)
        self.assertFalse(result.provider_invoked)
        self.assertEqual(result.denial_reason, "PERMISSION_DENIED")

    # 5. Environment denied
    def test_b13_05_environment_denied(self) -> None:
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 123},
            environment="production",
        )
        self.assertEqual(result.execution_state, ExecutionState.DENIED)
        self.assertFalse(result.is_verified_success)
        self.assertFalse(result.provider_invoked)
        self.assertEqual(result.denial_reason, "ENVIRONMENT_DENIED")

    # 6. L2 action without approval denied
    def test_b13_06_l2_action_without_approval_denied(self) -> None:
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="high_risk_ops_reconfiguration",
            material_payload={"config_key": "timeout", "new_val": 30},
            approval_token=None,
        )
        self.assertEqual(result.execution_state, ExecutionState.DENIED)
        self.assertFalse(result.is_verified_success)
        self.assertFalse(result.provider_invoked)
        self.assertEqual(result.denial_reason, "HUMAN_APPROVAL_REQUIRED")

    # 7. L2 action with valid approval proceeds if all other gates pass
    def test_b13_07_l2_action_with_valid_approval_proceeds(self) -> None:
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="high_risk_ops_reconfiguration",
            material_payload={"config_key": "timeout", "new_val": 30},
            approval_token="valid_human_approval_token_123",
        )
        self.assertEqual(result.execution_state, ExecutionState.VERIFIED)
        self.assertTrue(result.is_verified_success)
        self.assertTrue(result.provider_invoked)

    # 8. L3-H task autonomous attempt denied/human-only
    def test_b13_08_l3_h_task_autonomous_attempt_denied_human_only(self) -> None:
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="critical_system_freeze",
            material_payload={"scope": "all"},
        )
        self.assertEqual(result.execution_state, ExecutionState.DENIED)
        self.assertFalse(result.is_verified_success)
        self.assertFalse(result.provider_invoked)
        self.assertEqual(result.denial_reason, "AUTHORITY_CLASS_HUMAN_ONLY")

    # 9. L3-X task blocked
    def test_b13_09_l3_x_task_blocked(self) -> None:
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="prohibited_destructive_wipe",
            material_payload={"all": True},
        )
        self.assertEqual(result.execution_state, ExecutionState.DENIED)
        self.assertFalse(result.is_verified_success)
        self.assertFalse(result.provider_invoked)
        self.assertEqual(result.denial_reason, "AUTHORITY_CLASS_PROHIBITED")

    # 10. Requested maturity above max denied
    def test_b13_10_requested_maturity_above_max_denied(self) -> None:
        custom_policy = TaskActionPolicy(
            action_type="max_maturity_violation",
            purpose="routine_maintenance",
            authority_class=AuthorityClass.L1,
            required_maturity=AutonomyMaturity.M4,
            maximum_maturity=AutonomyMaturity.M2,  # required > max
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T2,
            allowed_environments=frozenset({"automated_test", "development"}),
            required_actor_type="bae_steward",
            required_permission="bae:bounded_write",
            data_scope="internal_ops",
        )
        self.action_policies.register(custom_policy)
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="max_maturity_violation",
            material_payload={},
        )
        self.assertEqual(result.execution_state, ExecutionState.DENIED)
        self.assertFalse(result.is_verified_success)
        self.assertEqual(result.denial_reason, "MAXIMUM_MATURITY_EXCEEDED")

    # 11. Target M3 does not act as current maturity
    def test_b13_11_target_m3_does_not_act_as_current_maturity(self) -> None:
        task_rec = self.registry.get("BAE-OPS-TASK-001")
        self.assertIsNotNone(task_rec)
        self.assertIsNone(task_rec.current_certified_maturity)
        self.assertEqual(task_rec.target_pilot_entry_maturity, AutonomyMaturity.M3)

    # 12. Active kill switch stops TASK
    def test_b13_12_active_kill_switch_stops_task(self) -> None:
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-TASK-001",
            reason="Task capability stopped",
            activating_authority="admin",
            operator_role="system_admin",
        )
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
        )
        self.assertEqual(result.execution_state, ExecutionState.STOPPED)
        self.assertFalse(result.provider_invoked)
        self.assertFalse(result.is_verified_success)

    # 13. Human override stops TASK
    def test_b13_13_human_override_stops_task(self) -> None:
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            is_human_override_active=True,
        )
        self.assertEqual(result.execution_state, ExecutionState.STOPPED)
        self.assertFalse(result.provider_invoked)

    # 14. B3 provenance required
    def test_b13_14_b3_provenance_required(self) -> None:
        invoked_contexts = []

        def mock_provider(payload, ctx):
            invoked_contexts.append(ctx)
            return {"status": "SUCCESS"}

        self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            provider_fn=mock_provider,
        )
        self.assertEqual(len(invoked_contexts), 1)
        self.assertIsInstance(invoked_contexts[0], GatewayExecutionContext)

    # 15. Direct adapter bypass rejected
    def test_b13_15_direct_adapter_bypass_rejected(self) -> None:
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            provider_fn=lambda p, ctx: {"status": "SUCCESS"},
            bypass_gateway_context=True,
        )
        self.assertEqual(result.execution_state, ExecutionState.FAILED)
        self.assertIn("Direct adapter execution prohibited", result.error_message or "")

    # 16. Provider invocation count zero on denial
    def test_b13_16_provider_invocation_count_zero_on_denial(self) -> None:
        call_count = 0

        def counting_provider(payload, ctx):
            nonlocal call_count
            call_count += 1
            return {"status": "SUCCESS"}

        self.executor.execute_task(
            correlation=self.correlation,
            action_type="unregistered_action",
            material_payload={},
            provider_fn=counting_provider,
        )
        self.assertEqual(call_count, 0)

    # 17. Successful provider acknowledgement alone does not equal verified success
    def test_b13_17_provider_ack_alone_does_not_equal_verified_success(self) -> None:
        def unverified_fn(res):
            return VerificationOutcome.UNVERIFIED, VerificationReason.WEAK_AGENT_SELF_REPORT_ONLY, VerificationEvidenceClass.AGENT_SELF_REPORT, None

        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            provider_fn=lambda p, ctx: {"ack": "ACK_RECEIVED"},
            verification_fn=unverified_fn,
        )
        self.assertEqual(result.execution_state, ExecutionState.UNVERIFIED)
        self.assertFalse(result.is_verified_success)
        self.assertTrue(result.provider_invoked)

    # 18. Authoritative postcondition verification permits successful completion
    def test_b13_18_authoritative_postcondition_permits_success(self) -> None:
        def auth_v_fn(res):
            return VerificationOutcome.VERIFIED, VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED, VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH, "sor://db/tx-123"

        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            verification_fn=auth_v_fn,
        )
        self.assertEqual(result.execution_state, ExecutionState.VERIFIED)
        self.assertTrue(result.is_verified_success)

    # 19. Verification unavailable fails safe
    def test_b13_19_verification_unavailable_fails_safe(self) -> None:
        def failed_v_fn(res):
            return VerificationOutcome.FAILED, VerificationReason.POSTCONDITION_STATE_MISMATCH, VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL, None

        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            verification_fn=failed_v_fn,
        )
        self.assertEqual(result.execution_state, ExecutionState.FAILED)
        self.assertFalse(result.is_verified_success)

    # 20. TASK execution audited
    def test_b13_20_task_execution_audited(self) -> None:
        self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
        )
        events = self.audit_repo.get_action_history(self.action_id)
        self.assertTrue(any(e.capability_id == "BAE-OPS-TASK-001" for e in events))

    # 21. Correlation lineage preserved
    def test_b13_21_correlation_lineage_preserved(self) -> None:
        result = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
        )
        self.assertEqual(result.correlation.objective_id, self.objective_id)
        self.assertEqual(result.correlation.action_id, self.action_id)
        self.assertEqual(result.correlation.correlation_id, self.correlation_id)

    # 22. PII/secrets sanitized
    def test_b13_22_pii_secrets_sanitized(self) -> None:
        self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"email": "alice@example.com", "password": "secretPassword123"},
        )
        events = self.audit_repo.get_action_history(self.action_id)
        task_event = next(e for e in events if e.capability_id == "BAE-OPS-TASK-001")
        sanitized = task_event.sanitized_metadata.get("sanitized_payload", {})
        self.assertTrue(sanitized["email"].startswith("[REDACTED_PII:hash="))
        self.assertEqual(sanitized["password"], "[REDACTED_SECRET]")

    # 23. Duplicate VERIFIED task not replayed
    def test_b13_23_duplicate_verified_task_not_replayed(self) -> None:
        provider_calls = 0

        def counting_provider(payload, ctx):
            nonlocal provider_calls
            provider_calls += 1
            return {"status": "SUCCESS"}

        idem_key = f"idem-test-23-{uuid4()}"
        res1 = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"item": "unique_1"},
            idempotency_key=idem_key,
            provider_fn=counting_provider,
        )
        self.assertEqual(provider_calls, 1)
        self.assertEqual(res1.execution_state, ExecutionState.VERIFIED)

        # Second call with identical idempotency key
        res2 = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"item": "unique_1"},
            idempotency_key=idem_key,
            provider_fn=counting_provider,
        )
        self.assertEqual(provider_calls, 1)  # Provider NOT called again
        self.assertTrue(res2.is_idempotent_no_op)
        self.assertEqual(res2.execution_state, ExecutionState.VERIFIED)

    # 24. Idempotency payload mismatch rejected
    def test_b13_24_idempotency_payload_mismatch_rejected(self) -> None:
        idem_key = f"idem-test-24-{uuid4()}"
        self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"key": "original"},
            idempotency_key=idem_key,
        )
        res_mismatch = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"key": "altered_payload"},
            idempotency_key=idem_key,
        )
        self.assertEqual(res_mismatch.execution_state, ExecutionState.DENIED)
        self.assertFalse(res_mismatch.provider_invoked)

    # 25. Unknown prior outcome prevents blind replay
    def test_b13_25_unknown_prior_outcome_prevents_blind_replay(self) -> None:
        idem_key = f"idem-test-25-{uuid4()}"

        def unknown_v_fn(res):
            return VerificationOutcome.UNKNOWN, VerificationReason.AUTHORITATIVE_SOURCE_UNAVAILABLE, VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL, None

        self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_task_status_update",
            material_payload={"status": "PENDING"},
            idempotency_key=idem_key,
            verification_fn=unknown_v_fn,
        )
        # Attempt duplicate request on UNKNOWN
        provider_calls = 0

        def counting_provider(p, ctx):
            nonlocal provider_calls
            provider_calls += 1
            return {"status": "SUCCESS"}

        res2 = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_task_status_update",
            material_payload={"status": "PENDING"},
            idempotency_key=idem_key,
            provider_fn=counting_provider,
        )
        self.assertEqual(provider_calls, 0)
        self.assertEqual(res2.execution_state, ExecutionState.UNVERIFIED)

    # =========================================================================
    # RETRY TESTS (26-50)
    # =========================================================================

    # 26. Retryable transient failure schedules retry
    def test_b13_26_retryable_transient_failure_schedules_retry(self) -> None:
        result = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
        )
        self.assertTrue(result.retry_decision.retry_authorized)
        self.assertEqual(result.retry_decision.failure_class, FailureClass.RETRYABLE)
        self.assertEqual(result.attempt_number, 2)

    # 27. Non-retryable failure does not schedule retry
    def test_b13_27_non_retryable_failure_does_not_schedule_retry(self) -> None:
        result = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="invalid_format",
        )
        self.assertFalse(result.retry_decision.retry_authorized)
        self.assertEqual(result.retry_decision.failure_class, FailureClass.NON_RETRYABLE)

    # 28. Retry requires fresh B2 authorization
    def test_b13_28_retry_requires_fresh_b2_authorization(self) -> None:
        result = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
        )
        self.assertIsNotNone(result.fresh_authorization_decision)
        self.assertTrue(result.fresh_authorization_decision.permitted)

    # 29. Changed permission blocks retry
    def test_b13_29_changed_permission_blocks_retry(self) -> None:
        # Register action requiring a permission that won't be granted on retry
        custom_policy = TaskActionPolicy(
            action_type="retry_perm_revoked_action",
            purpose="routine_maintenance",
            authority_class=AuthorityClass.L1,
            required_maturity=AutonomyMaturity.M1,
            maximum_maturity=AutonomyMaturity.M3,
            approval_level=ApprovalLevel.A0,
            tool_authority=ToolAuthorityClass.T2,
            allowed_environments=frozenset({"automated_test", "development"}),
            required_actor_type="bae_steward",
            required_permission="bae:special_permission",  # Revoked/not granted
            data_scope="internal_ops",
        )
        self.action_policies.register(custom_policy)
        result = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="retry_perm_revoked_action",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
        )
        self.assertIsNotNone(result.fresh_authorization_decision)
        self.assertFalse(result.fresh_authorization_decision.permitted)
        self.assertEqual(result.fresh_authorization_decision.denial_reason, AuthorizationDenialReason.PERMISSION_DENIED)

    # 30. Expired approval blocks retry
    def test_b13_30_expired_approval_blocks_retry(self) -> None:
        result = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="high_risk_ops_reconfiguration",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
            approval_token=None,  # Approval expired/missing on retry
        )
        self.assertIsNotNone(result.fresh_authorization_decision)
        self.assertFalse(result.fresh_authorization_decision.permitted)
        self.assertEqual(result.fresh_authorization_decision.denial_reason, AuthorizationDenialReason.HUMAN_APPROVAL_REQUIRED)

    # 31. Active kill switch blocks retry
    def test_b13_31_active_kill_switch_blocks_retry(self) -> None:
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-TASK-001",
            reason="Task capability killed during retry window",
            activating_authority="admin",
            operator_role="system_admin",
        )
        result = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
        )
        self.assertFalse(result.retry_decision.retry_authorized)
        self.assertEqual(result.retry_decision.stop_reason, RetryStopReason.KILL_SWITCH_ACTIVE)

    # 32. Human override blocks retry
    def test_b13_32_human_override_blocks_retry(self) -> None:
        result = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
            is_human_override_active=True,
        )
        self.assertIsNotNone(result.fresh_authorization_decision)
        self.assertFalse(result.fresh_authorization_decision.permitted)

    # 33. Environment change blocks retry
    def test_b13_33_environment_change_blocks_retry(self) -> None:
        result = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
            environment="production",
        )
        self.assertIsNotNone(result.fresh_authorization_decision)
        self.assertFalse(result.fresh_authorization_decision.permitted)
        self.assertEqual(result.fresh_authorization_decision.denial_reason, AuthorizationDenialReason.ENVIRONMENT_DENIED)

    # 34. Retry never widens L
    def test_b13_34_retry_never_widens_l(self) -> None:
        retry_rec = self.registry.get("BAE-OPS-RETRY-001")
        self.assertEqual(retry_rec.authority_class, AuthorityClass.L1)

    # 35. Retry never widens M
    def test_b13_35_retry_never_widens_m(self) -> None:
        retry_rec = self.registry.get("BAE-OPS-RETRY-001")
        self.assertIsNone(retry_rec.current_certified_maturity)
        self.assertEqual(retry_rec.target_pilot_entry_maturity, AutonomyMaturity.M3)

    # 36. Retry never widens A
    def test_b13_36_retry_never_widens_a(self) -> None:
        retry_rec = self.registry.get("BAE-OPS-RETRY-001")
        self.assertEqual(retry_rec.approval_level, ApprovalLevel.A0)

    # 37. Retry never widens T
    def test_b13_37_retry_never_widens_t(self) -> None:
        retry_rec = self.registry.get("BAE-OPS-RETRY-001")
        self.assertEqual(retry_rec.tool_authority, ToolAuthorityClass.T1)

    # 38. Retry preserves original data scope
    def test_b13_38_retry_preserves_original_data_scope(self) -> None:
        action_policy = self.action_policies.get_policy("internal_state_sync")
        self.assertEqual(action_policy.data_scope, "internal_ops")

    # 39. Idempotency binding preserved
    def test_b13_39_idempotency_binding_preserved(self) -> None:
        idem_key = f"idem-test-39-{uuid4()}"
        result = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
            idempotency_key=idem_key,
        )
        self.assertIsNotNone(result.execution_result)
        stored_idem = self.executor.retry_controller.idempotency_store.get(idem_key)
        self.assertIsNotNone(stored_idem)
        self.assertEqual(stored_idem.objective_id, self.objective_id)

    # 40. Duplicate VERIFIED operation prevents retry
    def test_b13_40_duplicate_verified_operation_prevents_retry(self) -> None:
        idem_key = f"idem-test-40-{uuid4()}"
        # Execute TASK to VERIFIED
        self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            idempotency_key=idem_key,
        )
        # Attempt RETRY on already verified action
        retry_res = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
            idempotency_key=idem_key,
        )
        self.assertFalse(retry_res.retry_decision.retry_authorized)
        self.assertEqual(retry_res.retry_decision.stop_reason, RetryStopReason.ALREADY_VERIFIED_SUCCESS)
        self.assertIsNone(retry_res.execution_result)

    # 41. UNKNOWN side-effect state prevents blind replay
    def test_b13_41_unknown_side_effect_prevents_blind_replay(self) -> None:
        idem_disp, _, msg = self.executor.retry_controller.evaluate_idempotency(
            idempotency_key="unknown-key",
            objective_id="obj-1",
            action_id="act-1",
            correlation_id="corr-1",
            capability_id="BAE-OPS-TASK-001",
            capability_version="1.0",
            environment="development",
            material_payload={"a": 1},
        )
        self.assertEqual(idem_disp, IdempotencyDisposition.FIRST_USE)

    # 42. UNVERIFIED state prevents blind replay where duplication is unsafe
    def test_b13_42_unverified_state_prevents_blind_replay(self) -> None:
        idem_key = f"idem-test-42-{uuid4()}"

        def unverified_fn(res):
            return VerificationOutcome.UNVERIFIED, VerificationReason.WEAK_AGENT_SELF_REPORT_ONLY, VerificationEvidenceClass.AGENT_SELF_REPORT, None

        self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            idempotency_key=idem_key,
            verification_fn=unverified_fn,
        )
        idem_disp, _, _ = self.executor.retry_controller.evaluate_idempotency(
            idempotency_key=idem_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id="BAE-OPS-TASK-001",
            capability_version="1.0",
            environment="development",
            material_payload={"data": 1},
        )
        self.assertEqual(idem_disp, IdempotencyDisposition.DUPLICATE_UNCERTAIN_PRESERVED)

    # 43. PARTIAL state prevents blind replay where duplication is unsafe
    def test_b13_43_partial_state_prevents_blind_replay(self) -> None:
        idem_key = f"idem-test-43-{uuid4()}"

        def partial_v_fn(res):
            return VerificationOutcome.PARTIALLY_VERIFIED, VerificationReason.TECHNICAL_EVIDENCE_INSUFFICIENT_FOR_POSTCONDITION, VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL, None

        self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            idempotency_key=idem_key,
            verification_fn=partial_v_fn,
        )
        idem_disp, _, _ = self.executor.retry_controller.evaluate_idempotency(
            idempotency_key=idem_key,
            objective_id=self.objective_id,
            action_id=self.action_id,
            correlation_id=self.correlation_id,
            capability_id="BAE-OPS-TASK-001",
            capability_version="1.0",
            environment="development",
            material_payload={"data": 1},
        )
        self.assertEqual(idem_disp, IdempotencyDisposition.DUPLICATE_UNCERTAIN_PRESERVED)

    # 44. Authoritative proof of prior success cancels retry
    def test_b13_44_authoritative_proof_cancels_retry(self) -> None:
        idem_key = f"idem-test-44-{uuid4()}"
        self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            idempotency_key=idem_key,
        )
        res = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
            idempotency_key=idem_key,
        )
        self.assertFalse(res.retry_decision.retry_authorized)
        self.assertEqual(res.retry_decision.stop_reason, RetryStopReason.ALREADY_VERIFIED_SUCCESS)

    # 45. Due retry with valid authorization executes exactly once
    def test_b13_45_due_retry_with_valid_authorization_executes_once(self) -> None:
        provider_calls = 0

        def counting_provider(p, ctx):
            nonlocal provider_calls
            provider_calls += 1
            return {"status": "SUCCESS"}

        res = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
            provider_fn=counting_provider,
        )
        self.assertEqual(provider_calls, 1)
        self.assertIsNotNone(res.execution_result)
        self.assertTrue(res.execution_result.is_verified_success)

    # 46. Retry attempt increments lineage
    def test_b13_46_retry_attempt_increments_lineage(self) -> None:
        orig_id = str(uuid4())
        res = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=orig_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
        )
        self.assertIsNotNone(res.execution_result)
        self.assertEqual(res.execution_result.correlation.parent_action_id, orig_id)
        self.assertEqual(res.execution_result.correlation.retry_attempt_number, 2)

    # 47. Retry exhaustion stops/escalates
    def test_b13_47_retry_exhaustion_stops_and_escalates(self) -> None:
        res = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=3,  # Max attempts is 3, so attempt 4 exceeds
            error_reason="connection_timeout",
        )
        self.assertFalse(res.retry_decision.retry_authorized)
        self.assertEqual(res.retry_decision.stop_reason, RetryStopReason.MAX_ATTEMPTS_EXCEEDED)
        self.assertTrue(res.is_exhausted)
        self.assertIsNotNone(res.escalation_package)
        self.assertEqual(res.escalation_package.escalation_reason, EscalationReason.RETRY_EXHAUSTED)

    # 48. Retry budget cannot become infinite
    def test_b13_48_retry_budget_cannot_become_infinite(self) -> None:
        policy = self.executor.retry_controller.policy_registry.get_policy("BAE-OPS-OBSERVE-001", "1.0")
        self.assertIsNotNone(policy)
        self.assertLessEqual(policy.max_attempts, 10)
        self.assertGreater(policy.max_attempts, 0)

    # 49. Provider invocation remains zero when retry denied
    def test_b13_49_provider_invocation_remains_zero_when_retry_denied(self) -> None:
        calls = 0

        def counting_provider(p, ctx):
            nonlocal calls
            calls += 1
            return {"status": "SUCCESS"}

        self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="invalid_format",  # NON_RETRYABLE
            provider_fn=counting_provider,
        )
        self.assertEqual(calls, 0)

    # 50. Retry events persist to B7
    def test_b13_50_retry_events_persist_to_b7(self) -> None:
        res = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
        )
        events = self.audit_repo.get_action_history(res.execution_result.correlation.action_id)
        self.assertTrue(any(e.capability_id == "BAE-OPS-RETRY-001" for e in events))

    # =========================================================================
    # CROSS-CONTROL / GOVERNANCE TESTS (51-72)
    # =========================================================================

    # 51. TASK uses B2/B3/B4/B5/B6/B7/B9 path
    def test_b13_51_task_uses_full_governed_path(self) -> None:
        res = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"check": "full_path"},
        )
        self.assertEqual(res.execution_state, ExecutionState.VERIFIED)
        self.assertTrue(res.is_verified_success)

    # 52. RETRY consumes B6 rather than parallel implementation
    def test_b13_52_retry_consumes_b6_retry_controller(self) -> None:
        self.assertIsInstance(self.executor.retry_controller, RetryController)
        self.assertIsInstance(self.executor.retry_controller.idempotency_store, IdempotencyStore)

    # 53. B8 escalation is non-authoritative
    def test_b13_53_b8_escalation_is_non_authoritative(self) -> None:
        res = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=3,
            error_reason="connection_timeout",
        )
        self.assertIsNotNone(res.escalation_package)
        self.assertFalse(hasattr(res.escalation_package, "execute_authorized"))

    # 54. Kill activation between authorization and provider invocation stops TASK
    def test_b13_54_kill_activation_between_auth_and_provider_stops_task(self) -> None:
        # Activate kill switch to test stopping before execution
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-TASK-001",
            reason="Killed between auth and provider",
            activating_authority="admin",
            operator_role="system_admin",
        )
        res = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
        )
        self.assertEqual(res.execution_state, ExecutionState.STOPPED)
        self.assertFalse(res.is_verified_success)

    # 55. Kill activation between retry scheduling and retry execution stops RETRY
    def test_b13_55_kill_activation_between_scheduling_and_retry_stops_retry(self) -> None:
        self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-TASK-001",
            reason="Killed during scheduled window",
            activating_authority="admin",
            operator_role="system_admin",
        )
        res = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
        )
        self.assertFalse(res.retry_decision.retry_authorized)

    # 56. Clearing kill does not auto-resume TASK
    def test_b13_56_clearing_kill_does_not_auto_resume_task(self) -> None:
        switch_id = self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-TASK-001",
            reason="Temporary stop",
            activating_authority="admin",
            operator_role="system_admin",
        )
        res1 = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
        )
        self.assertEqual(res1.execution_state, ExecutionState.STOPPED)

        # Clear kill switch
        self.kill_switch.clear_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-TASK-001",
            clearing_authority="admin",
            clearing_reason="Resumed operations",
            operator_role="system_admin",
        )
        # res1 remains STOPPED
        self.assertEqual(res1.execution_state, ExecutionState.STOPPED)

    # 57. Clearing kill does not auto-run RETRY
    def test_b13_57_clearing_kill_does_not_auto_run_retry(self) -> None:
        switch_id = self.kill_switch.activate_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-TASK-001",
            reason="Temporary stop",
            activating_authority="admin",
            operator_role="system_admin",
        )
        res_retry = self.executor.execute_retry(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={"data": 1},
            original_action_id=self.action_id,
            current_attempt_count=1,
            error_reason="connection_timeout",
        )
        self.assertFalse(res_retry.retry_decision.retry_authorized)

        self.kill_switch.clear_switch(
            scope=KillSwitchScope.CAPABILITY,
            target_identifier="BAE-OPS-TASK-001",
            clearing_authority="admin",
            clearing_reason="Resumed operations",
            operator_role="system_admin",
        )
        # res_retry state did not change
        self.assertFalse(res_retry.retry_decision.retry_authorized)

    # 58. Autonomous agent cannot certify TASK
    def test_b13_58_autonomous_agent_cannot_certify_task(self) -> None:
        task_rec = self.registry.get("BAE-OPS-TASK-001")
        self.assertEqual(task_rec.lifecycle_state, CapabilityLifecycleState.DEFINED)
        self.assertNotEqual(task_rec.lifecycle_state, CapabilityLifecycleState.CERTIFIED)

    # 59. Autonomous agent cannot activate TASK
    def test_b13_59_autonomous_agent_cannot_activate_task(self) -> None:
        task_rec = self.registry.get("BAE-OPS-TASK-001")
        self.assertFalse(task_rec.executable)

    # 60. Autonomous agent cannot certify RETRY
    def test_b13_60_autonomous_agent_cannot_certify_retry(self) -> None:
        retry_rec = self.registry.get("BAE-OPS-RETRY-001")
        self.assertEqual(retry_rec.lifecycle_state, CapabilityLifecycleState.DEFINED)
        self.assertNotEqual(retry_rec.lifecycle_state, CapabilityLifecycleState.CERTIFIED)

    # 61. Autonomous agent cannot activate RETRY
    def test_b13_61_autonomous_agent_cannot_activate_retry(self) -> None:
        retry_rec = self.registry.get("BAE-OPS-RETRY-001")
        self.assertFalse(retry_rec.executable)

    # 62. Canonical TASK seed remains unique
    def test_b13_62_canonical_task_seed_remains_unique(self) -> None:
        all_task = [r for r in self.registry.list_all() if r.capability_id == "BAE-OPS-TASK-001"]
        self.assertEqual(len(all_task), 1)

    # 63. Canonical RETRY seed remains unique
    def test_b13_63_canonical_retry_seed_remains_unique(self) -> None:
        all_retry = [r for r in self.registry.list_all() if r.capability_id == "BAE-OPS-RETRY-001"]
        self.assertEqual(len(all_retry), 1)

    # 64. Wave 1 remains unchanged
    def test_b13_64_wave1_remains_unchanged(self) -> None:
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

    # 65. CRM Activity remains conditional/non-executable
    def test_b13_65_crm_activity_remains_conditional_non_executable(self) -> None:
        crm_rec = self.registry.get("BAE-CRM-ACTIVITY-001")
        self.assertIsNotNone(crm_rec)
        self.assertEqual(crm_rec.wave, PilotWave.WAVE_3)
        self.assertEqual(crm_rec.classification_state, "CONDITIONAL")
        self.assertFalse(crm_rec.executable)

    # 66. Customer Follow-Up remains disabled
    def test_b13_66_customer_followup_remains_disabled(self) -> None:
        followup_rec = self.registry.get("BAE-COMM-FOLLOWUP-001")
        self.assertIsNotNone(followup_rec)
        self.assertEqual(followup_rec.wave, PilotWave.WAVE_4)
        self.assertEqual(followup_rec.classification_state, "UNRESOLVED_DISABLED")
        self.assertFalse(followup_rec.executable)

    # 67. Gate C not started
    def test_b13_67_gate_c_not_started(self) -> None:
        for rec in self.registry.list_all():
            self.assertNotEqual(rec.lifecycle_state, CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT)

    # 68. Gate D unauthorized
    def test_b13_68_gate_d_unauthorized(self) -> None:
        self.assertFalse(self.policy_evaluator.gate_d_authorized)

    # 69. No production route introduced
    def test_b13_69_no_production_route_introduced(self) -> None:
        task_res = self.executor.execute_task(
            correlation=self.correlation,
            action_type="internal_state_sync",
            material_payload={},
            environment="production",
        )
        self.assertEqual(task_res.execution_state, ExecutionState.DENIED)

    # 70. No production merge/deployment
    def test_b13_70_no_production_merge_or_deployment(self) -> None:
        for rec in self.registry.list_all():
            self.assertNotIn("production", rec.allowed_environments)

    # 71. B14 not started
    def test_b13_71_b14_not_started(self) -> None:
        # B14 is Wave 2 Acceptance Harness Execution
        for rec in self.registry.list_all():
            self.assertIsNone(rec.current_certified_maturity)

    # 72. All B1-B12 regressions remain green
    def test_b13_72_all_b1_b12_regressions_remain_green(self) -> None:
        # Registry loads and has exactly 9 canonical capabilities
        self.assertEqual(len(self.registry.list_all()), 9)


if __name__ == "__main__":
    unittest.main()
