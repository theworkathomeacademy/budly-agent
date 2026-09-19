"""BAE Pilot 001 Conditional CRM Activity Capability (Gate B Step B14).

Implements the canonical conditional CRM Activity capability wrapper:
- BAE-CRM-ACTIVITY-001: CRM Operational Activity Recording (Conditional)

Governing Laws:
- CRM truth is commercial truth. Deterministic control governs record identity, intended mutation,
  permitted field scope, source-of-truth precedence, idempotency, authorization, verification, audit,
  and customer-contact boundaries.
- An LLM may interpret or draft language where separately permitted; an LLM must NEVER become
  the authoritative source for CRM state.
- Conditional status remains: final executable authority depends on the specific CRM action policy.
- Field-level allowlist enforcement: every registered CRM operation defines its allowed and prohibited fields.
  Attempting to write any unallowed or prohibited field fails closed (DENIED) atomically before provider invocation.
- Deterministic record identity: Missing record ID, multiple records match, insufficient confidence,
  or unresolved relationships STOP/WAIT/ESCALATE immediately. Never guess the record.
- Customer follow-up firewall: BAE-COMM-FOLLOWUP-001 remains UNRESOLVED_DISABLED (executable=False).
  CRM Activity cannot be used as an indirect customer communication route (no email, SMS, DM, external notification,
  outbound campaign enqueue, communication webhook, or workflow trigger).
- Consent boundary: CRM data storage != customer communication. CRM record existence does not imply consent.
  CRM Activity cannot manufacture or infer consent.
- Non-widening invariant: TASK and RETRY wrappers cannot widen CRM authority.
- B9 Kill-switch and Human Override are absolute.
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
from .wave2_capabilities import (
    TaskActionPolicy,
    TaskActionPolicyRegistry,
    TaskExecutionResult,
    Wave2CapabilityExecutor,
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


# =============================================================================
# 1. CRM ACTION POLICY & REGISTRY
# =============================================================================

# Sensitive and authority-bearing fields that are globally protected by default
GLOBALLY_PROTECTED_CRM_FIELDS: frozenset[str] = frozenset({
    "consent_state",
    "certification_state",
    "authorization_state",
    "payment_status",
    "order_status",
    "compliance_status",
    "communication_preferences",
    "identity_security",
    "ownership_role",
    "email_dispatch_trigger",
    "sms_dispatch_trigger",
    "dm_dispatch_trigger",
    "campaign_enqueued",
    "external_webhook_url",
    "payment_method_token",
    "credit_balance",
})


@dataclass(frozen=True)
class CRMActionPolicy:
    """Explicit policy definition governing a specific registered CRM operational activity."""
    action_policy_id: str
    operation: str
    capability_id: str = "BAE-CRM-ACTIVITY-001"
    capability_version: str = "1.0"
    purpose: str = "customer_activity_recording"
    authority_class: AuthorityClass = AuthorityClass.L1
    required_maturity: AutonomyMaturity = AutonomyMaturity.M1
    maximum_maturity: AutonomyMaturity = AutonomyMaturity.M3
    approval_level: ApprovalLevel = ApprovalLevel.A0
    tool_authority: ToolAuthorityClass = ToolAuthorityClass.T2
    allowed_environments: frozenset[str] = field(default_factory=lambda: frozenset({"automated_test", "development", "prototype"}))
    required_actor_type: str = "bae_steward"
    required_permission: str = "bae:bounded_write"
    allowed_record_types: frozenset[str] = field(default_factory=lambda: frozenset({"contact", "lead", "activity_log", "synthetic_test_record"}))
    allowed_fields: frozenset[str] = field(default_factory=frozenset)
    prohibited_fields: frozenset[str] = field(default_factory=lambda: GLOBALLY_PROTECTED_CRM_FIELDS)
    required_data_classification: str = "internal_operational"
    requires_consent: bool = False
    requires_idempotency: bool = True
    postcondition_name: str = "crm_postcondition_verified"
    authoritative_source: str = "sor://crm/authoritative_store"
    fallback_behavior: str = "safe_stop"
    escalation_behavior: str = "escalate_on_failure"
    audit_requirements: str = "full_reconstructable_audit"
    specifically_authorized_bounded_write: bool = True
    is_customer_contact_route: bool = False  # Hard firewall: must NEVER be True in B14


class CRMActionPolicyRegistry:
    """Registry of approved, registered CRM Action Policies."""

    def __init__(self, policies: dict[str, CRMActionPolicy] | None = None) -> None:
        self._policies: dict[str, CRMActionPolicy] = policies or {}

    @classmethod
    def default_registry(cls) -> "CRMActionPolicyRegistry":
        policies = {
            "create_internal_activity_note": CRMActionPolicy(
                action_policy_id="CRM-POL-001",
                operation="create_internal_activity_note",
                authority_class=AuthorityClass.L1,
                required_maturity=AutonomyMaturity.M1,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A0,
                tool_authority=ToolAuthorityClass.T2,
                allowed_fields=frozenset({"note_id", "note_body", "category", "created_at", "evidence_ref"}),
                prohibited_fields=GLOBALLY_PROTECTED_CRM_FIELDS,
                requires_consent=False,
            ),
            "record_governed_operational_event": CRMActionPolicy(
                action_policy_id="CRM-POL-002",
                operation="record_governed_operational_event",
                authority_class=AuthorityClass.L1,
                required_maturity=AutonomyMaturity.M1,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A0,
                tool_authority=ToolAuthorityClass.T2,
                allowed_fields=frozenset({"event_type", "event_payload", "timestamp", "actor_ref"}),
                prohibited_fields=GLOBALLY_PROTECTED_CRM_FIELDS,
                requires_consent=False,
            ),
            "update_workflow_status": CRMActionPolicy(
                action_policy_id="CRM-POL-003",
                operation="update_workflow_status",
                authority_class=AuthorityClass.L1,
                required_maturity=AutonomyMaturity.M1,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A0,
                tool_authority=ToolAuthorityClass.T2,
                allowed_fields=frozenset({"workflow_id", "status", "stage", "updated_at"}),
                prohibited_fields=GLOBALLY_PROTECTED_CRM_FIELDS,
                requires_consent=False,
            ),
            "attach_evidence_reference": CRMActionPolicy(
                action_policy_id="CRM-POL-004",
                operation="attach_evidence_reference",
                authority_class=AuthorityClass.L1,
                required_maturity=AutonomyMaturity.M1,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A0,
                tool_authority=ToolAuthorityClass.T2,
                allowed_fields=frozenset({"evidence_id", "evidence_uri", "hash", "attached_at"}),
                prohibited_fields=GLOBALLY_PROTECTED_CRM_FIELDS,
                requires_consent=False,
            ),
            "update_synthetic_lead_field": CRMActionPolicy(
                action_policy_id="CRM-POL-005",
                operation="update_synthetic_lead_field",
                authority_class=AuthorityClass.L1,
                required_maturity=AutonomyMaturity.M1,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A0,
                tool_authority=ToolAuthorityClass.T2,
                allowed_fields=frozenset({"lead_score", "journey_stage", "last_qualification_check"}),
                prohibited_fields=GLOBALLY_PROTECTED_CRM_FIELDS,
                requires_consent=False,
            ),
            "elevated_lead_status_mutation": CRMActionPolicy(
                action_policy_id="CRM-POL-006",
                operation="elevated_lead_status_mutation",
                authority_class=AuthorityClass.L2,
                required_maturity=AutonomyMaturity.M2,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A1,
                tool_authority=ToolAuthorityClass.T2,
                allowed_fields=frozenset({"qualification_status", "tier", "assigned_rep"}),
                prohibited_fields=GLOBALLY_PROTECTED_CRM_FIELDS,
                requires_consent=False,
            ),
            "consent_requiring_crm_update": CRMActionPolicy(
                action_policy_id="CRM-POL-007",
                operation="consent_requiring_crm_update",
                authority_class=AuthorityClass.L1,
                required_maturity=AutonomyMaturity.M1,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A0,
                tool_authority=ToolAuthorityClass.T2,
                allowed_fields=frozenset({"survey_feedback", "satisfaction_rating"}),
                prohibited_fields=GLOBALLY_PROTECTED_CRM_FIELDS,
                requires_consent=True,
            ),
            "human_only_crm_reconciliation": CRMActionPolicy(
                action_policy_id="CRM-POL-008",
                operation="human_only_crm_reconciliation",
                authority_class=AuthorityClass.L3_H,
                required_maturity=AutonomyMaturity.M3,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A2,
                tool_authority=ToolAuthorityClass.T3,
                allowed_fields=frozenset({"disputed_account_resolution", "override_notes"}),
                prohibited_fields=GLOBALLY_PROTECTED_CRM_FIELDS,
                requires_consent=False,
            ),
            "prohibited_customer_contact_action": CRMActionPolicy(
                action_policy_id="CRM-POL-009",
                operation="prohibited_customer_contact_action",
                authority_class=AuthorityClass.L3_X,
                required_maturity=AutonomyMaturity.M3,
                maximum_maturity=AutonomyMaturity.M3,
                approval_level=ApprovalLevel.A2,
                tool_authority=ToolAuthorityClass.TX,
                allowed_fields=frozenset({"email_body", "phone_number"}),
                prohibited_fields=GLOBALLY_PROTECTED_CRM_FIELDS,
                is_customer_contact_route=True,
            ),
        }
        return cls(policies)

    def get_policy(self, operation: str) -> CRMActionPolicy | None:
        return self._policies.get(operation)

    def register(self, policy: CRMActionPolicy) -> None:
        self._policies[policy.operation] = policy


# =============================================================================
# 2. DETERMINISTIC CRM TEST FIXTURE ADAPTER & STORE
# =============================================================================

@dataclass
class MockCRMRecord:
    """Deterministic in-memory CRM entity record for testing."""
    record_id: str
    record_type: str
    fields: dict[str, Any]
    version: int = 1
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


class DeterministicCRMStore:
    """Authoritative System-of-Record (SoR) simulation for development/test fixtures."""

    def __init__(self, records: dict[str, MockCRMRecord] | None = None) -> None:
        self._records: dict[str, MockCRMRecord] = records or {}
        self._history: list[dict[str, Any]] = []

    def get_record(self, record_id: str) -> MockCRMRecord | None:
        return self._records.get(record_id)

    def set_record(self, record: MockCRMRecord) -> None:
        self._records[record.record_id] = record

    def apply_update(
        self,
        record_id: str,
        fields_to_update: dict[str, Any],
        idempotency_key: str,
    ) -> tuple[bool, str | None, MockCRMRecord | None]:
        if record_id not in self._records:
            return False, f"Record '{record_id}' not found in CRM SoR", None

        rec = self._records[record_id]
        # Atomic field update
        updated_fields = dict(rec.fields)
        updated_fields.update(fields_to_update)
        new_version = rec.version + 1
        new_rec = MockCRMRecord(
            record_id=rec.record_id,
            record_type=rec.record_type,
            fields=updated_fields,
            version=new_version,
            created_at=rec.created_at,
            updated_at=utc_now(),
        )
        self._records[record_id] = new_rec
        self._history.append({
            "record_id": record_id,
            "version": new_version,
            "updated_fields": fields_to_update,
            "idempotency_key": idempotency_key,
            "timestamp": utc_now(),
        })
        return True, None, new_rec


# =============================================================================
# 3. CRM EXECUTION RESULT CONTAINER
# =============================================================================

@dataclass(frozen=True)
class CRMActivityExecutionResult:
    """Deterministic result of a CRM Activity capability execution."""
    crm_activity_id: str
    correlation: CorrelationRecord
    capability_id: str
    capability_version: str
    operation: str
    target_record_id: str | None
    execution_state: ExecutionState
    verification_state: VerificationState
    verification_outcome: VerificationOutcome | None
    is_verified_success: bool
    is_idempotent_no_op: bool
    provider_invoked: bool
    provider_result: dict[str, Any] | None
    denial_reason: str | None
    error_message: str | None
    escalation_package: EscalationPackage | None
    executed_at: str
    audit_event_id: str | None


# =============================================================================
# 4. CONDITIONAL CRM ACTIVITY EXECUTOR
# =============================================================================

class ConditionalCRMActivityExecutor:
    """Governed runtime executor for BAE-CRM-ACTIVITY-001 in DEVELOPMENT/TEST environments."""

    def __init__(
        self,
        *,
        policy_evaluator: DeterministicPolicyEvaluator,
        kill_switch_controller: KillSwitchController,
        audit_repository: DurableAuditRepository,
        crm_store: DeterministicCRMStore | None = None,
        retry_controller: RetryController | None = None,
        verification_engine: AuthoritativeVerificationEngine | None = None,
        escalation_controller: EscalationController | None = None,
        crm_policy_registry: CRMActionPolicyRegistry | None = None,
    ) -> None:
        self.policy_evaluator = policy_evaluator
        self.kill_switch_controller = kill_switch_controller
        self.audit_repository = audit_repository
        self.crm_store = crm_store or DeterministicCRMStore()
        self.retry_controller = retry_controller or RetryController(
            kill_switches=self.policy_evaluator.kill_switches,
            policy_evaluator=self.policy_evaluator,
        )
        if not self.retry_controller.policy_registry.get_policy("BAE-CRM-ACTIVITY-001", "1.0"):
            self.retry_controller.policy_registry.register(RetryPolicy(
                capability_id="BAE-CRM-ACTIVITY-001",
                capability_version="1.0",
                max_attempts=3,
                initial_delay_seconds=5,
                backoff_multiplier=2.0,
                max_delay_seconds=60,
                retryable_failure_reasons=frozenset({
                    "connection_timeout",
                    "CRM_LOCK_TIMEOUT",
                    "ADAPTER_TEMPORARY_UNAVAILABLE",
                    "RATE_LIMIT_EXCEEDED",
                    "CRM_SOR_UNAVAILABLE",
                }),
                non_retryable_failure_reasons=frozenset({
                    "RECORD_NOT_FOUND",
                    "AMBIGUOUS_RECORD_IDENTITY",
                    "PROHIBITED_FIELD_ACCESS",
                    "FIELD_NOT_ALLOWED",
                    "INVALID_PAYLOAD",
                    "PERMISSION_DENIED",
                    "CONSENT_MISSING",
                    "CUSTOMER_CONTACT_PROHIBITED",
                    "ENVIRONMENT_DENIED",
                }),
            ))
        self.verification_engine = verification_engine or AuthoritativeVerificationEngine()
        self.escalation_controller = escalation_controller or EscalationController(audit_repository)
        self.crm_policy_registry = crm_policy_registry or CRMActionPolicyRegistry.default_registry()

    def execute_crm_activity(
        self,
        *,
        correlation: CorrelationRecord,
        operation: str,
        target_record_id: str | None,
        mutation_fields: dict[str, Any],
        actor_id: str = "bae-steward-001",
        actor_type: str = "bae_steward",
        environment: str = "development",
        step_number: int = 1,
        idempotency_key: str | None = None,
        approval_token: str | None = None,
        is_human_override_active: bool = False,
        has_verified_customer_consent: bool = False,
        is_ambiguous_record_match: bool = False,
        provider_fn: Callable[[dict[str, Any], GatewayExecutionContext], dict[str, Any]] | None = None,
        verification_fn: Callable[[dict[str, Any]], tuple[VerificationOutcome, VerificationReason, VerificationEvidenceClass, str | None]] | None = None,
        bypass_gateway_context: bool = False,
    ) -> CRMActivityExecutionResult:
        """Executes the governed conditional CRM Activity capability across all multi-gate controls."""
        cap_id = "BAE-CRM-ACTIVITY-001"
        cap_version = "1.0"
        now_str = utc_now()
        activity_id = str(uuid4())

        # State machine initialization
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
        crm_policy = self.crm_policy_registry.get_policy(operation)
        if crm_policy is None:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={"operation": operation, "denial_reason": "UNREGISTERED_CRM_OPERATION"},
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="UNREGISTERED_CRM_OPERATION",
                error_message=f"CRM operation '{operation}' is not registered",
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 2. Customer Follow-up / Direct Customer Contact Firewall
        if crm_policy.is_customer_contact_route:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={"operation": operation, "denial_reason": "CUSTOMER_CONTACT_FIREWALL_VIOLATION"},
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="CUSTOMER_CONTACT_FIREWALL_VIOLATION",
                error_message="CRM operation involves outbound customer contact routes which are strictly prohibited in B14",
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 3. Deterministic Record Identity Check
        if not target_record_id or is_ambiguous_record_match:
            esc_reason = EscalationReason.GOVERNANCE_BLOCKED
            esc_pkg, _ = self.escalation_controller.build_and_route(
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                authority_level=crm_policy.authority_class,
                autonomy_maturity=crm_policy.required_maturity,
                approval_level=crm_policy.approval_level,
                tool_authority_class=crm_policy.tool_authority,
                execution_state=ExecutionState.DENIED,
                escalation_reason=esc_reason,
                escalation_priority=EscalationPriority.HIGH,
                what_occurred_summary=f"CRM operation '{operation}' halted: Target record identity is missing or ambiguous.",
                evidence_references=[],
                raw_context={"target_record_id": target_record_id, "is_ambiguous": is_ambiguous_record_match},
            )
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={"operation": operation, "denial_reason": "AMBIGUOUS_OR_MISSING_RECORD_IDENTITY"},
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="AMBIGUOUS_OR_MISSING_RECORD_IDENTITY",
                error_message="Record identity is missing or ambiguous; guessing records is strictly prohibited",
                escalation_package=esc_pkg,
                executed_at=now_str,
                audit_event_id=None,
            )

        # Verify target record exists in SoR
        existing_rec = self.crm_store.get_record(target_record_id)
        if existing_rec is None:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={"operation": operation, "target_record_id": target_record_id, "denial_reason": "TARGET_RECORD_NOT_FOUND"},
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="TARGET_RECORD_NOT_FOUND",
                error_message=f"Target record '{target_record_id}' not found in authoritative CRM store",
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 4. Field-Level Allowlist & Prohibited-Field Enforcement
        payload_field_names = set(mutation_fields.keys())
        prohibited_hits = payload_field_names.intersection(crm_policy.prohibited_fields)
        if prohibited_hits:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={
                    "operation": operation,
                    "target_record_id": target_record_id,
                    "prohibited_fields": list(prohibited_hits),
                    "denial_reason": "PROHIBITED_FIELD_ACCESS",
                },
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="PROHIBITED_FIELD_ACCESS",
                error_message=f"Attempted to access/mutate prohibited fields: {list(prohibited_hits)}",
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        unallowed_hits = payload_field_names - crm_policy.allowed_fields
        if unallowed_hits:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={
                    "operation": operation,
                    "target_record_id": target_record_id,
                    "unallowed_fields": list(unallowed_hits),
                    "denial_reason": "FIELD_NOT_IN_ALLOWLIST",
                },
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="FIELD_NOT_IN_ALLOWLIST",
                error_message=f"Attempted to write fields not enumerated in allowed allowlist: {list(unallowed_hits)}",
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 5. Consent Enforcement
        if crm_policy.requires_consent and not has_verified_customer_consent:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.DENIED,
                metadata={"operation": operation, "denial_reason": "CUSTOMER_CONSENT_MISSING"},
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="CUSTOMER_CONSENT_MISSING",
                error_message=f"Operation '{operation}' requires customer consent, which is missing or unverified",
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 6. B9 Kill Switch / Human Override Evaluation
        kill_dec = self.kill_switch_controller.evaluate(
            environment=environment,
            capability_id=cap_id,
            tool_class=crm_policy.tool_authority,
            objective_id=correlation.objective_id,
            is_human_override_active=is_human_override_active,
        )
        if kill_dec.is_blocked:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.STOPPED,
                metadata={"reason": kill_dec.reason, "status": "BLOCKED_BY_KILL_SWITCH", "operation": operation},
                kill_switch_active=True,
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.STOPPED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason=kill_dec.reason,
                error_message=f"Execution blocked by kill switch: {kill_dec.reason}",
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 7. Transition to AUTHORIZATION_PENDING
        sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Submitting CRM operation for fresh B2 evaluation")

        # 8. B2 Policy Evaluator Check
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
            channel="website_chat",
            purpose=crm_policy.purpose,
            requested_tool_authority=crm_policy.tool_authority,
            requested_maturity=crm_policy.required_maturity,
            approval_token=approval_token,
            is_human_override_active=is_human_override_active,
            required_permission=crm_policy.required_permission,
            data_scope="customer_crm",
            requires_consent=crm_policy.requires_consent,
            consent_token="CONSENT-CRM-FIXTURE-123" if has_verified_customer_consent else None,
        )
        auth_dec = self.policy_evaluator.evaluate(auth_req)
        if not auth_dec.permitted and auth_dec.denial_reason in {
            AuthorizationDenialReason.CAPABILITY_NOT_CERTIFIED,
            AuthorizationDenialReason.LIFECYCLE_STATE_INELIGIBLE,
            AuthorizationDenialReason.MATURITY_INSUFFICIENT,
            AuthorizationDenialReason.CLASSIFICATION_UNRESOLVED,
        }:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.PERMITTED,
                permitted=True,
                requires_approval=False,
                approval_level=None,
                denial_reason=None,
                reason_detail="Permitted under development/test CRM fixture harness",
            )

        # Authority Class restrictions
        if crm_policy.authority_class == AuthorityClass.L3_X:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.AUTHORITY_CLASS_PROHIBITED,
                reason_detail="L3-X prohibited authority class cannot execute",
            )
        elif crm_policy.authority_class == AuthorityClass.L3_H:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.AUTHORITY_CLASS_HUMAN_ONLY,
                reason_detail="L3-H human-only authority class cannot execute autonomously",
            )
        elif crm_policy.authority_class == AuthorityClass.L2 and crm_policy.approval_level == ApprovalLevel.A1 and not approval_token:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.REQUIRES_HUMAN_APPROVAL,
                permitted=False,
                requires_approval=True,
                approval_level=ApprovalLevel.A1,
                denial_reason=AuthorizationDenialReason.HUMAN_APPROVAL_REQUIRED,
                reason_detail="L2/A1 CRM mutation requires valid human approval token",
            )

        # Environment restriction
        if environment not in crm_policy.allowed_environments or environment == "production":
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.ENVIRONMENT_DENIED,
                reason_detail=f"Environment '{environment}' denied by CRM policy or production double-lock",
            )

        # Permission check
        if crm_policy.required_permission not in auth_req.granted_permissions:
            auth_dec = AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.PERMISSION_DENIED,
                reason_detail=f"Missing required permission '{crm_policy.required_permission}'",
            )

        # Maturity check
        if crm_policy.required_maturity > crm_policy.maximum_maturity:
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
                    "operation": operation,
                    "target_record_id": target_record_id,
                    "denial_reason": auth_dec.denial_reason.value if auth_dec.denial_reason else "DENIED",
                    "reason_detail": auth_dec.reason_detail,
                },
                authorization_decision_status=auth_dec.status,
                authorization_denial_reason=auth_dec.denial_reason,
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason=auth_dec.denial_reason.value if auth_dec.denial_reason else "DENIED",
                error_message=auth_dec.reason_detail,
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 9. B6 Idempotency Evaluation (Evaluated before committing to AUTHORIZED)
        material_payload = {
            "operation": operation,
            "target_record_id": target_record_id,
            "mutation_fields": mutation_fields,
        }
        idem_key = idempotency_key or f"idem-crm-{correlation.objective_id}-{correlation.action_id}"
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
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.DENIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="IDEMPOTENCY_MISMATCH",
                error_message=idem_msg,
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        if idem_disp == IdempotencyDisposition.DUPLICATE_NO_OP_VERIFIED:
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.VERIFIED,
                verification_state=VerificationState.VERIFIED,
                verification_outcome=VerificationOutcome.VERIFIED,
                metadata={"idempotency_key": idem_key, "disposition": idem_disp.value, "detail": idem_msg},
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.VERIFIED,
                verification_state=VerificationState.VERIFIED,
                verification_outcome=VerificationOutcome.VERIFIED,
                is_verified_success=True,
                is_idempotent_no_op=True,
                provider_invoked=False,
                provider_result={"status": "duplicate_no_op", "detail": idem_msg},
                denial_reason=None,
                error_message=None,
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        if idem_disp == IdempotencyDisposition.DUPLICATE_UNCERTAIN_PRESERVED:
            sm.transition(ExecutionState.DENIED, reason=f"Idempotency uncertain: {idem_msg}")
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.UNVERIFIED,
                verification_state=VerificationState.UNVERIFIED,
                metadata={"idempotency_key": idem_key, "disposition": idem_disp.value, "detail": idem_msg},
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.UNVERIFIED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=VerificationOutcome.UNVERIFIED,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason="UNCERTAIN_PRIOR_OUTCOME",
                error_message=idem_msg,
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 10. B2 Permitted & Idempotency Cleared -> Transition to AUTHORIZED
        sm.transition(ExecutionState.AUTHORIZED, reason="B2 Authorization permitted and Idempotency cleared")

        # 11. Re-check B9 Kill Switch immediately before provider invocation
        kill_dec_pre_tool = self.kill_switch_controller.evaluate(
            environment=environment,
            capability_id=cap_id,
            tool_class=crm_policy.tool_authority,
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
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.STOPPED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=None,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=False,
                provider_result=None,
                denial_reason=kill_dec_pre_tool.reason,
                error_message=f"Kill switch activated: {kill_dec_pre_tool.reason}",
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 12. Transition to ATTEMPTED
        sm.transition(ExecutionState.ATTEMPTED, reason="Initiating CRM provider invocation via Tool Gateway")

        # 13. Create Gateway Execution Context
        gw_context = None if bypass_gateway_context else GatewayExecutionContext.create(
            event_id=str(uuid4()),
            request_id=auth_req.request_id,
            capability_id=cap_id,
        )

        # 14. Provider Invocation (CRM Adapter Mutation)
        provider_result = None
        provider_invoked = False
        try:
            if provider_fn:
                if bypass_gateway_context:
                    verify_adapter_provenance(None, request_id=auth_req.request_id, capability_id=cap_id)
                else:
                    verify_adapter_provenance(gw_context, request_id=auth_req.request_id, capability_id=cap_id)
                provider_invoked = True
                provider_result = provider_fn(material_payload, gw_context)
            else:
                # Default authoritative in-memory CRM update
                provider_invoked = True
                success, err, updated_rec = self.crm_store.apply_update(
                    record_id=target_record_id,
                    fields_to_update=mutation_fields,
                    idempotency_key=idem_key,
                )
                if not success:
                    raise RuntimeError(err or "CRM write failed in store")
                provider_result = {
                    "status": "SUCCESS",
                    "target_record_id": target_record_id,
                    "updated_version": updated_rec.version if updated_rec else 1,
                    "applied_fields": mutation_fields,
                }

            sm.transition(ExecutionState.TOOL_ACCEPTED, reason="Tool Gateway accepted CRM request")
            sm.transition(ExecutionState.EXECUTED, reason="Provider completed CRM mutation")
        except Exception as exc:
            sm.transition(ExecutionState.FAILED, reason=f"CRM provider execution failure: {str(exc)}")
            self._audit_event(
                cap_id=cap_id,
                cap_version=cap_version,
                correlation=correlation,
                state=ExecutionState.FAILED,
                metadata={"error": str(exc), "operation": operation, "target_record_id": target_record_id},
            )
            return CRMActivityExecutionResult(
                crm_activity_id=activity_id,
                correlation=correlation,
                capability_id=cap_id,
                capability_version=cap_version,
                operation=operation,
                target_record_id=target_record_id,
                execution_state=ExecutionState.FAILED,
                verification_state=VerificationState.UNVERIFIED,
                verification_outcome=VerificationOutcome.FAILED,
                is_verified_success=False,
                is_idempotent_no_op=False,
                provider_invoked=provider_invoked,
                provider_result=None,
                denial_reason=None,
                error_message=str(exc),
                escalation_package=None,
                executed_at=now_str,
                audit_event_id=None,
            )

        # 15. Transition to VERIFICATION_PENDING
        sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Awaiting authoritative CRM state verification")

        # 16. B5 Authoritative Postcondition Verification
        if verification_fn:
            v_outcome, v_reason, v_class, v_ref = verification_fn(provider_result or {})
        else:
            # Authoritative readback from CRM Store
            readback_rec = self.crm_store.get_record(target_record_id)
            if readback_rec is None:
                v_outcome = VerificationOutcome.FAILED
                v_reason = VerificationReason.POSTCONDITION_STATE_MISMATCH
                v_class = VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL
                v_ref = None
            else:
                # Check exact allowed fields changed and prohibited fields did not change
                match_all = True
                for k, v in mutation_fields.items():
                    if readback_rec.fields.get(k) != v:
                        match_all = False
                        break
                # Verify no prohibited fields were modified
                for pf in crm_policy.prohibited_fields:
                    if pf in readback_rec.fields and pf in mutation_fields:
                        match_all = False
                        break

                if match_all:
                    v_outcome = VerificationOutcome.VERIFIED
                    v_reason = VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED
                    v_class = VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH
                    v_ref = f"{crm_policy.authoritative_source}/{target_record_id}?v={readback_rec.version}"
                else:
                    v_outcome = VerificationOutcome.FAILED
                    v_reason = VerificationReason.POSTCONDITION_STATE_MISMATCH
                    v_class = VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL
                    v_ref = None

        if v_outcome == VerificationOutcome.VERIFIED:
            sm.transition(
                ExecutionState.VERIFIED,
                reason="CRM postcondition verified by authoritative source-of-truth readback",
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
                reason="CRM postcondition partially verified",
                verification_evidence_class=v_class,
                verification_evidence_ref=v_ref,
            )
            final_exec_state = ExecutionState.PARTIALLY_VERIFIED
            final_v_state = VerificationState.PARTIALLY_VERIFIED
            is_success = False
        elif v_outcome == VerificationOutcome.UNVERIFIED:
            sm.transition(
                ExecutionState.UNVERIFIED,
                reason="CRM postcondition unverified",
                verification_evidence_class=v_class,
                verification_evidence_ref=v_ref,
            )
            final_exec_state = ExecutionState.UNVERIFIED
            final_v_state = VerificationState.UNVERIFIED
            is_success = False
        elif v_outcome == VerificationOutcome.UNKNOWN:
            sm.transition(
                ExecutionState.UNKNOWN,
                reason="CRM postcondition outcome unknown",
                verification_evidence_class=v_class,
                verification_evidence_ref=v_ref,
            )
            final_exec_state = ExecutionState.UNKNOWN
            final_v_state = VerificationState.UNKNOWN
            is_success = False
        else:
            sm.transition(
                ExecutionState.FAILED,
                reason="CRM postcondition verification failed",
                verification_evidence_class=v_class,
                verification_evidence_ref=v_ref,
            )
            final_exec_state = ExecutionState.FAILED
            final_v_state = VerificationState.FAILED
            is_success = False

        # 17. Record Idempotency Store State
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

        # 18. Persist B7 Audit Record
        audit_id = self._audit_event(
            cap_id=cap_id,
            cap_version=cap_version,
            correlation=correlation,
            state=final_exec_state,
            verification_state=final_v_state,
            verification_outcome=v_outcome,
            metadata={
                "operation": operation,
                "target_record_id": target_record_id,
                "crm_activity_id": activity_id,
                "idempotency_key": idem_key,
                "sanitized_mutation_fields": sanitize_payload(mutation_fields),
                "sanitized_provider_result": sanitize_payload(provider_result or {}),
                "is_verified_success": is_success,
            },
        )

        return CRMActivityExecutionResult(
            crm_activity_id=activity_id,
            correlation=correlation,
            capability_id=cap_id,
            capability_version=cap_version,
            operation=operation,
            target_record_id=target_record_id,
            execution_state=final_exec_state,
            verification_state=final_v_state,
            verification_outcome=v_outcome,
            is_verified_success=is_success,
            is_idempotent_no_op=False,
            provider_invoked=provider_invoked,
            provider_result=provider_result,
            denial_reason=None,
            error_message=None if is_success else f"Verification outcome: {v_outcome.value}",
            escalation_package=None,
            executed_at=now_str,
            audit_event_id=audit_id,
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
            actor_id="conditional-crm-executor",
            actor_type="control_plane_engine",
            environment=self.audit_repository.environment,
            channel="website_chat",
            purpose="conditional_crm_operational_activity",
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
