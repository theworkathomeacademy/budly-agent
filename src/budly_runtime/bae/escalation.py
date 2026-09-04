"""BAE Pilot 001 Step B8 Escalation Packaging & Internal Routing Engine.

Implements the governed escalation packaging and internal routing control plane:
- Converts qualifying stopped, denied, uncertain, approval-required, verification-deficient,
  or human-dependent operational states into structured, auditable decision-support packages.
- Escalation is NOT authorization: Creating, routing, delivering, viewing, or acknowledging
  an escalation package does not authorize actions, change L/M/A/T, satisfy approvals,
  or bypass B2/B3/B4/B5/B6 controls.
- Silence is never approval; delivery acknowledgement is never approval; recommendations are non-binding.
- Internal routing only: No customer communication is authorized.
- Deduplication / rate control: Prevents escalation storms for identical material contexts.
- B7 audit & evidence persistence: Persists packages, routing attempts, delivery states, and dedupe events.
- Fresh B2 reauthorization interface: Human responses must return through fresh B2 evaluation.
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
    sanitize_payload,
)
from .policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    utc_now,
)
from .state_machine import (
    ExecutionState,
    VerificationEvidenceClass,
    VerificationState,
)
from .types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    ToolAuthorityClass,
)
from .verification_engine import (
    VerificationMethod,
    VerificationOutcome,
    VerificationReason,
    VerificationResult,
)


class EscalationReason(str, Enum):
    """Deterministic reasons triggering escalation evaluation."""
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    HUMAN_ONLY_ACTION = "HUMAN_ONLY_ACTION"
    AUTHORIZATION_DENIED_REVIEWABLE = "AUTHORIZATION_DENIED_REVIEWABLE"
    VERIFICATION_UNKNOWN = "VERIFICATION_UNKNOWN"
    VERIFICATION_UNVERIFIED = "VERIFICATION_UNVERIFIED"
    VERIFICATION_PARTIAL = "VERIFICATION_PARTIAL"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"
    NON_RETRYABLE_FAILURE = "NON_RETRYABLE_FAILURE"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    CONTROL_STOP = "CONTROL_STOP"
    HUMAN_OVERRIDE = "HUMAN_OVERRIDE"
    ROUTE_UNAVAILABLE = "ROUTE_UNAVAILABLE"
    POLICY_REVIEW_REQUIRED = "POLICY_REVIEW_REQUIRED"
    GOVERNANCE_BLOCKED = "GOVERNANCE_BLOCKED"


class EscalationPriority(str, Enum):
    """Urgency / priority classification of an escalation package."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EscalationDisposition(str, Enum):
    """Deterministic policy outcome for an escalation evaluation."""
    ESCALATE = "ESCALATE"
    DO_NOT_ESCALATE = "DO_NOT_ESCALATE"
    WAIT = "WAIT"
    STOP = "STOP"


class EscalationDeliveryState(str, Enum):
    """Lifecycle state of escalation packaging and routing."""
    CREATED = "CREATED"
    ROUTE_SELECTED = "ROUTE_SELECTED"
    DELIVERY_PENDING = "DELIVERY_PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"
    WAITING = "WAITING"
    STOPPED = "STOPPED"


class HumanOptionType(str, Enum):
    """Structured human choices presented in decision-support packages."""
    APPROVE_FOR_REAUTHORIZATION = "APPROVE_FOR_REAUTHORIZATION"
    REJECT = "REJECT"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    RETRY_IF_REAUTHORIZED = "RETRY_IF_REAUTHORIZED"
    CANCEL_OBJECTIVE = "CANCEL_OBJECTIVE"
    DEFER = "DEFER"
    ACKNOWLEDGE_ONLY = "ACKNOWLEDGE_ONLY"


@dataclass(frozen=True)
class HumanOption:
    """Structured, non-authorizing choice available to a human operator."""
    option_id: str
    option_type: HumanOptionType
    label: str
    description: str
    resulting_intended_action: str
    requires_fresh_b2_authorization: bool = True
    requires_approval_reference: bool = False
    autonomous_continuation_possible: bool = True
    expiry_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "option_id": self.option_id,
            "option_type": self.option_type.value,
            "label": self.label,
            "description": self.description,
            "resulting_intended_action": self.resulting_intended_action,
            "requires_fresh_b2_authorization": self.requires_fresh_b2_authorization,
            "requires_approval_reference": self.requires_approval_reference,
            "autonomous_continuation_possible": self.autonomous_continuation_possible,
            "expiry_seconds": self.expiry_seconds,
        }


