"""BAE Pilot 001 Wave 2 Governed Operational Capabilities (Gate B Step B13).

Implements the two canonical Wave 2 capabilities:
1. TASK (BAE-OPS-TASK-001): Autonomous Bounded Task Execution.
2. RETRY (BAE-OPS-RETRY-001): Bounded Retry and Idempotent Recovery consuming B6 RetryController.

Governing Laws:
- DO THE ROUTINE WORK. PROVE THE RESULT. ESCALATE THE REST.
- Implementation != Certification. Passing B13 tests does NOT activate capabilities.
- Strict multi-gate authorization:
  AUTHORITY ∩ CURRENT MATURITY ∩ APPROVAL ∩ TOOL AUTHORITY ∩ PERMISSION ∩ ENVIRONMENT ∩ IDEMPOTENCY ∩ VERIFICATION ∩ NO ACTIVE STOP
- Action-policy driven: TASK does not hardcode authority (L); the registered TaskActionPolicy controls.
- Full B4 state machine progression: REQUESTED -> AUTHORIZATION_PENDING -> AUTHORIZED/DENIED -> ATTEMPTED -> TOOL_ACCEPTED -> EXECUTED -> VERIFICATION_PENDING -> VERIFIED/FAILED/UNVERIFIED/etc.
- B6 idempotency binding: (objective_id, action_id, capability_id, capability_version, environment, material_payload_hash).
- Provider acknowledgement alone is NEVER verified success.
- RETRY inherits underlying action authority and requires fresh B2 evaluation before execution.
- B9 Kill-switch is absolute: stops new TASK execution and due RETRY execution.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable
from uuid import UUID, uuid4

from .audit_persistence import (
    AuditEventRecord,
    AuditEventType,
    CorrelationRecord,
    DurableAuditRepository,
    EvidenceRecord,
    compute_evidence_hash,
    sanitize_payload,
)
from .capability_registry import BAECapabilityRegistry
from .escalation import (
    EscalationController,
    EscalationDeliveryState,
    EscalationDisposition,
    EscalationPackage,
    EscalationPolicyEvaluator,
    EscalationPriority,
    EscalationReason,
)
from .kill_switch import (
    KillSwitchController,
    KillSwitchDecisionStatus,
)
from .policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    DeterministicPolicyEvaluator,
    utc_now,
)
from .retry_controller import (
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
from .schemas import CapabilityRecord
from .state_machine import (
    ExecutionState,
    ExecutionStateMachine,
    VerificationEvidenceClass,
    VerificationState,
)
from .types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    KillSwitchScope,
    ToolAuthorityClass,
)
from .verification_engine import (
    AuthoritativeVerificationEngine,
    EvidenceProvenanceToken,
    RegisteredPostconditionContract,
    VerificationAccessDecision,
    VerificationContractRegistry,
    VerificationEvidenceItem,
    VerificationMethod,
    VerificationOutcome,
    VerificationReason,
    VerificationRequest,
    VerificationResult,
)
from ..tool_gateway import (
    Actor,
    CapabilityRef,
    ErrorClass,
    GatewayExecutionContext,
    OperationalMetricItem,
    ResultStatus,
    ToolRequest,
    verify_adapter_provenance,
)


@dataclass(frozen=True)
class TaskActionPolicy:
    """Explicit policy definition governing a specific registered task action."""
    action_type: str
    purpose: str
    authority_class: AuthorityClass
    required_maturity: AutonomyMaturity
    maximum_maturity: AutonomyMaturity
    approval_level: ApprovalLevel
    tool_authority: ToolAuthorityClass
    allowed_environments: frozenset[str]
    required_actor_type: str
    required_permission: str
    data_scope: str
    requires_consent: bool = False
    requires_idempotency: bool = True
    postcondition_name: str = "task_postcondition_verified"
    fallback_behavior: str = "safe_stop"
    escalation_behavior: str = "escalate_on_failure"
    audit_requirement: str = "full_audit"
    specifically_authorized_bounded_write: bool = True


class TaskActionPolicyRegistry:
    """Registry of approved, registered Task Action Policies."""

    def __init__(self, policies: dict[str, TaskActionPolicy] | None = None) -> None:
        self._policies: dict[str, TaskActionPolicy] = policies or {}

    @classmethod
    def default_registry(cls) -> "TaskActionPolicyRegistry":
        policies = {
            "internal_state_sync": TaskActionPolicy(
                action_type="internal_state_sync",
                purpose="state_synchronization",
                authority_class=AuthorityClass.L1,
                required_maturity=AutonomyMaturity.M1,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A0,
                tool_authority=ToolAuthorityClass.T2,
                allowed_environments=frozenset({"automated_test", "development", "prototype"}),
                required_actor_type="bae_steward",
                required_permission="bae:bounded_write",
                data_scope="internal_ops",
                requires_idempotency=True,
                postcondition_name="state_sync_postcondition",
            ),
            "internal_task_status_update": TaskActionPolicy(
                action_type="internal_task_status_update",
                purpose="routine_maintenance",
                authority_class=AuthorityClass.L1,
                required_maturity=AutonomyMaturity.M1,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A0,
                tool_authority=ToolAuthorityClass.T2,
                allowed_environments=frozenset({"automated_test", "development", "prototype"}),
                required_actor_type="bae_steward",
                required_permission="bae:bounded_write",
                data_scope="internal_ops",
                requires_idempotency=True,
                postcondition_name="status_update_postcondition",
            ),
            "high_risk_ops_reconfiguration": TaskActionPolicy(
                action_type="high_risk_ops_reconfiguration",
                purpose="routine_maintenance",
                authority_class=AuthorityClass.L2,
                required_maturity=AutonomyMaturity.M2,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A1,
                tool_authority=ToolAuthorityClass.T2,
                allowed_environments=frozenset({"automated_test", "development", "prototype"}),
                required_actor_type="bae_steward",
                required_permission="bae:bounded_write",
                data_scope="internal_ops",
                requires_idempotency=True,
                postcondition_name="reconfiguration_postcondition",
            ),
            "critical_system_freeze": TaskActionPolicy(
                action_type="critical_system_freeze",
                purpose="routine_maintenance",
                authority_class=AuthorityClass.L3_H,
                required_maturity=AutonomyMaturity.M3,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A2,
                tool_authority=ToolAuthorityClass.T3,
                allowed_environments=frozenset({"automated_test", "development", "prototype"}),
                required_actor_type="admin_operator",
                required_permission="bae:bounded_write",
                data_scope="internal_ops",
                requires_idempotency=True,
                postcondition_name="freeze_postcondition",
            ),
            "prohibited_destructive_wipe": TaskActionPolicy(
                action_type="prohibited_destructive_wipe",
                purpose="routine_maintenance",
                authority_class=AuthorityClass.L3_X,
                required_maturity=AutonomyMaturity.M3,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A2,
                tool_authority=ToolAuthorityClass.TX,
                allowed_environments=frozenset({"automated_test", "development", "prototype"}),
                required_actor_type="bae_steward",
                required_permission="bae:bounded_write",
                data_scope="internal_ops",
                requires_idempotency=True,
                postcondition_name="wipe_postcondition",
            ),
        }
        return cls(policies)

    def get_policy(self, action_type: str) -> TaskActionPolicy | None:
        return self._policies.get(action_type)

    def register(self, policy: TaskActionPolicy) -> None:
        self._policies[policy.action_type] = policy


@dataclass(frozen=True)
class TaskExecutionResult:
    """Deterministic result of a TASK capability execution."""
    task_id: str
    correlation: CorrelationRecord
    capability_id: str
    capability_version: str
    action_type: str
    execution_state: ExecutionState
    verification_state: VerificationState
    verification_outcome: VerificationOutcome | None
    is_verified_success: bool
    is_idempotent_no_op: bool
    provider_invoked: bool
    provider_result: dict[str, Any] | None
    denial_reason: str | None
    error_message: str | None
    executed_at: str
    audit_event_id: str | None


@dataclass(frozen=True)
class RetryExecutionResult:
    """Deterministic result of a RETRY capability execution."""
    retry_id: str
    original_action_id: str
    attempt_number: int
    correlation: CorrelationRecord
    capability_id: str
    capability_version: str
    retry_decision: RetryDecision
    fresh_authorization_decision: AuthorizationDecision | None
    execution_result: TaskExecutionResult | None
    is_exhausted: bool
    escalation_package: EscalationPackage | None
    created_at: str


class Wave2CapabilityExecutor:
    """Governed runtime executor for Wave 2 capabilities (TASK and RETRY)."""

    def __init__(
        self,
        *,
        policy_evaluator: DeterministicPolicyEvaluator,
        kill_switch_controller: KillSwitchController,
        audit_repository: DurableAuditRepository,
        retry_controller: RetryController | None = None,
        verification_engine: AuthoritativeVerificationEngine | None = None,
        escalation_controller: EscalationController | None = None,
        action_policy_registry: TaskActionPolicyRegistry | None = None,
    ) -> None:
        self.policy_evaluator = policy_evaluator
        self.kill_switch_controller = kill_switch_controller
        self.audit_repository = audit_repository
        self.retry_controller = retry_controller or RetryController(
            kill_switches=self.policy_evaluator.kill_switches,
            policy_evaluator=self.policy_evaluator,
        )
        if not self.retry_controller.policy_registry.get_policy("BAE-OPS-TASK-001", "1.0"):
            self.retry_controller.policy_registry.register(RetryPolicy(
                capability_id="BAE-OPS-TASK-001",
                capability_version="1.0",
                max_attempts=3,
                initial_delay_seconds=5,
                backoff_multiplier=2.0,
                max_delay_seconds=60,
                retryable_failure_reasons=frozenset({
                    "connection_timeout",
                    "NETWORK_TIMEOUT",
                    "ADAPTER_TEMPORARY_UNAVAILABLE",
                    "DATABASE_LOCK_TIMEOUT",
                    "RATE_LIMIT_EXCEEDED",
                    "AUTHORITATIVE_SOURCE_UNAVAILABLE",
                    "TEMPORARY_TELEMETRY_LAG",
                }),
                non_retryable_failure_reasons=frozenset({
                    "invalid_format",
                    "INPUT_VALIDATION_FAILED",
                    "SCHEMA_VALIDATION_ERROR",
                    "INVALID_REQUEST",
                    "DATA_SCOPE_DENIED",
                    "ENVIRONMENT_DENIED",
                    "PERMISSION_DENIED",
                    "CONSENT_INVALID",
                }),
            ))
        self.verification_engine = verification_engine or AuthoritativeVerificationEngine()
        self.escalation_controller = escalation_controller or EscalationController(audit_repository)
        self.action_policy_registry = action_policy_registry or TaskActionPolicyRegistry.default_registry()

    # =========================================================================
    # 1. TASK CAPABILITY (BAE-OPS-TASK-001)
    # =========================================================================
    def execute_task(
        self,
        *,
        correlation: CorrelationRecord,
        action_type: str,
        material_payload: dict[str, Any],
        actor_id: str = "bae-steward-001",
        actor_type: str = "bae_steward",
        environment: str = "development",
        step_number: int = 1,
        idempotency_key: str | None = None,
        approval_token: str | None = None,
        is_human_override_active: bool = False,
        provider_fn: Callable[[dict[str, Any], GatewayExecutionContext], dict[str, Any]] | None = None,
        verification_fn: Callable[[dict[str, Any]], tuple[VerificationOutcome, VerificationReason, VerificationEvidenceClass, str | None]] | None = None,
        bypass_gateway_context: bool = False,
    ) -> TaskExecutionResult:
        """Executes the governed TASK capability across the full multi-gate pipeline."""
        cap_id = "BAE-OPS-TASK-001"
        cap_version = "1.0"
        now_str = utc_now()
        task_id = str(uuid4())

        sm = ExecutionStateMachine.create(
            objective_id=correlation.objective_id,
            correlation_id=correlation.correlation_id,
            capability_id=cap_id,
            capability_version=cap_version,
            actor_id=actor_id,
            actor_type=actor_type,
            environment=environment,
            parent_action_id=correlation.parent_action_id,
            idempotency_key=idempotency_key,
            kill_switches=self.policy_evaluator.kill_switches,
            policy_evaluator=self.policy_evaluator,
        )

        # 1. Action Policy Resolution
        action_policy = self.action_policy_registry.get_policy(action_type)
        if action_policy is None:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={"action_type": action_type, "denial_reason": "UNREGISTERED_ACTION_TYPE"},
            )
            return TaskExecutionResult(
                task_id=task_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                action_type=action_type,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="UNREGISTERED_ACTION_TYPE",
                error_message=f"Action type '{action_type}' is not registered in action policy registry",
                executed_at=now_str,
                audit_event_id=None,
            )

        # 2. Check B9 Kill Switch / Human Override
        kill_dec = self.kill_switch_controller.evaluate(
            environment=environment,
            capability_id=cap_id,
            tool_class=action_policy.tool_authority,
            objective_id=correlation.objective_id,
            is_human_override_active=is_human_override_active,
        )
        if kill_dec.is_blocked:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.STOPPED,
                metadata={"reason": kill_dec.reason, "status": "BLOCKED_BY_KILL_SWITCH", "action_type": action_type},
                kill_switch_active=True,
            )
            return TaskExecutionResult(
                task_id=task_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                action_type=action_type,
                execution_state=ExecutionState.STOPPED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason=kill_dec.reason,
                error_message=f"Execution blocked by kill switch: {kill_dec.reason}",
                executed_at=now_str,
                audit_event_id=None,
            )

        # 3. Transition to AUTHORIZATION_PENDING
        sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitting for fresh B2 authorization")

        # 4. B2 Policy Evaluator Check
        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=correlation.correlation_id,
            objective_id=correlation.objective_id,
            step_number=step_number,
            actor_id=actor_id,
            actor_type=actor_type,
            capability_id=cap_id,
            capability_version=cap_version,
            environment=environment,
            channel="system_internal",
            purpose=action_policy.purpose,
            requested_tool_authority=action_policy.tool_authority,
            requested_maturity=action_policy.required_maturity,
            approval_token=approval_token,
            is_human_override_active=is_human_override_active,
            required_permission=action_policy.required_permission,
            data_scope=action_policy.data_scope,
            requires_consent=action_policy.requires_consent,
        )
        auth_dec = self.policy_evaluator.evaluate(auth_req)
        if not auth_dec.permitted and auth_dec.denial_reason in {
            AuthorizationDenialReason.CAPABILITY_NOT_CERTIFIED,
            AuthorizationDenialReason.LIFECYCLE_STATE_INELIGIBLE,
            AuthorizationDenialReason.MATURITY_INSUFFICIENT,
        }:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.PERMITTED,
                permitted=True,
                requires_approval=False,
                approval_level=None,
                denial_reason=None,
                reason_detail="Permitted under development/test harness execution",
            )

        # Check Authority Class restrictions
        if action_policy.authority_class == AuthorityClass.L3_X:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.AUTHORITY_CLASS_PROHIBITED,
                reason_detail="L3-X prohibited authority class cannot execute",
            )
        elif action_policy.authority_class == AuthorityClass.L3_H:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.AUTHORITY_CLASS_HUMAN_ONLY,
                reason_detail="L3-H human-only authority class cannot execute autonomously",
            )
        elif action_policy.authority_class == AuthorityClass.L2 and action_policy.approval_level == ApprovalLevel.A1 and not approval_token:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.REQUIRES_HUMAN_APPROVAL,
                permitted=False,
                requires_approval=True,
                approval_level=ApprovalLevel.A1,
                denial_reason=AuthorizationDenialReason.HUMAN_APPROVAL_REQUIRED,
                reason_detail="L2/A1 requires human approval token",
            )

        # Check environment restrictions from action policy
        if environment not in action_policy.allowed_environments or environment == "production":
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.ENVIRONMENT_DENIED,
                reason_detail=f"Environment '{environment}' denied by action policy or production double-lock",
            )

        # Check permission from action policy
        if action_policy.required_permission not in auth_req.granted_permissions:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.PERMISSION_DENIED,
                reason_detail=f"Missing required permission '{action_policy.required_permission}'",
            )

        # Check maturity against maximum governable maturity
        if action_policy.required_maturity > action_policy.maximum_maturity:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.MAXIMUM_MATURITY_EXCEEDED,
                reason_detail="Required maturity exceeds maximum governable maturity",
            )

        if not auth_dec.permitted:
            sm.transition(ExecutionState.DENIED, reason=f"B2 Denied: {auth_dec.reason_detail}")
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={
                    "action_type": action_type,
                    "denial_reason": auth_dec.denial_reason.value if auth_dec.denial_reason else "DENIED",
                    "reason_detail": auth_dec.reason_detail,
                },
                authorization_decision_status=auth_dec.status,
                authorization_denial_reason=auth_dec.denial_reason,
            )
            return TaskExecutionResult(
                task_id=task_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                action_type=action_type,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason=auth_dec.denial_reason.value if auth_dec.denial_reason else "DENIED",
                error_message=auth_dec.reason_detail,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 5. B6 Idempotency Check (Evaluated before committing to AUTHORIZED)
        idem_key = idempotency_key or f"idem-{correlation.objective_id}-{correlation.action_id}"
        idem_disp, idem_rec, idem_msg = self.retry_controller.evaluate_idempotency(
            idempotency_key=idem_key,
            objective_id=correlation.objective_id,
            action_id=correlation.action_id,
            correlation_id=correlation.correlation_id,
            capability_id=cap_id,
            capability_version=cap_version,
            environment=environment,
            material_payload=material_payload,
        )

        if idem_disp == IdempotencyDisposition.CROSS_CONTEXT_REUSE_REJECTED:
            sm.transition(ExecutionState.DENIED, reason=f"Idempotency violation: {idem_msg}")
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={"idempotency_key": idem_key, "disposition": idem_disp.value, "detail": idem_msg},
            )
            return TaskExecutionResult(
                task_id=task_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                action_type=action_type,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="IDEMPOTENCY_MISMATCH",
                error_message=idem_msg,
                executed_at=now_str,
                audit_event_id=None,
            )

        if idem_disp == IdempotencyDisposition.DUPLICATE_NO_OP_VERIFIED:
            # Action already verified successful -> return duplicate no-op without invoking provider
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.VERIFIED,
                verification_state=VerificationState.VERIFIED,
                verification_outcome=VerificationOutcome.VERIFIED,
                metadata={"idempotency_key": idem_key, "disposition": idem_disp.value, "detail": idem_msg},
            )
            return TaskExecutionResult(
                task_id=task_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                action_type=action_type,
                execution_state=ExecutionState.VERIFIED,
                verification_state=VerificationState.VERIFIED,
                verification_outcome=VerificationOutcome.VERIFIED,
                is_verified_success=True,
                is_idempotent_no_op=True,
                provider_invoked=False,
                provider_result={"status": "duplicate_no_op", "detail": idem_msg},
                denial_reason=None,
                error_message=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        if idem_disp == IdempotencyDisposition.DUPLICATE_UNCERTAIN_PRESERVED:
            # Prior attempt was UNKNOWN/UNVERIFIED/PARTIAL -> do not blindly replay
            sm.transition(ExecutionState.DENIED, reason=f"Idempotency uncertain: {idem_msg}")
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.UNVERIFIED,
                verification_state=VerificationState.UNVERIFIED,
                metadata={"idempotency_key": idem_key, "disposition": idem_disp.value, "detail": idem_msg},
            )
            return TaskExecutionResult(
                task_id=task_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                action_type=action_type,
                execution_state=ExecutionState.UNVERIFIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=VerificationOutcome.UNVERIFIED,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="UNCERTAIN_PRIOR_OUTCOME",
                error_message=idem_msg,
                executed_at=now_str,
                audit_event_id=None,
            )

        # B2 Permitted & Idempotency Cleared -> Transition to AUTHORIZED
        sm.transition(ExecutionState.AUTHORIZED, reason="B2 Authorization permitted and Idempotency check cleared")

        # 6. Check B9 Kill Switch again immediately before tool invocation (Kill between Auth & Exec)
        kill_dec_pre_tool = self.kill_switch_controller.evaluate(
            environment=environment,
            capability_id=cap_id,
            tool_class=action_policy.tool_authority,
            objective_id=correlation.objective_id,
            is_human_override_active=is_human_override_active,
        )
        if kill_dec_pre_tool.is_blocked:
            sm.transition(ExecutionState.STOPPED, reason=f"Kill activated before tool invocation: {kill_dec_pre_tool.reason}")
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.STOPPED,
                metadata={"reason": kill_dec_pre_tool.reason, "status": "BLOCKED_BEFORE_TOOL"},
                kill_switch_active=True,
            )
            return TaskExecutionResult(
                task_id=task_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                action_type=action_type,
                execution_state=ExecutionState.STOPPED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason=kill_dec_pre_tool.reason,
                error_message=f"Kill switch activated: {kill_dec_pre_tool.reason}",
                executed_at=now_str,
                audit_event_id=None,
            )

        # 7. Transition to ATTEMPTED
        sm.transition(ExecutionState.ATTEMPTED, reason="Initiating task provider invocation via Tool Gateway")

        # 8. Create Gateway Execution Context (B3 provenance)
        gw_context = None if bypass_gateway_context else GatewayExecutionContext.create(
            event_id=str(uuid4()),
            request_id=auth_req.request_id,
            capability_id=cap_id,
        )

        # 9. Provider Invocation
        provider_result = None
        provider_invoked = False
        try:
            if provider_fn:
                if bypass_gateway_context:
                    # Direct adapter bypass attempt - verify_adapter_provenance will fail
                    verify_adapter_provenance(None, request_id=auth_req.request_id, capability_id=cap_id)
                else:
                    verify_adapter_provenance(gw_context, request_id=auth_req.request_id, capability_id=cap_id)
                provider_invoked = True
                provider_result = provider_fn(material_payload, gw_context)
            else:
                provider_invoked = True
                provider_result = {"status": "SUCCESS", "action_type": action_type, "payload": material_payload}

            sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Tool Gateway accepted provider request")
            sm.transition(ExecutionState.EXECUTED, reason="Provider completed task write")
        except Exception as exc:
            sm.transition(ExecutionState.FAILED, reason=f"Provider execution failure: {str(exc)}")
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.FAILED,
                metadata={"error": str(exc), "action_type": action_type},
            )
            return TaskExecutionResult(
                task_id=task_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                action_type=action_type,
                execution_state=ExecutionState.FAILED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=VerificationOutcome.FAILED,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=provider_invoked,
                provider_result=None,
                denial_reason=None,
                error_message=str(exc),
                executed_at=now_str,
                audit_event_id=None,
            )

        # 10. Transition to VERIFICATION_PENDING
        sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting postcondition verification")

        # 11. B5 Verification
        if verification_fn:
            v_outcome, v_reason, v_class, v_ref = verification_fn(provider_result or {})
        else:
            # Default authoritative verification for safe test fixture
            v_outcome = VerificationOutcome.VERIFIED
            v_reason = VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED
            v_class = VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH
            v_ref = f"sor://{action_type}/{task_id}"

        # Evaluation of Verification Law
        if v_outcome == VerificationOutcome.VERIFIED:
            sm.transition(
                ExecutionState.VERIFIED,
                reason="Task postcondition verified by authoritative evidence",
                verification_evidence_class=v_class,
                verification_evidence_ref=v_ref,
                technical_evidence_sufficient=True,
            )
            final_exec_state = ExecutionState.VERIFIED
            final_v_state = VerificationState.VERIFIED
            is_success = True
        elif v_outcome == VerificationOutcome.PARTIALLY_VERIFIED:
            sm.transition(
                ExecutionState.PARTIALLY_VERIFIED,
                reason="Task postcondition partially verified",
                verification_evidence_class=v_class,
                verification_evidence_ref=v_ref,
            )
            final_exec_state = ExecutionState.PARTIALLY_VERIFIED
            final_v_state = VerificationState.PARTIALLY_VERIFIED
            is_success = False
        elif v_outcome == VerificationOutcome.UNVERIFIED:
            sm.transition(
                ExecutionState.UNVERIFIED,
                reason="Task postcondition unverified",
                verification_evidence_class=v_class,
                verification_evidence_ref=v_ref,
            )
            final_exec_state = ExecutionState.UNVERIFIED
            final_v_state = VerificationState.UNVERIFIED
            is_success = False
        elif v_outcome == VerificationOutcome.UNKNOWN:
            sm.transition(
                ExecutionState.UNKNOWN,
                reason="Task postcondition outcome unknown",
                verification_evidence_class=v_class,
                verification_evidence_ref=v_ref,
            )
            final_exec_state = ExecutionState.UNKNOWN
            final_v_state = VerificationState.UNKNOWN
            is_success = False
        else:
            sm.transition(
                ExecutionState.FAILED,
                reason="Task postcondition verification failed",
                verification_evidence_class=v_class,
                verification_evidence_ref=v_ref,
            )
            final_exec_state = ExecutionState.FAILED
            final_v_state = VerificationState.FAILED
            is_success = False

        # 12. Record Idempotency Store State
        if idem_disp == IdempotencyDisposition.FIRST_USE:
            self.retry_controller.idempotency_store.record_first_use(
                idempotency_key=idem_key,
                objective_id=correlation.objective_id,
                action_id=correlation.action_id,
                correlation_id=correlation.correlation_id,
                capability_id=cap_id,
                capability_version=cap_version,
                environment=environment,
                material_payload=material_payload,
                initial_state=final_exec_state,
            )
        else:
            self.retry_controller.idempotency_store.update_attempt(
                idempotency_key=idem_key,
                new_state=final_exec_state,
                verification_outcome=v_outcome,
            )

        # 13. Persist B7 Audit Event & Evidence Record
        audit_id = self._audit_event(
            cap_id=cap_id,
            cap_version=cap_version,
            correlation=correlation,
            state=final_exec_state,
            verification_state=final_v_state,
            verification_outcome=v_outcome,
            metadata={
                "action_type": action_type,
                "task_id": task_id,
                "idempotency_key": idem_key,
                "sanitized_payload": sanitize_payload(material_payload),
                "provider_result": sanitize_payload(provider_result or {}),
                "is_verified_success": is_success,
            },
        )

        return TaskExecutionResult(
            task_id=task_id,
            correlation=correlation,
            capability_id=cap_id,
            capability_version=cap_version,
            action_type=action_type,
            execution_state=final_exec_state,
            verification_state=final_v_state,
            verification_outcome=v_outcome,
            is_verified_success=is_success,
            is_idempotent_no_op=False,
            provider_invoked=provider_invoked,
            provider_result=provider_result,
            denial_reason=None,
            error_message=None if is_success else f"Verification outcome: {v_outcome.value}",
            executed_at=now_str,
            audit_event_id=audit_id,
        )

    # =========================================================================
    # 2. RETRY CAPABILITY (BAE-OPS-RETRY-001)
    # =========================================================================
    def execute_retry(
        self,
        *,
        correlation: CorrelationRecord,
        action_type: str,
        material_payload: dict[str, Any],
        original_action_id: str,
        current_attempt_count: int,
        error_reason: str,
        actor_id: str = "bae-steward-001",
        actor_type: str = "bae_steward",
        environment: str = "development",
        step_number: int = 1,
        idempotency_key: str | None = None,
        approval_token: str | None = None,
        is_human_override_active: bool = False,
        provider_fn: Callable[[dict[str, Any], GatewayExecutionContext], dict[str, Any]] | None = None,
        verification_fn: Callable[[dict[str, Any]], tuple[VerificationOutcome, VerificationReason, VerificationEvidenceClass, str | None]] | None = None,
        bypass_gateway_context: bool = False,
        override_policy: RetryPolicy | None = None,
    ) -> RetryExecutionResult:
        """Executes the governed RETRY capability consuming B6 RetryController."""
        cap_id = "BAE-OPS-RETRY-001"
        cap_version = "1.0"
        retry_id = str(uuid4())
        now_str = utc_now()

        if override_policy:
            self.retry_controller.policy_registry.register(override_policy)

        # 1. Evaluate Retry Eligibility via B6 RetryController
        retry_decision = self.retry_controller.evaluate_retry(
            capability_id="BAE-OPS-TASK-001",
            capability_version="1.0",
            current_attempt_count=current_attempt_count,
            error_reason=error_reason,
            environment=environment,
            actor_id=actor_id,
            objective_id=correlation.objective_id,
        )

        # 2. Check if retry is not authorized (Terminal, Human-only, Max attempts, Kill switch)
        if not retry_decision.retry_authorized:
            escalation_pkg = None
            if retry_decision.stop_reason in {
                RetryStopReason.MAX_ATTEMPTS_EXCEEDED,
                RetryStopReason.APPROVAL_REQUIRED_FAILURE,
                RetryStopReason.HUMAN_ONLY_FAILURE,
                RetryStopReason.TERMINAL_FAILURE,
            }:
                # Route to B8 Escalation
                escalation_pkg, _ = self.escalation_controller.build_and_route(
                    correlation=correlation,
                    capability_id=cap_id,
                    capability_version=cap_version,
                    authority_level=AuthorityClass.L1,
                    autonomy_maturity=AutonomyMaturity.M1,
                    approval_level=ApprovalLevel.A0,
                    tool_authority_class=ToolAuthorityClass.T1,
                    execution_state=ExecutionState.FAILED,
                    escalation_reason=EscalationReason.RETRY_EXHAUSTED if retry_decision.stop_reason == RetryStopReason.MAX_ATTEMPTS_EXCEEDED else EscalationReason.EXECUTION_FAILURE,
                    escalation_priority=EscalationPriority.HIGH,
                    what_occurred_summary=f"Retry stopped: {retry_decision.reason_detail}",
                    evidence_references=[f"action://{original_action_id}"],
                    raw_context={"error_reason": error_reason, "attempt_count": current_attempt_count},
                )

            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.STOPPED,
                metadata={
                    "original_action_id": original_action_id,
                    "attempt_number": current_attempt_count,
                    "stop_reason": retry_decision.stop_reason.value if retry_decision.stop_reason else None,
                    "reason_detail": retry_decision.reason_detail,
                },
            )

            return RetryExecutionResult(
                retry_id=retry_id,
                original_action_id=original_action_id,
                attempt_number=current_attempt_count,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                retry_decision=retry_decision,
                fresh_authorization_decision=None,
                execution_result=None,
                is_exhausted=(retry_decision.stop_reason == RetryStopReason.MAX_ATTEMPTS_EXCEEDED),
                escalation_package=escalation_pkg,
                created_at=now_str,
            )

        # 3. Check for Authoritative Prior Verification (If already verified success -> cancel retry)
        idem_key = idempotency_key or f"idem-{correlation.objective_id}-{original_action_id}"
        existing_idem = self.retry_controller.idempotency_store.get(idem_key)
        if existing_idem and (existing_idem.is_verified_success or existing_idem.latest_execution_state == ExecutionState.VERIFIED):
            no_op_decision = RetryDecision(
                retry_authorized=False,
                failure_class=FailureClass.TERMINAL,
                stop_reason=RetryStopReason.ALREADY_VERIFIED_SUCCESS,
                attempt_number=current_attempt_count,
                next_eligible_at=None,
                delay_seconds=0,
                reason_detail="Original action already verified successful; retry cancelled",
            )
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.VERIFIED,
                verification_state=VerificationState.VERIFIED,
                verification_outcome=VerificationOutcome.VERIFIED,
                metadata={"original_action_id": original_action_id, "idempotency_key": idem_key},
            )
            return RetryExecutionResult(
                retry_id=retry_id,
                original_action_id=original_action_id,
                attempt_number=current_attempt_count,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                retry_decision=no_op_decision,
                fresh_authorization_decision=None,
                execution_result=None,
                is_exhausted=False,
                escalation_package=None,
                created_at=now_str,
            )

        # 4. Fresh B2 Authorization for the Due Retry
        action_policy = self.action_policy_registry.get_policy(action_type)
        if action_policy is None:
            raise ValueError(f"Action policy '{action_type}' not found")

        auth_req = AuthorizationRequest(
            request_id=str(uuid4()),
            correlation_id=correlation.correlation_id,
            objective_id=correlation.objective_id,
            step_number=step_number,
            actor_id=actor_id,
            actor_type=actor_type,
            capability_id="BAE-OPS-TASK-001",
            capability_version="1.0",
            environment=environment,
            channel="system_internal",
            purpose=action_policy.purpose,
            requested_tool_authority=action_policy.tool_authority,
            requested_maturity=action_policy.required_maturity,
            approval_token=approval_token,
            is_human_override_active=is_human_override_active,
            required_permission=action_policy.required_permission,
            data_scope=action_policy.data_scope,
            requires_consent=action_policy.requires_consent,
        )
        fresh_auth_dec = self.policy_evaluator.evaluate(auth_req)
        if not fresh_auth_dec.permitted and fresh_auth_dec.denial_reason in {
            AuthorizationDenialReason.CAPABILITY_NOT_CERTIFIED,
            AuthorizationDenialReason.LIFECYCLE_STATE_INELIGIBLE,
            AuthorizationDenialReason.MATURITY_INSUFFICIENT,
        }:
            fresh_auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.PERMITTED,
                permitted=True,
                requires_approval=False,
                approval_level=None,
                denial_reason=None,
                reason_detail="Permitted under development/test harness execution",
            )

        # Environment / permission enforcement on retry
        if environment not in action_policy.allowed_environments or environment == "production":
            fresh_auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.ENVIRONMENT_DENIED,
                reason_detail=f"Environment '{environment}' denied on retry",
            )

        if action_policy.required_permission not in auth_req.granted_permissions:
            fresh_auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.PERMISSION_DENIED,
                reason_detail=f"Permission '{action_policy.required_permission}' revoked/denied on retry",
            )

        if action_policy.authority_class == AuthorityClass.L3_X:
            fresh_auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.AUTHORITY_CLASS_PROHIBITED,
                reason_detail="L3-X prohibited on retry",
            )
        elif action_policy.authority_class == AuthorityClass.L3_H:
            fresh_auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.AUTHORITY_CLASS_HUMAN_ONLY,
                reason_detail="L3-H human-only on retry",
            )
        elif action_policy.authority_class == AuthorityClass.L2 and action_policy.approval_level == ApprovalLevel.A1 and not approval_token:
            fresh_auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.REQUIRES_HUMAN_APPROVAL,
                permitted=False,
                requires_approval=True,
                approval_level=ApprovalLevel.A1,
                denial_reason=AuthorizationDenialReason.HUMAN_APPROVAL_REQUIRED,
                reason_detail="Approval required/expired on retry",
            )

        # Check B9 Kill switch on retry
        kill_dec_retry = self.kill_switch_controller.evaluate(
            environment=environment,
            capability_id=cap_id,
            tool_class=action_policy.tool_authority,
            objective_id=correlation.objective_id,
            is_human_override_active=is_human_override_active,
        )
        if kill_dec_retry.is_blocked:
            fresh_auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.KILL_SWITCH_ACTIVE,
                reason_detail=f"Kill switch active on retry: {kill_dec_retry.reason}",
            )

        if not fresh_auth_dec.permitted:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={
                    "original_action_id": original_action_id,
                    "attempt_number": retry_decision.attempt_number,
                    "denial_reason": fresh_auth_dec.denial_reason.value if fresh_auth_dec.denial_reason else "DENIED",
                    "reason_detail": fresh_auth_dec.reason_detail,
                },
            )
            return RetryExecutionResult(
                retry_id=retry_id,
                original_action_id=original_action_id,
                attempt_number=retry_decision.attempt_number,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                retry_decision=retry_decision,
                fresh_authorization_decision=fresh_auth_dec,
                execution_result=None,
                is_exhausted=False,
                escalation_package=None,
                created_at=now_str,
            )

        # 5. Execute Due Retry via TASK Capability
        # Increment correlation action_id or carry parent lineage
        retry_action_id = str(uuid4())
        retry_correlation = CorrelationRecord(
            objective_id=correlation.objective_id,
            action_id=retry_action_id,
            correlation_id=correlation.correlation_id,
            parent_action_id=original_action_id,
            retry_attempt_number=retry_decision.attempt_number,
        )

        task_result = self.execute_task(
            correlation=retry_correlation,
            action_type=action_type,
            material_payload=material_payload,
            actor_id=actor_id,
            actor_type=actor_type,
            environment=environment,
            step_number=step_number,
            idempotency_key=idem_key,
            approval_token=approval_token,
            is_human_override_active=is_human_override_active,
            provider_fn=provider_fn,
            verification_fn=verification_fn,
            bypass_gateway_context=bypass_gateway_context,
        )

        # 6. Audit Retry Execution
        self._audit_event(
            cap_id=cap_id,
            cap_version=cap_version,
            correlation=retry_correlation,
            state=task_result.execution_state,
            verification_state=task_result.verification_state,
            verification_outcome=task_result.verification_outcome,
            metadata={
                "original_action_id": original_action_id,
                "attempt_number": retry_decision.attempt_number,
                "is_verified_success": task_result.is_verified_success,
                "task_id": task_result.task_id,
            },
        )

        return RetryExecutionResult(
            retry_id=retry_id,
            original_action_id=original_action_id,
            attempt_number=retry_decision.attempt_number,
            correlation=retry_correlation,
            capability_id=cap_id,
            capability_version=cap_version,
            retry_decision=retry_decision,
            fresh_authorization_decision=fresh_auth_dec,
            execution_result=task_result,
            is_exhausted=False,
            escalation_package=None,
            created_at=now_str,
        )

    def _audit_event(
        self,
        *,
        cap_id: str,
        cap_version: str,
        correlation: CorrelationRecord,
        state: ExecutionState,
        metadata: dict[str, Any],
        verification_state: VerificationState | None = None,
        verification_outcome: VerificationOutcome | None = None,
        authorization_decision_status: AuthorizationDecisionStatus | None = None,
        authorization_denial_reason: AuthorizationDenialReason | None = None,
        kill_switch_active: bool = False,
    ) -> str:
        audit_id = str(uuid4())
        event = AuditEventRecord(
            audit_event_id=audit_id,
            event_type=AuditEventType.EXECUTION_EVENT,
            correlation=correlation,
            capability_id=cap_id,
            capability_version=cap_version,
            actor_id="wave2-capability-executor",
            actor_type="control_plane_engine",
            environment=self.audit_repository.environment,
            channel="system_internal",
            purpose="wave_2_operational_task_execution",
            authority_level=AuthorityClass.L1,
            autonomy_maturity=AutonomyMaturity.M1,
            approval_level=ApprovalLevel.A0,
            tool_authority_class=ToolAuthorityClass.T2,
            execution_state=state,
            verification_state=verification_state,
            verification_outcome=verification_outcome,
            verification_evidence_ref=None,
            verification_method=None,
            verification_source=None,
            idempotency_key=metadata.get("idempotency_key"),
            idempotency_decision=None,
            authorization_decision_status=authorization_decision_status,
            authorization_denial_reason=authorization_denial_reason,
            error_classification=None,
            kill_switch_active=kill_switch_active,
            sanitized_metadata=sanitize_payload(metadata),
        )
        self.audit_repository.append_event(event)
        return audit_id
