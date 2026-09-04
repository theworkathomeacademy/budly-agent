"""BAE Pilot 001 Execution / Verification State Machine (Gate B Step B4 - Section 22 Scope).

Implements the canonical state model:
REQUESTED
→ AUTHORIZATION_PENDING
→ AUTHORIZED / DENIED
→ ATTEMPTED
→ TOOL_ACCEPTED
→ EXECUTED
→ VERIFICATION_PENDING
→ VERIFIED / PARTIALLY_VERIFIED / UNVERIFIED / FAILED / UNKNOWN
→ ESCALATED where applicable
→ COMPLETE / STOPPED / WAITING / RETRY_SCHEDULED

Enforces canonical Section 22 governance invariants:
1. ATTEMPTED must transition to TOOL_ACCEPTED; direct ATTEMPTED -> EXECUTED is prohibited.
2. DENIED must never transition to ATTEMPTED.
3. TOOL_ACCEPTED must never imply VERIFIED.
4. EXECUTED must not imply successful business outcome.
5. Verification evidence classification:
   - AUTHORITATIVE_SOURCE_OF_TRUTH: Can produce VERIFIED.
   - DETERMINISTIC_DIRECT_TECHNICAL: Can produce VERIFIED only when explicitly identified as sufficient for postcondition.
   - CORROBORATED_SECONDARY_OPERATIONAL: Secondary only; cannot produce standalone full VERIFIED.
   - PROVIDER_ACKNOWLEDGEMENT: Acknowledgement only; cannot produce VERIFIED.
   - AGENT_SELF_REPORT: Self-report only; cannot produce VERIFIED.
   - NONE / UNKNOWN: Cannot produce VERIFIED.
6. PARTIALLY_VERIFIED cannot become VERIFIED without new evidence satisfying the minimal evidence boundary (PARTIALLY_VERIFIED -> VERIFICATION_PENDING -> VERIFIED).
7. UNKNOWN and UNVERIFIED must never be inferred as success.
8. Synchronized execution and verification states:
   - VERIFICATION_PENDING => VerificationState.PENDING
   - VERIFIED => VerificationState.VERIFIED
   - PARTIALLY_VERIFIED => VerificationState.PARTIALLY_VERIFIED
   - UNVERIFIED => VerificationState.UNVERIFIED
   - verification FAILED => VerificationState.FAILED
   - verification UNKNOWN => VerificationState.UNKNOWN
9. Hardened COMPLETE:
   - FAILED, ESCALATED, or WAITING transitioning to COMPLETE requires an explicit non-success disposition.
   - A success disposition is reachable only from VERIFIED.
10. FAILED may enter RETRY_SCHEDULED only when later retry policy explicitly authorizes it.
11. Kill switches and human overrides immediately transition execution to STOPPED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from .policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
    AuthorizationRequest,
    BAEKillSwitchRegistry,
    DeterministicPolicyEvaluator,
    utc_now,
)
from .types import ToolAuthorityClass


class ExecutionState(str, Enum):
    """Canonical Execution State Model for BAE Pilot 001."""
    REQUESTED = "REQUESTED"
    AUTHORIZATION_PENDING = "AUTHORIZATION_PENDING"
    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    ATTEMPTED = "ATTEMPTED"
    TOOL_ACCEPTED = "TOOL_ACCEPTED"
    EXECUTED = "EXECUTED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    ESCALATED = "ESCALATED"
    COMPLETE = "COMPLETE"
    STOPPED = "STOPPED"
    WAITING = "WAITING"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"


class VerificationState(str, Enum):
    """Authoritative Verification State Dimension."""
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class VerificationEvidenceClass(str, Enum):
    """Minimal Verification Evidence Classification for B4 State Integrity."""
    AUTHORITATIVE_SOURCE_OF_TRUTH = "AUTHORITATIVE_SOURCE_OF_TRUTH"
    DETERMINISTIC_DIRECT_TECHNICAL = "DETERMINISTIC_DIRECT_TECHNICAL"
    CORROBORATED_SECONDARY_OPERATIONAL = "CORROBORATED_SECONDARY_OPERATIONAL"
    PROVIDER_ACKNOWLEDGEMENT = "PROVIDER_ACKNOWLEDGEMENT"
    AGENT_SELF_REPORT = "AGENT_SELF_REPORT"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class StateTransitionError(RuntimeError):
    """Raised when an illegal or un-governed state transition is attempted."""
    def __init__(self, from_state: ExecutionState, to_state: ExecutionState, reason: str) -> None:
        super().__init__(f"Illegal state transition from {from_state.value} to {to_state.value}: {reason}")
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason


@dataclass(frozen=True)
class ExecutionStateRecord:
    """Immutable record capturing the exact execution, authorization, and verification state at a step."""
    objective_id: str
    action_id: str
    correlation_id: str
    capability_id: str
    capability_version: str
    actor_id: str
    actor_type: str
    environment: str
    current_execution_state: ExecutionState
    verification_state: VerificationState
    created_at: str
    updated_at: str
    parent_action_id: str | None = None
    authorization_decision: AuthorizationDecisionStatus | None = None
    authorization_reason: str | None = None
    step_number: int = 1
    tool_provider_result: dict[str, Any] | None = None
    verification_evidence_reference: str | None = None
    verification_evidence_class: VerificationEvidenceClass | None = None
    retry_reference: str | None = None
    idempotency_key: str | None = None
    final_disposition: str | None = None
    error_classification: str | None = None
    state_history: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "action_id": self.action_id,
            "correlation_id": self.correlation_id,
            "parent_action_id": self.parent_action_id,
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "environment": self.environment,
            "authorization_decision": self.authorization_decision.value if self.authorization_decision else None,
            "authorization_reason": self.authorization_reason,
            "current_execution_state": self.current_execution_state.value,
            "tool_provider_result": self.tool_provider_result,
            "verification_state": self.verification_state.value,
            "verification_evidence_reference": self.verification_evidence_reference,
            "verification_evidence_class": self.verification_evidence_class.value if self.verification_evidence_class else None,
            "retry_reference": self.retry_reference,
            "idempotency_key": self.idempotency_key,
            "step_number": self.step_number,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "final_disposition": self.final_disposition,
            "error_classification": self.error_classification,
            "state_history": list(self.state_history),
        }


class ExecutionStateMachine:
    """Authoritative Execution / Verification State Machine for BAE Pilot 001."""

    ALLOWED_TRANSITIONS: dict[ExecutionState, frozenset[ExecutionState]] = {
        ExecutionState.REQUESTED: frozenset({
            ExecutionState.AUTHORIZATION_PENDING,
            ExecutionState.STOPPED,
        }),
        ExecutionState.AUTHORIZATION_PENDING: frozenset({
            ExecutionState.AUTHORIZED,
            ExecutionState.DENIED,
            ExecutionState.STOPPED,
        }),
        ExecutionState.AUTHORIZED: frozenset({
            ExecutionState.ATTEMPTED,
            ExecutionState.AUTHORIZATION_PENDING,  # Reauthorization on state change
            ExecutionState.STOPPED,
        }),
        ExecutionState.DENIED: frozenset({
            ExecutionState.STOPPED,
            ExecutionState.ESCALATED,
            ExecutionState.WAITING,
        }),
        ExecutionState.ATTEMPTED: frozenset({
            ExecutionState.TOOL_ACCEPTED,  # Mandatory canonical path (ATTEMPTED -> EXECUTED removed)
            ExecutionState.FAILED,
            ExecutionState.UNKNOWN,
            ExecutionState.STOPPED,
        }),
        ExecutionState.TOOL_ACCEPTED: frozenset({
            ExecutionState.EXECUTED,
            ExecutionState.FAILED,
            ExecutionState.UNKNOWN,
            ExecutionState.STOPPED,
        }),
        ExecutionState.EXECUTED: frozenset({
            ExecutionState.VERIFICATION_PENDING,
            ExecutionState.STOPPED,
        }),
        ExecutionState.VERIFICATION_PENDING: frozenset({
            ExecutionState.VERIFIED,
            ExecutionState.PARTIALLY_VERIFIED,
            ExecutionState.UNVERIFIED,
            ExecutionState.FAILED,
            ExecutionState.UNKNOWN,
            ExecutionState.STOPPED,
        }),
        ExecutionState.VERIFIED: frozenset({
            ExecutionState.COMPLETE,
            ExecutionState.AUTHORIZATION_PENDING,  # Next step
            ExecutionState.STOPPED,
        }),
        ExecutionState.PARTIALLY_VERIFIED: frozenset({
            ExecutionState.VERIFICATION_PENDING,  # Must go to VERIFICATION_PENDING first to re-verify
            ExecutionState.ESCALATED,
            ExecutionState.WAITING,
            ExecutionState.STOPPED,
        }),
        ExecutionState.UNVERIFIED: frozenset({
            ExecutionState.ESCALATED,
            ExecutionState.WAITING,
            ExecutionState.STOPPED,
            ExecutionState.FAILED,
        }),
        ExecutionState.FAILED: frozenset({
            ExecutionState.RETRY_SCHEDULED,
            ExecutionState.ESCALATED,
            ExecutionState.STOPPED,
            ExecutionState.COMPLETE,  # Explicit failure closure only
        }),
        ExecutionState.UNKNOWN: frozenset({
            ExecutionState.ESCALATED,
            ExecutionState.STOPPED,
            ExecutionState.WAITING,
        }),
        ExecutionState.ESCALATED: frozenset({
            ExecutionState.WAITING,
            ExecutionState.AUTHORIZATION_PENDING,
            ExecutionState.STOPPED,
            ExecutionState.COMPLETE,  # Explicit non-success closure only
        }),
        ExecutionState.WAITING: frozenset({
            ExecutionState.AUTHORIZATION_PENDING,
            ExecutionState.STOPPED,
            ExecutionState.COMPLETE,  # Explicit non-success closure only
        }),
        ExecutionState.RETRY_SCHEDULED: frozenset({
            ExecutionState.AUTHORIZATION_PENDING,
            ExecutionState.STOPPED,
        }),
        ExecutionState.COMPLETE: frozenset(),
        ExecutionState.STOPPED: frozenset(),
    }

    def __init__(
        self,
        record: ExecutionStateRecord,
        kill_switches: BAEKillSwitchRegistry | None = None,
        policy_evaluator: DeterministicPolicyEvaluator | None = None,
    ) -> None:
        self.record = record
        self.kill_switches = kill_switches
        self.policy_evaluator = policy_evaluator

    @classmethod
    def create(
        cls,
        *,
        objective_id: str,
        correlation_id: str,
        capability_id: str,
        capability_version: str = "1.0",
        actor_id: str,
        actor_type: str,
        environment: str,
        parent_action_id: str | None = None,
        idempotency_key: str | None = None,
        kill_switches: BAEKillSwitchRegistry | None = None,
        policy_evaluator: DeterministicPolicyEvaluator | None = None,
    ) -> "ExecutionStateMachine":
        action_id = str(uuid4())
        now = utc_now()
        record = ExecutionStateRecord(
            objective_id=objective_id,
            action_id=action_id,
            correlation_id=correlation_id,
            parent_action_id=parent_action_id,
            capability_id=capability_id,
            capability_version=capability_version,
            actor_id=actor_id,
            actor_type=actor_type,
            environment=environment,
            current_execution_state=ExecutionState.REQUESTED,
            verification_state=VerificationState.PENDING,
            created_at=now,
            updated_at=now,
            idempotency_key=idempotency_key,
            state_history=({
                "from_state": None,
                "to_state": ExecutionState.REQUESTED.value,
                "timestamp": now,
                "reason": "Execution requested",
            },),
        )
        return cls(record, kill_switches=kill_switches, policy_evaluator=policy_evaluator)

    def transition(
        self,
        target_state: ExecutionState,
        *,
        reason: str,
        authorization_decision: AuthorizationDecision | None = None,
        tool_provider_result: dict[str, Any] | None = None,
        verification_evidence_ref: str | None = None,
        verification_evidence_class: VerificationEvidenceClass | None = None,
        technical_evidence_sufficient: bool = False,
        retry_authorized: bool = False,
        explicit_disposition: str | None = None,
        error_classification: str | None = None,
        human_override_stop: bool = False,
    ) -> ExecutionStateRecord:
        """Executes a validated state transition enforcing all canonical Section 22 governance invariants."""
        current = self.record.current_execution_state

        # Check kill switch or human override intervention
        if human_override_stop:
            target_state = ExecutionState.STOPPED
            reason = f"Human override intervened: {reason}"
        elif self.kill_switches:
            blocked, ks_reason = self.kill_switches.is_blocked(
                self.record.environment, self.record.capability_id, ToolAuthorityClass.T0, self.record.objective_id
            )
            if blocked:
                target_state = ExecutionState.STOPPED
                reason = f"Kill switch active, forced transition to STOPPED: {ks_reason}"

        # Invariant: Terminal states cannot transition
        if current in {ExecutionState.COMPLETE, ExecutionState.STOPPED}:
            raise StateTransitionError(current, target_state, f"Terminal state {current.value} cannot transition to {target_state.value}")

        # Invariant 1: ATTEMPTED cannot transition directly to EXECUTED (must go through TOOL_ACCEPTED)
        if current == ExecutionState.ATTEMPTED and target_state == ExecutionState.EXECUTED:
            raise StateTransitionError(current, target_state, "Invariant violation: ATTEMPTED cannot transition directly to EXECUTED; must transition to TOOL_ACCEPTED first")

        # Invariant 2: DENIED must never transition to ATTEMPTED
        if current == ExecutionState.DENIED and target_state == ExecutionState.ATTEMPTED:
            raise StateTransitionError(current, target_state, "Invariant violation: DENIED state cannot transition to ATTEMPTED")

        # Invariant 3: TOOL_ACCEPTED must never imply VERIFIED
        if target_state == ExecutionState.VERIFIED and current in {ExecutionState.TOOL_ACCEPTED, ExecutionState.EXECUTED, ExecutionState.ATTEMPTED}:
            raise StateTransitionError(current, target_state, "Invariant violation: Tool acknowledgement / execution does not imply VERIFIED")

        # Invariant 4 & 5: Verification Evidence Boundary
        if target_state == ExecutionState.VERIFIED:
            ev_class = verification_evidence_class or self.record.verification_evidence_class
            if ev_class in {VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT, VerificationEvidenceClass.AGENT_SELF_REPORT, VerificationEvidenceClass.NONE, VerificationEvidenceClass.UNKNOWN, None}:
                raise StateTransitionError(
                    current, target_state,
                    f"Invariant violation: Evidence class {ev_class.value if ev_class else 'NONE'} cannot produce VERIFIED state"
                )
            if ev_class == VerificationEvidenceClass.CORROBORATED_SECONDARY_OPERATIONAL:
                raise StateTransitionError(
                    current, target_state,
                    "Invariant violation: Secondary operational evidence alone cannot produce standalone VERIFIED state"
                )
            if ev_class == VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL and not technical_evidence_sufficient:
                raise StateTransitionError(
                    current, target_state,
                    "Invariant violation: DETERMINISTIC_DIRECT_TECHNICAL evidence requires explicit technical sufficiency identification"
                )

        # Invariant 6: PARTIALLY_VERIFIED cannot become VERIFIED without going through VERIFICATION_PENDING
        if current == ExecutionState.PARTIALLY_VERIFIED and target_state == ExecutionState.VERIFIED:
            raise StateTransitionError(current, target_state, "Invariant violation: PARTIALLY_VERIFIED cannot transition directly to VERIFIED; must transition to VERIFICATION_PENDING first")

        # Invariant 7: UNKNOWN and UNVERIFIED must never be inferred as success (cannot transition directly to COMPLETE as SUCCESS)
        if current in {ExecutionState.UNKNOWN, ExecutionState.UNVERIFIED} and target_state == ExecutionState.COMPLETE:
            raise StateTransitionError(current, target_state, f"Invariant violation: {current.value} cannot transition directly to COMPLETE as success")

        # Invariant 8: Hardened COMPLETE from FAILED, ESCALATED, WAITING requires explicit non-success disposition
        if target_state == ExecutionState.COMPLETE:
            if current in {ExecutionState.FAILED, ExecutionState.ESCALATED, ExecutionState.WAITING}:
                if explicit_disposition == "SUCCESS" or (explicit_disposition is None and self.record.verification_state != VerificationState.VERIFIED):
                    raise StateTransitionError(
                        current, target_state,
                        f"Invariant violation: Transition to COMPLETE from {current.value} cannot produce a SUCCESS disposition without prior VERIFIED state"
                    )

        # Invariant 9: FAILED may enter RETRY_SCHEDULED only when retry policy explicitly authorizes it
        if current == ExecutionState.FAILED and target_state == ExecutionState.RETRY_SCHEDULED and not retry_authorized:
            raise StateTransitionError(current, target_state, "Invariant violation: FAILED cannot enter RETRY_SCHEDULED without explicit retry authorization")

        # Check allowed transition graph
        allowed = self.ALLOWED_TRANSITIONS.get(current, frozenset())
        if target_state not in allowed and target_state != ExecutionState.STOPPED:
            raise StateTransitionError(current, target_state, f"Transition from {current.value} to {target_state.value} is not allowed by canonical model")

        # Synchronize execution and verification state deterministically
        now = utc_now()
        ver_state = self.record.verification_state
        if target_state == ExecutionState.VERIFICATION_PENDING:
            ver_state = VerificationState.PENDING
        elif target_state == ExecutionState.VERIFIED:
            ver_state = VerificationState.VERIFIED
        elif target_state == ExecutionState.PARTIALLY_VERIFIED:
            ver_state = VerificationState.PARTIALLY_VERIFIED
        elif target_state == ExecutionState.UNVERIFIED:
            ver_state = VerificationState.UNVERIFIED
        elif target_state == ExecutionState.FAILED and current == ExecutionState.VERIFICATION_PENDING:
            ver_state = VerificationState.FAILED
        elif target_state == ExecutionState.UNKNOWN and current == ExecutionState.VERIFICATION_PENDING:
            ver_state = VerificationState.UNKNOWN

        auth_dec = self.record.authorization_decision
        auth_reason = self.record.authorization_reason
        if authorization_decision is not None:
            auth_dec = authorization_decision.status
            auth_reason = authorization_decision.reason_detail or (authorization_decision.denial_reason.value if authorization_decision.denial_reason else None)

        tool_res = tool_provider_result if tool_provider_result is not None else self.record.tool_provider_result
        ver_ref = verification_evidence_ref if verification_evidence_ref is not None else self.record.verification_evidence_reference
        ver_cls = verification_evidence_class if verification_evidence_class is not None else self.record.verification_evidence_class
        err_cls = error_classification if error_classification is not None else self.record.error_classification

        final_disp = self.record.final_disposition
        if target_state == ExecutionState.COMPLETE:
            if explicit_disposition is not None:
                final_disp = explicit_disposition
            else:
                final_disp = "SUCCESS" if ver_state == VerificationState.VERIFIED else "COMPLETED_NON_SUCCESS"
        elif target_state == ExecutionState.STOPPED:
            final_disp = "STOPPED"
        elif target_state == ExecutionState.DENIED:
            final_disp = "DENIED"

        history_entry = {
            "from_state": current.value,
            "to_state": target_state.value,
            "timestamp": now,
            "reason": reason,
        }

        self.record = ExecutionStateRecord(
            objective_id=self.record.objective_id,
            action_id=self.record.action_id,
            correlation_id=self.record.correlation_id,
            parent_action_id=self.record.parent_action_id,
            capability_id=self.record.capability_id,
            capability_version=self.record.capability_version,
            actor_id=self.record.actor_id,
            actor_type=self.record.actor_type,
            environment=self.record.environment,
            current_execution_state=target_state,
            verification_state=ver_state,
            created_at=self.record.created_at,
            updated_at=now,
            authorization_decision=auth_dec,
            authorization_reason=auth_reason,
            step_number=self.record.step_number,
            tool_provider_result=tool_res,
            verification_evidence_reference=ver_ref,
            verification_evidence_class=ver_cls,
            retry_reference=self.record.retry_reference,
            idempotency_key=self.record.idempotency_key,
            final_disposition=final_disp,
            error_classification=err_cls,
            state_history=self.record.state_history + (history_entry,),
        )
        return self.record