@dataclass(frozen=True)
class HumanResponseReference:
    """Represents an operator response submitted back to governance."""
    response_id: str
    escalation_id: str
    objective_id: str
    action_id: str
    correlation_id: str
    selected_option_type: HumanOptionType
    operator_id: str
    operator_role: str
    approval_token_ref: str | None = None
    response_notes: str = ""
    responded_at: str = field(default_factory=utc_now)
    is_stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "response_id": self.response_id,
            "escalation_id": self.escalation_id,
            "objective_id": self.objective_id,
            "action_id": self.action_id,
            "correlation_id": self.correlation_id,
            "selected_option_type": self.selected_option_type.value,
            "operator_id": self.operator_id,
            "operator_role": self.operator_role,
            "approval_token_ref": self.approval_token_ref,
            "response_notes": self.response_notes,
            "responded_at": self.responded_at,
            "is_stale": self.is_stale,
        }


@dataclass(frozen=True)
class EscalationPackage:
    """Immutable, structured decision-support package for human operators."""
    escalation_id: str
    correlation: CorrelationRecord
    capability_id: str
    capability_version: str
    authority_level: AuthorityClass | None
    autonomy_maturity: AutonomyMaturity | None
    approval_level: ApprovalLevel | None
    tool_authority_class: ToolAuthorityClass | None
    execution_state: ExecutionState
    verification_state: VerificationState | None
    verification_outcome: VerificationOutcome | None
    verification_method: VerificationMethod | None
    verification_source: str | None
    escalation_reason: EscalationReason
    escalation_priority: EscalationPriority
    what_occurred_summary: str
    what_remains_permitted: list[str]
    what_is_prohibited: list[str]
    audit_event_references: list[str]
    evidence_references: list[str]
    available_human_options: list[HumanOption]
    recommended_safe_action: str
    impact_of_no_action: str
    internal_route: str
    delivery_state: EscalationDeliveryState
    created_at: str = field(default_factory=utc_now)
    review_by: str | None = None
    delivery_acknowledged_at: str | None = None
    human_response_ref: HumanResponseReference | None = None
    sanitized_context: dict[str, Any] = field(default_factory=dict)

    def compute_dedupe_fingerprint(self) -> str:
        """Computes a deterministic fingerprint of material escalation context."""
        raw = (
            f"{self.correlation.objective_id}|"
            f"{self.correlation.action_id}|"
            f"{self.capability_id}|"
            f"{self.capability_version}|"
            f"{self.escalation_reason.value}|"
            f"{self.execution_state.value}|"
            f"{self.verification_state.value if self.verification_state else 'NONE'}|"
            f"{','.join(sorted(self.evidence_references))}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "escalation_id": self.escalation_id,
            "correlation": self.correlation.to_dict(),
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
            "authority_level": self.authority_level.value if self.authority_level else None,
            "autonomy_maturity": self.autonomy_maturity.value if self.autonomy_maturity else None,
            "approval_level": self.approval_level.value if self.approval_level else None,
            "tool_authority_class": self.tool_authority_class.value if self.tool_authority_class else None,
            "execution_state": self.execution_state.value,
            "verification_state": self.verification_state.value if self.verification_state else None,
            "verification_outcome": self.verification_outcome.value if self.verification_outcome else None,
            "verification_method": self.verification_method.value if self.verification_method else None,
            "verification_source": self.verification_source,
            "escalation_reason": self.escalation_reason.value,
            "escalation_priority": self.escalation_priority.value,
            "what_occurred_summary": self.what_occurred_summary,
            "what_remains_permitted": list(self.what_remains_permitted),
            "what_is_prohibited": list(self.what_is_prohibited),
            "audit_event_references": list(self.audit_event_references),
            "evidence_references": list(self.evidence_references),
            "available_human_options": [opt.to_dict() for opt in self.available_human_options],
            "recommended_safe_action": self.recommended_safe_action,
            "impact_of_no_action": self.impact_of_no_action,
            "internal_route": self.internal_route,
            "delivery_state": self.delivery_state.value,
            "created_at": self.created_at,
            "review_by": self.review_by,
            "delivery_acknowledged_at": self.delivery_acknowledged_at,
            "human_response_ref": self.human_response_ref.to_dict() if self.human_response_ref else None,
            "sanitized_context": self.sanitized_context,
        }


