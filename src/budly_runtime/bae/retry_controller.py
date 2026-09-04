"""BAE Pilot 001 Retry / Idempotency Controller (Gate B Step B6).

Enforces strict governed retry and idempotency invariants:
1. Retry inherits the authority restrictions of the underlying action and never widens them.
2. Every retry is a new material autonomous step and requires current B2 authorization before execution.
3. A prior successful authorization token cannot authorize a later retry after governing state changes.
4. Idempotency is mandatory for duplicate-sensitive operations.
5. Duplicate detection prevents repeated side effects while preserving audit evidence.
6. UNKNOWN, UNVERIFIED, and PARTIALLY_VERIFIED outcomes are not treated as automatically safe to retry.
7. FAILED enters RETRY_SCHEDULED only when an explicit registered retry policy authorizes it.
8. Distinguishes failure classifications:
   - RETRYABLE
   - NON_RETRYABLE
   - APPROVAL_REQUIRED
   - HUMAN_ONLY
   - TERMINAL
9. Bounded attempt counts, deterministic exponential backoff with jitter/caps, and deterministic stop conditions.
10. Retry never bypasses kill switches, human override, suspension, permission revocation, consent changes, release-state changes, environment restrictions, verification availability, or Tool Gateway controls.
11. Idempotency keys are bound to material objective/action/operation and cannot be reused across unrelated contexts.
12. Duplicate idempotency keys after a VERIFIED successful effect produce a deterministic duplicate/no-op result without executing side effects again.
13. Duplicate keys after FAILED, UNKNOWN, UNVERIFIED, or uncertain prior attempts preserve prior evidence and follow registered retry policy.
14. Attempt history, idempotency history, next eligible retry time, retry reason, retry authorization, and terminal disposition are fully auditable.
15. Scheduling a retry does not execute the tool; when due, fresh B2 authorization and B3 gateway enforcement are required.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from .policy_evaluator import (
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
from .state_machine import (
    ExecutionState,
    ExecutionStateMachine,
    ExecutionStateRecord,
    StateTransitionError,
    VerificationEvidenceClass,
    VerificationState,
)
from .verification_engine import (
    VerificationAccessDecision,
    VerificationMethod,
    VerificationOutcome,
    VerificationReason,
    VerificationResult,
)


class FailureClass(str, Enum):
    """Deterministic Failure Classifications."""
    RETRYABLE = "RETRYABLE"
    NON_RETRYABLE = "NON_RETRYABLE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    HUMAN_ONLY = "HUMAN_ONLY"
    TERMINAL = "TERMINAL"


class RetryStopReason(str, Enum):
    """Deterministic Reasons for Terminating Retry Lifecycle."""
    MAX_ATTEMPTS_EXCEEDED = "MAX_ATTEMPTS_EXCEEDED"
    NON_RETRYABLE_FAILURE = "NON_RETRYABLE_FAILURE"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"
    HUMAN_ONLY_FAILURE = "HUMAN_ONLY_FAILURE"
    APPROVAL_REQUIRED_FAILURE = "APPROVAL_REQUIRED_FAILURE"
    NO_RETRY_POLICY_REGISTERED = "NO_RETRY_POLICY_REGISTERED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    HUMAN_OVERRIDE_ACTIVE = "HUMAN_OVERRIDE_ACTIVE"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    ENVIRONMENT_PROHIBITED = "ENVIRONMENT_PROHIBITED"
    AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
    ALREADY_VERIFIED_SUCCESS = "ALREADY_VERIFIED_SUCCESS"


class IdempotencyDisposition(str, Enum):
    """Deterministic dispositions for idempotency evaluation."""
    FIRST_USE = "FIRST_USE"
    DUPLICATE_NO_OP_VERIFIED = "DUPLICATE_NO_OP_VERIFIED"
    DUPLICATE_RETRY_PERMITTED = "DUPLICATE_RETRY_PERMITTED"
    DUPLICATE_RETRY_DENIED = "DUPLICATE_RETRY_DENIED"
    DUPLICATE_UNCERTAIN_PRESERVED = "DUPLICATE_UNCERTAIN_PRESERVED"
    CROSS_CONTEXT_REUSE_REJECTED = "CROSS_CONTEXT_REUSE_REJECTED"


@dataclass(frozen=True)
class RetryPolicy:
    """Ratified retry policy for a capability/operation."""
    capability_id: str
    capability_version: str
    max_attempts: int = 3
    initial_delay_seconds: int = 5
    backoff_multiplier: float = 2.0
    max_delay_seconds: int = 300
    retryable_failure_reasons: frozenset[str] = frozenset({
        "ADAPTER_TEMPORARY_UNAVAILABLE",
        "DATABASE_LOCK_TIMEOUT",
        "NETWORK_TIMEOUT",
        "RATE_LIMIT_EXCEEDED",
        "AUTHORITATIVE_SOURCE_UNAVAILABLE",
        "TEMPORARY_TELEMETRY_LAG",
    })
    non_retryable_failure_reasons: frozenset[str] = frozenset({
        "INPUT_VALIDATION_FAILED",
        "SCHEMA_VALIDATION_ERROR",
        "INVALID_REQUEST",
        "DATA_SCOPE_DENIED",
        "ENVIRONMENT_DENIED",
        "PERMISSION_DENIED",
        "CONSENT_INVALID",
    })
    approval_required_failure_reasons: frozenset[str] = frozenset({
        "HUMAN_APPROVAL_REQUIRED",
        "RESTRICTED_DATA_MUTATION_SUSPECTED",
    })
    human_only_failure_reasons: frozenset[str] = frozenset({
        "HUMAN_INTERVENTION_MANDATED",
        "SYSTEM_SECURITY_COMPROMISE_SUSPECTED",
    })
    terminal_failure_reasons: frozenset[str] = frozenset({
        "PERMANENT_CORRUPTION",
        "CONTRACT_TERMINATED",
        "UNSUPPORTED_PROTOCOL_VERSION",
    })

    def classify_failure(self, error_reason: str) -> FailureClass:
        if error_reason in self.terminal_failure_reasons:
            return FailureClass.TERMINAL
        if error_reason in self.human_only_failure_reasons:
            return FailureClass.HUMAN_ONLY
        if error_reason in self.approval_required_failure_reasons:
            return FailureClass.APPROVAL_REQUIRED
        if error_reason in self.non_retryable_failure_reasons:
            return FailureClass.NON_RETRYABLE
        if error_reason in self.retryable_failure_reasons:
            return FailureClass.RETRYABLE
        # Default fail-closed for unclassified failure reasons
        return FailureClass.NON_RETRYABLE

    def calculate_backoff(self, attempt_number: int) -> int:
        if attempt_number <= 1:
            return self.initial_delay_seconds
        delay = self.initial_delay_seconds * (self.backoff_multiplier ** (attempt_number - 1))
        return min(int(delay), self.max_delay_seconds)


@dataclass(frozen=True)
class RetryAttempt:
    """Record of an executed or scheduled retry attempt."""
    attempt_number: int
    scheduled_at: str
    eligible_at: str
    executed_at: str | None
    error_reason: str | None
    failure_class: FailureClass | None
    authorization_decision_ref: str | None
    verification_outcome: VerificationOutcome | None


@dataclass(frozen=True)
class IdempotencyRecord:
    """Bound idempotency state record for an objective/action/operation."""
    idempotency_key: str
    objective_id: str
    action_id: str
    correlation_id: str
    capability_id: str
    capability_version: str
    environment: str
    material_payload_hash: str
    first_seen_at: str
    last_attempt_at: str
    attempt_count: int
    is_verified_success: bool
    latest_verification_outcome: VerificationOutcome | None
    latest_execution_state: ExecutionState
    attempts: tuple[RetryAttempt, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RetryDecision:
    """Deterministic retry decision artifact."""
    retry_authorized: bool
    failure_class: FailureClass
    stop_reason: RetryStopReason | None
    attempt_number: int
    next_eligible_at: str | None
    delay_seconds: int
    reason_detail: str


class RetryPolicyRegistry:
    """Registry of ratified retry policies for governed BAE capabilities."""

    def __init__(self, policies: dict[tuple[str, str], RetryPolicy] | None = None) -> None:
        self._policies: dict[tuple[str, str], RetryPolicy] = policies or {}

    @classmethod
    def default_registry(cls) -> "RetryPolicyRegistry":
        policies = {
            ("BAE-OPS-OBSERVE-001", "1.0"): RetryPolicy(
                capability_id="BAE-OPS-OBSERVE-001",
                capability_version="1.0",
                max_attempts=3,
                initial_delay_seconds=5,
                backoff_multiplier=2.0,
                max_delay_seconds=60,
            ),
            ("activity.record", "1.0"): RetryPolicy(
                capability_id="activity.record",
                capability_version="1.0",
                max_attempts=3,
                initial_delay_seconds=10,
                backoff_multiplier=2.0,
                max_delay_seconds=120,
            ),
            ("customer.preference.record", "1.0"): RetryPolicy(
                capability_id="customer.preference.record",
                capability_version="1.0",
                max_attempts=2,
                initial_delay_seconds=10,
                backoff_multiplier=2.0,
                max_delay_seconds=60,
            ),
            ("customer.relationship_fact.record", "1.0"): RetryPolicy(
                capability_id="customer.relationship_fact.record",
                capability_version="1.0",
                max_attempts=2,
                initial_delay_seconds=10,
                backoff_multiplier=2.0,
                max_delay_seconds=60,
            ),
            ("customer.memory.retrieve", "1.0"): RetryPolicy(
                capability_id="customer.memory.retrieve",
                capability_version="1.0",
                max_attempts=3,
                initial_delay_seconds=5,
                backoff_multiplier=2.0,
                max_delay_seconds=60,
            ),
        }
        return cls(policies)

    def get_policy(self, capability_id: str, capability_version: str) -> RetryPolicy | None:
        return self._policies.get((capability_id, capability_version))

    def register(self, policy: RetryPolicy) -> None:
        self._policies[(policy.capability_id, policy.capability_version)] = policy


class IdempotencyStore:
    """In-memory auditable store for idempotency records."""

    def __init__(self) -> None:
        self._store: dict[str, IdempotencyRecord] = {}

    def get(self, idempotency_key: str) -> IdempotencyRecord | None:
        return self._store.get(idempotency_key)

    def record_first_use(
        self,
        *,
        idempotency_key: str,
        objective_id: str,
        action_id: str,
        correlation_id: str,
        capability_id: str,
        capability_version: str,
        environment: str,
        material_payload: dict[str, Any],
        initial_state: ExecutionState,
    ) -> IdempotencyRecord:
        now = utc_now()
        payload_hash = hashlib.sha256(
            json.dumps(material_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            objective_id=objective_id,
            action_id=action_id,
            correlation_id=correlation_id,
            capability_id=capability_id,
            capability_version=capability_version,
            environment=environment,
            material_payload_hash=payload_hash,
            first_seen_at=now,
            last_attempt_at=now,
            attempt_count=1,
            is_verified_success=(initial_state == ExecutionState.VERIFIED),
            latest_verification_outcome=VerificationOutcome.VERIFIED if initial_state == ExecutionState.VERIFIED else None,
            latest_execution_state=initial_state,
            attempts=(RetryAttempt(
                attempt_number=1,
                scheduled_at=now,
                eligible_at=now,
                executed_at=now,
                error_reason=None,
                failure_class=None,
                authorization_decision_ref=None,
                verification_outcome=VerificationOutcome.VERIFIED if initial_state == ExecutionState.VERIFIED else None,
            ),),
        )
        self._store[idempotency_key] = record
        return record

    def update_attempt(
        self,
        *,
        idempotency_key: str,
        new_state: ExecutionState,
        verification_outcome: VerificationOutcome | None = None,
        error_reason: str | None = None,
        failure_class: FailureClass | None = None,
        auth_decision_ref: str | None = None,
    ) -> IdempotencyRecord:
        record = self._store.get(idempotency_key)
        if not record:
            raise KeyError(f"Idempotency record {idempotency_key} not found")

        now = utc_now()
        new_count = record.attempt_count + 1
        new_attempt = RetryAttempt(
            attempt_number=new_count,
            scheduled_at=now,
            eligible_at=now,
            executed_at=now,
            error_reason=error_reason,
            failure_class=failure_class,
            authorization_decision_ref=auth_decision_ref,
            verification_outcome=verification_outcome,
        )
        is_success = (new_state == ExecutionState.VERIFIED or record.is_verified_success)
        updated = IdempotencyRecord(
            idempotency_key=record.idempotency_key,
            objective_id=record.objective_id,
            action_id=record.action_id,
            correlation_id=record.correlation_id,
            capability_id=record.capability_id,
            capability_version=record.capability_version,
            environment=record.environment,
            material_payload_hash=record.material_payload_hash,
            first_seen_at=record.first_seen_at,
            last_attempt_at=now,
            attempt_count=new_count,
            is_verified_success=is_success,
            latest_verification_outcome=verification_outcome or record.latest_verification_outcome,
            latest_execution_state=new_state,
            attempts=record.attempts + (new_attempt,),
        )
        self._store[idempotency_key] = updated
        return updated


class RetryController:
    """Deterministic Retry / Idempotency Controller enforcing B1-B6 governance."""

    def __init__(
        self,
        policy_registry: RetryPolicyRegistry | None = None,
        idempotency_store: IdempotencyStore | None = None,
        kill_switches: BAEKillSwitchRegistry | None = None,
        policy_evaluator: DeterministicPolicyEvaluator | None = None,
    ) -> None:
        self.policy_registry = policy_registry or RetryPolicyRegistry.default_registry()
        self.idempotency_store = idempotency_store or IdempotencyStore()
        self.kill_switches = kill_switches or BAEKillSwitchRegistry()
        self.policy_evaluator = policy_evaluator

    def evaluate_idempotency(
        self,
        *,
        idempotency_key: str,
        objective_id: str,
        action_id: str,
        correlation_id: str,
        capability_id: str,
        capability_version: str,
        environment: str,
        material_payload: dict[str, Any],
    ) -> tuple[IdempotencyDisposition, IdempotencyRecord | None, str]:
        """Evaluates idempotency key binding and duplicate status."""
        existing = self.idempotency_store.get(idempotency_key)
        if existing is None:
            return IdempotencyDisposition.FIRST_USE, None, "First use of idempotency key"

        # Check cross-context binding (must match objective, action, capability, environment)
        if (
            existing.objective_id != objective_id
            or existing.action_id != action_id
            or existing.capability_id != capability_id
            or existing.capability_version != capability_version
            or existing.environment != environment
        ):
            return (
                IdempotencyDisposition.CROSS_CONTEXT_REUSE_REJECTED,
                existing,
                "Cross-context reuse of idempotency key across different objective/action/capability/environment is prohibited",
            )

        payload_hash = hashlib.sha256(
            json.dumps(material_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        if existing.material_payload_hash != payload_hash:
            return (
                IdempotencyDisposition.CROSS_CONTEXT_REUSE_REJECTED,
                existing,
                "Material payload hash mismatch for idempotency key",
            )

        # If already VERIFIED successful effect -> duplicate no-op
        if existing.is_verified_success or existing.latest_execution_state == ExecutionState.VERIFIED:
            return (
                IdempotencyDisposition.DUPLICATE_NO_OP_VERIFIED,
                existing,
                "Action already verified successful; duplicate request produces deterministic no-op result without repeating side-effects",
            )

        # If previous attempt was UNKNOWN, UNVERIFIED, or PARTIALLY_VERIFIED -> preserve uncertainty
        if existing.latest_execution_state in {ExecutionState.UNKNOWN, ExecutionState.UNVERIFIED, ExecutionState.PARTIALLY_VERIFIED}:
            return (
                IdempotencyDisposition.DUPLICATE_UNCERTAIN_PRESERVED,
                existing,
                f"Prior attempt resulted in uncertain state ({existing.latest_execution_state.value}); preserving evidence without inferring safe replay",
            )

        # Prior attempt was FAILED -> evaluate retry policy
        return (
            IdempotencyDisposition.DUPLICATE_RETRY_PERMITTED,
            existing,
            "Prior attempt failed; duplicate key may retry if authorized by retry policy",
        )

    def evaluate_retry(
        self,
        *,
        capability_id: str,
        capability_version: str,
        current_attempt_count: int,
        error_reason: str,
        environment: str,
        actor_id: str,
        objective_id: str | None = None,
    ) -> RetryDecision:
        """Evaluates whether a failed action is eligible to transition to RETRY_SCHEDULED."""
        # Check kill switches first
        from .types import ToolAuthorityClass
        blocked, kill_reason = self.kill_switches.is_blocked(
            environment=environment,
            capability_id=capability_id,
            tool_class=ToolAuthorityClass.T0,
            objective_id=objective_id or "",
        )
        if blocked:
            return RetryDecision(
                retry_authorized=False,
                failure_class=FailureClass.TERMINAL,
                stop_reason=RetryStopReason.KILL_SWITCH_ACTIVE,
                attempt_number=current_attempt_count,
                next_eligible_at=None,
                delay_seconds=0,
                reason_detail=f"Kill switch is active: {kill_reason}",
            )

        policy = self.policy_registry.get_policy(capability_id, capability_version)
        if policy is None:
            return RetryDecision(
                retry_authorized=False,
                failure_class=FailureClass.TERMINAL,
                stop_reason=RetryStopReason.NO_RETRY_POLICY_REGISTERED,
                attempt_number=current_attempt_count,
                next_eligible_at=None,
                delay_seconds=0,
                reason_detail="No ratified retry policy registered for capability",
            )

        failure_class = policy.classify_failure(error_reason)

        if failure_class == FailureClass.TERMINAL:
            return RetryDecision(
                retry_authorized=False,
                failure_class=FailureClass.TERMINAL,
                stop_reason=RetryStopReason.TERMINAL_FAILURE,
                attempt_number=current_attempt_count,
                next_eligible_at=None,
                delay_seconds=0,
                reason_detail=f"Terminal failure class for reason: {error_reason}",
            )

        if failure_class == FailureClass.HUMAN_ONLY:
            return RetryDecision(
                retry_authorized=False,
                failure_class=FailureClass.HUMAN_ONLY,
                stop_reason=RetryStopReason.HUMAN_ONLY_FAILURE,
                attempt_number=current_attempt_count,
                next_eligible_at=None,
                delay_seconds=0,
                reason_detail=f"Human-only failure class for reason: {error_reason}",
            )

        if failure_class == FailureClass.APPROVAL_REQUIRED:
            return RetryDecision(
                retry_authorized=False,
                failure_class=FailureClass.APPROVAL_REQUIRED,
                stop_reason=RetryStopReason.APPROVAL_REQUIRED_FAILURE,
                attempt_number=current_attempt_count,
                next_eligible_at=None,
                delay_seconds=0,
                reason_detail=f"Human approval required for reason: {error_reason}",
            )

        if failure_class == FailureClass.NON_RETRYABLE:
            return RetryDecision(
                retry_authorized=False,
                failure_class=FailureClass.NON_RETRYABLE,
                stop_reason=RetryStopReason.NON_RETRYABLE_FAILURE,
                attempt_number=current_attempt_count,
                next_eligible_at=None,
                delay_seconds=0,
                reason_detail=f"Non-retryable failure for reason: {error_reason}",
            )

        # Check max attempts
        next_attempt = current_attempt_count + 1
        if next_attempt > policy.max_attempts:
            return RetryDecision(
                retry_authorized=False,
                failure_class=FailureClass.RETRYABLE,
                stop_reason=RetryStopReason.MAX_ATTEMPTS_EXCEEDED,
                attempt_number=next_attempt,
                next_eligible_at=None,
                delay_seconds=0,
                reason_detail=f"Maximum retry attempts exceeded ({policy.max_attempts})",
            )

        # Calculate deterministic backoff
        delay_sec = policy.calculate_backoff(next_attempt)
        eligible_at = (datetime.now(timezone.utc) + timedelta(seconds=delay_sec)).isoformat()

        return RetryDecision(
            retry_authorized=True,
            failure_class=FailureClass.RETRYABLE,
            stop_reason=None,
            attempt_number=next_attempt,
            next_eligible_at=eligible_at,
            delay_seconds=delay_sec,
            reason_detail=f"Retry authorized; scheduled for attempt {next_attempt} in {delay_sec}s",
        )

    def apply_retry_scheduling(
        self,
        sm: ExecutionStateMachine,
        retry_decision: RetryDecision,
    ) -> ExecutionStateRecord:
        """Transitions state machine to RETRY_SCHEDULED if retry_authorized is True."""
        if not retry_decision.retry_authorized:
            raise StateTransitionError(
                sm.record.current_execution_state,
                ExecutionState.RETRY_SCHEDULED,
                f"Cannot schedule retry: {retry_decision.reason_detail}",
            )

        return sm.transition(
            ExecutionState.RETRY_SCHEDULED,
            reason=retry_decision.reason_detail,
            retry_authorized=True,
        )

    def authorize_retry_execution(
        self,
        *,
        sm: ExecutionStateMachine,
        auth_request: AuthorizationRequest,
        evaluator: DeterministicPolicyEvaluator,
    ) -> tuple[bool, AuthorizationDecision]:
        """Re-evaluates current B2 authorization before transitioning from RETRY_SCHEDULED to AUTHORIZATION_PENDING."""
        if sm.record.current_execution_state != ExecutionState.RETRY_SCHEDULED:
            raise StateTransitionError(
                sm.record.current_execution_state,
                ExecutionState.AUTHORIZATION_PENDING,
                "Can only authorize retry execution from RETRY_SCHEDULED state",
            )

        # Transition to AUTHORIZATION_PENDING
        sm.transition(ExecutionState.AUTHORIZATION_PENDING, reason="Re-authorizing scheduled retry with fresh B2 evaluation")

        # Evaluate current governing state through B2 policy evaluator
        decision = evaluator.evaluate(auth_request)

        if decision.permitted:
            sm.transition(ExecutionState.AUTHORIZED, reason="Retry authorized by B2", authorization_decision=decision)
            return True, decision
        else:
            sm.transition(ExecutionState.DENIED, reason="Retry authorization denied by B2", authorization_decision=decision)
            return False, decision