@dataclass(frozen=True)
class EscalationRoute:
    """Approved internal communication route configuration."""
    route_id: str
    channel_type: str  # e.g., "internal_ops_queue", "internal_dashboard", "internal_slack"
    destination_target: str
    is_external_customer_facing: bool = False
    is_active: bool = True


class EscalationRouteRegistry:
    """Manages strictly internal approved escalation routes."""
    def __init__(self, routes: list[EscalationRoute] | None = None) -> None:
        self._routes: dict[str, EscalationRoute] = {}
        if routes:
            for r in routes:
                self.register_route(r)
        else:
            # Register standard internal development/test routes
            self.register_route(EscalationRoute(
                route_id="internal_ops_queue",
                channel_type="internal_queue",
                destination_target="ops-steward-queue-01",
                is_external_customer_facing=False,
                is_active=True,
            ))
            self.register_route(EscalationRoute(
                route_id="internal_supervisor_inbox",
                channel_type="internal_inbox",
                destination_target="supervisor-review-box",
                is_external_customer_facing=False,
                is_active=True,
            ))

    def register_route(self, route: EscalationRoute) -> None:
        if route.is_external_customer_facing:
            raise ValueError(f"Prohibited external/customer route registration: {route.route_id}. B8 is internal only.")
        self._routes[route.route_id] = route

    def get_route(self, route_id: str) -> EscalationRoute | None:
        return self._routes.get(route_id)

    def is_valid_route(self, route_id: str) -> bool:
        route = self._routes.get(route_id)
        return route is not None and route.is_active and not route.is_external_customer_facing


class EscalationPolicyEvaluator:
    """Evaluates operational context and decides whether an escalation package must be created."""
    
    NON_ESCALATING_DENIALS = frozenset({
        AuthorizationDenialReason.CAPABILITY_NOT_REGISTERED,
        AuthorizationDenialReason.ENVIRONMENT_DENIED,
        AuthorizationDenialReason.GATE_D_RELEASE_STATE_INVALID,
        AuthorizationDenialReason.TOOL_AUTHORITY_PROHIBITED,
    })

    @classmethod
    def evaluate(
        cls,
        *,
        execution_state: ExecutionState,
        verification_state: VerificationState | None = None,
        auth_decision: AuthorizationDecision | None = None,
        verification_result: VerificationResult | None = None,
        retry_exhausted: bool = False,
        persistence_failed: bool = False,
        human_override: bool = False,
        control_stopped: bool = False,
    ) -> tuple[EscalationDisposition, EscalationReason | None, EscalationPriority]:
        """Returns deterministic (disposition, reason, priority)."""
        # 1. Persistence failure
        if persistence_failed:
            return EscalationDisposition.ESCALATE, EscalationReason.PERSISTENCE_FAILURE, EscalationPriority.CRITICAL

        # 2. Human override / Control Stop
        if human_override:
            return EscalationDisposition.ESCALATE, EscalationReason.HUMAN_OVERRIDE, EscalationPriority.HIGH
        if control_stopped:
            return EscalationDisposition.ESCALATE, EscalationReason.CONTROL_STOP, EscalationPriority.HIGH

        # 3. Retry exhausted
        if retry_exhausted:
            return EscalationDisposition.ESCALATE, EscalationReason.RETRY_EXHAUSTED, EscalationPriority.HIGH

        # 4. Authorization / Policy boundary
        if auth_decision:
            if auth_decision.status == AuthorizationDecisionStatus.REQUIRES_HUMAN_APPROVAL:
                return EscalationDisposition.ESCALATE, EscalationReason.APPROVAL_REQUIRED, EscalationPriority.NORMAL
            if auth_decision.status == AuthorizationDecisionStatus.DENIED:
                if auth_decision.denial_reason == AuthorizationDenialReason.AUTHORITY_CLASS_HUMAN_ONLY:
                    return EscalationDisposition.ESCALATE, EscalationReason.HUMAN_ONLY_ACTION, EscalationPriority.NORMAL
                if auth_decision.denial_reason == AuthorizationDenialReason.HUMAN_APPROVAL_REQUIRED:
                    return EscalationDisposition.ESCALATE, EscalationReason.APPROVAL_REQUIRED, EscalationPriority.NORMAL
                if auth_decision.denial_reason in cls.NON_ESCALATING_DENIALS:
                    return EscalationDisposition.DO_NOT_ESCALATE, None, EscalationPriority.LOW
                return EscalationDisposition.ESCALATE, EscalationReason.AUTHORIZATION_DENIED_REVIEWABLE, EscalationPriority.NORMAL

        # 5. Verification states
        if verification_state == VerificationState.UNKNOWN or execution_state == ExecutionState.UNKNOWN:
            return EscalationDisposition.ESCALATE, EscalationReason.VERIFICATION_UNKNOWN, EscalationPriority.HIGH
        if verification_state == VerificationState.UNVERIFIED or execution_state == ExecutionState.UNVERIFIED:
            return EscalationDisposition.ESCALATE, EscalationReason.VERIFICATION_UNVERIFIED, EscalationPriority.NORMAL
        if verification_state == VerificationState.PARTIALLY_VERIFIED or execution_state == ExecutionState.PARTIALLY_VERIFIED:
            return EscalationDisposition.ESCALATE, EscalationReason.VERIFICATION_PARTIAL, EscalationPriority.NORMAL
        if verification_result and verification_result.reason == VerificationReason.VERIFICATION_SOURCE_UNAVAILABLE:
            return EscalationDisposition.ESCALATE, EscalationReason.VERIFICATION_UNAVAILABLE, EscalationPriority.HIGH

        # 6. Execution failure
        if execution_state == ExecutionState.FAILED:
            return EscalationDisposition.ESCALATE, EscalationReason.NON_RETRYABLE_FAILURE, EscalationPriority.HIGH

        return EscalationDisposition.DO_NOT_ESCALATE, None, EscalationPriority.LOW


class EscalationController:
    """Core controller for packaging, deduplicating, routing, and recording escalations."""

    def __init__(
        self,
        audit_repo: DurableAuditRepository,
        route_registry: EscalationRouteRegistry | None = None,
    ) -> None:
        self._audit_repo = audit_repo
        self._route_registry = route_registry or EscalationRouteRegistry()
        self._seen_fingerprints: dict[str, str] = {}  # fingerprint -> escalation_id

    def build_and_route(
        self,
        *,
        correlation: CorrelationRecord,
        capability_id: str,
        capability_version: str,
        authority_level: AuthorityClass | None,
        autonomy_maturity: AutonomyMaturity | None,
        approval_level: ApprovalLevel | None,
        tool_authority_class: ToolAuthorityClass | None,
        execution_state: ExecutionState,
        verification_state: VerificationState | None = None,
        verification_outcome: VerificationOutcome | None = None,
        verification_method: VerificationMethod | None = None,
        verification_source: str | None = None,
        escalation_reason: EscalationReason,
        escalation_priority: EscalationPriority,
        what_occurred_summary: str,
        what_remains_permitted: list[str] | None = None,
        what_is_prohibited: list[str] | None = None,
        audit_event_references: list[str] | None = None,
        evidence_references: list[str] | None = None,
        available_human_options: list[HumanOption] | None = None,
        recommended_safe_action: str = "Await human review or manual reauthorization",
        impact_of_no_action: str = "Autonomous execution halted; no side effects produced",
        internal_route: str = "internal_ops_queue",
        raw_context: dict[str, Any] | None = None,
    ) -> tuple[EscalationPackage | None, EscalationDeliveryState]:
        """Packages, deduplicates, verifies route, and persists escalation records to B7."""
        # 1. Check Route Validity
        if not self._route_registry.is_valid_route(internal_route):
            # Prohibited or unavailable route fails safe to STOPPED/WAITING
            self._record_governance_audit(
                correlation=correlation,
                capability_id=capability_id,
                capability_version=capability_version,
                state=ExecutionState.STOPPED,
                metadata={
                    "error": "UNAVAILABLE_OR_PROHIBITED_ROUTE",
                    "requested_route": internal_route,
                },
            )
            return None, EscalationDeliveryState.STOPPED

        # 2. Build Human Options if not provided
        options = available_human_options or self._default_options_for_reason(escalation_reason, authority_level)

        # 3. Sanitize Context
        sanitized_ctx = sanitize_payload(raw_context)

        # 4. Construct Package
        package = EscalationPackage(
            escalation_id=str(uuid4()),
            correlation=correlation,
            capability_id=capability_id,
            capability_version=capability_version,
            authority_level=authority_level,
            autonomy_maturity=autonomy_maturity,
            approval_level=approval_level,
            tool_authority_class=tool_authority_class,
            execution_state=execution_state,
            verification_state=verification_state,
            verification_outcome=verification_outcome,
            verification_method=verification_method,
            verification_source=verification_source,
            escalation_reason=escalation_reason,
            escalation_priority=escalation_priority,
            what_occurred_summary=what_occurred_summary,
            what_remains_permitted=what_remains_permitted or ["Manual operational inspection", "Safe non-autonomous review"],
            what_is_prohibited=what_is_prohibited or ["Unverified autonomous writes", "Bypassing B2 continuous authorization"],
            audit_event_references=audit_event_references or [],
            evidence_references=evidence_references or [],
            available_human_options=options,
            recommended_safe_action=recommended_safe_action,
            impact_of_no_action=impact_of_no_action,
            internal_route=internal_route,
            delivery_state=EscalationDeliveryState.CREATED,
            sanitized_context=sanitized_ctx,
        )

        # 5. Check Deduplication
        fingerprint = package.compute_dedupe_fingerprint()
        if fingerprint in self._seen_fingerprints:
            # Duplicate suppressed
            prior_id = self._seen_fingerprints[fingerprint]
            self._record_governance_audit(
                correlation=correlation,
                capability_id=capability_id,
                capability_version=capability_version,
                state=ExecutionState.ESCALATED,
                metadata={
                    "escalation_deduplicated": True,
                    "suppressed_escalation_id": package.escalation_id,
                    "existing_escalation_id": prior_id,
                    "fingerprint": fingerprint,
                },
            )
            return package, EscalationDeliveryState.ACKNOWLEDGED

        self._seen_fingerprints[fingerprint] = package.escalation_id

        # 6. Simulate Internal Route Delivery in Dev/Test
        delivery_state = EscalationDeliveryState.SENT

        # 7. Record B7 Audit Event
        self._record_governance_audit(
            correlation=correlation,
            capability_id=capability_id,
            capability_version=capability_version,
            state=ExecutionState.ESCALATED,
            metadata={
                "escalation_id": package.escalation_id,
                "escalation_reason": package.escalation_reason.value,
                "escalation_priority": package.escalation_priority.value,
                "internal_route": package.internal_route,
                "delivery_state": delivery_state.value,
                "options_count": len(package.available_human_options),
                "sanitized_context": package.sanitized_context,
            },
        )

        return package, delivery_state

    def _default_options_for_reason(
        self,
        reason: EscalationReason,
        authority_level: AuthorityClass | None,
    ) -> list[HumanOption]:
        """Builds default structured options conforming to authority bounds."""
        options = []
        if authority_level == AuthorityClass.L3_X:
            # Absolutely prohibited: NO autonomous continuation or authorization option
            options.append(HumanOption(
                option_id=str(uuid4()),
                option_type=HumanOptionType.CANCEL_OBJECTIVE,
                label="Cancel Prohibited Action",
                description="Action is strictly prohibited under L3-X governance.",
                resulting_intended_action="Terminate autonomous action without continuation.",
                requires_fresh_b2_authorization=False,
                autonomous_continuation_possible=False,
            ))
            options.append(HumanOption(
                option_id=str(uuid4()),
                option_type=HumanOptionType.ACKNOWLEDGE_ONLY,
                label="Acknowledge Prohibited State",
                description="Acknowledge non-executable policy denial.",
                resulting_intended_action="Record operator awareness.",
                requires_fresh_b2_authorization=False,
                autonomous_continuation_possible=False,
            ))
            return options

        if reason in {EscalationReason.APPROVAL_REQUIRED, EscalationReason.AUTHORIZATION_DENIED_REVIEWABLE}:
            options.append(HumanOption(
                option_id=str(uuid4()),
                option_type=HumanOptionType.APPROVE_FOR_REAUTHORIZATION,
                label="Approve for Re-authorization",
                description="Grant required approval; requires fresh B2 policy re-evaluation.",
                resulting_intended_action="Submit approval reference to B2 continuous authorization.",
                requires_fresh_b2_authorization=True,
                requires_approval_reference=True,
                autonomous_continuation_possible=True,
            ))
            options.append(HumanOption(
                option_id=str(uuid4()),
                option_type=HumanOptionType.REJECT,
                label="Reject Action",
                description="Disapprove autonomous continuation.",
                resulting_intended_action="Transition execution to terminal STOPPED state.",
                requires_fresh_b2_authorization=False,
                autonomous_continuation_possible=False,
            ))

        elif reason in {EscalationReason.VERIFICATION_UNKNOWN, EscalationReason.VERIFICATION_UNVERIFIED, EscalationReason.VERIFICATION_PARTIAL}:
            options.append(HumanOption(
                option_id=str(uuid4()),
                option_type=HumanOptionType.REQUEST_MORE_EVIDENCE,
                label="Request Authoritative Evidence",
                description="Collect additional deterministic verification evidence.",
                resulting_intended_action="Re-query authoritative verification source.",
                requires_fresh_b2_authorization=True,
                autonomous_continuation_possible=True,
            ))
            options.append(HumanOption(
                option_id=str(uuid4()),
                option_type=HumanOptionType.CANCEL_OBJECTIVE,
                label="Cancel Unverified Step",
                description="Cease execution due to incomplete verification.",
                resulting_intended_action="Halt action execution.",
                requires_fresh_b2_authorization=False,
                autonomous_continuation_possible=False,
            ))

        else:
            options.append(HumanOption(
                option_id=str(uuid4()),
                option_type=HumanOptionType.ACKNOWLEDGE_ONLY,
                label="Acknowledge Disposition",
                description="Acknowledge operational stopping condition.",
                resulting_intended_action="Confirm operator receipt.",
                requires_fresh_b2_authorization=False,
                autonomous_continuation_possible=False,
            ))
            options.append(HumanOption(
                option_id=str(uuid4()),
                option_type=HumanOptionType.DEFER,
                label="Defer Decision",
                description="Postpone operational review.",
                resulting_intended_action="Maintain WAITING state.",
                requires_fresh_b2_authorization=False,
                autonomous_continuation_possible=False,
            ))

        return options

    def _record_governance_audit(
        self,
        correlation: CorrelationRecord,
        capability_id: str,
        capability_version: str,
        state: ExecutionState,
        metadata: dict[str, Any],
    ) -> None:
        event = AuditEventRecord(
            audit_event_id=str(uuid4()),
            event_type=AuditEventType.ESCALATION_EVENT,
            correlation=correlation,
            capability_id=capability_id,
            capability_version=capability_version,
            actor_id="bae-escalation-controller",
            actor_type="control_plane_engine",
            environment=self._audit_repo.environment,
            channel="system_internal",
            purpose="escalation_packaging_and_routing",
            authority_level=None,
            autonomy_maturity=None,
            approval_level=None,
            tool_authority_class=None,
            execution_state=state,
            verification_state=None,
            verification_outcome=None,
            verification_evidence_ref=None,
            verification_method=None,
            verification_source=None,
            idempotency_key=None,
            idempotency_decision=None,
            authorization_decision_status=None,
            authorization_denial_reason=None,
            error_classification=None,
            sanitized_metadata=metadata,
        )
        self._audit_repo.append_event(event)


def validate_human_response_for_reauthorization(
    response: HumanResponseReference | None,
    expected_objective_id: str,
    expected_action_id: str,
) -> tuple[bool, str]:
    """Validates whether a human response can be referenced in fresh B2 authorization.
    
    Enforces that silence, delivery, wrong objective, or stale responses NEVER authorize.
    """
    if response is None:
        return False, "SILENCE_OR_MISSING_RESPONSE"
    if response.is_stale:
        return False, "STALE_HUMAN_RESPONSE"
    if response.objective_id != expected_objective_id:
        return False, "OBJECTIVE_ID_MISMATCH"
    if response.action_id != expected_action_id:
        return False, "ACTION_ID_MISMATCH"
    if response.selected_option_type not in {
        HumanOptionType.APPROVE_FOR_REAUTHORIZATION,
        HumanOptionType.RETRY_IF_REAUTHORIZED,
    }:
        return False, "SELECTED_OPTION_DOES_NOT_AUTHORIZE"
    return True, "VALID_HUMAN_RESPONSE_REFERENCE"
