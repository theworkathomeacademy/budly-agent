"""BAE Pilot 001 Schema Definitions.

Data structures for:
- CapabilityRecord: Governed capability tracking with L/M/A/T, certification status, wave, and lifecycle state.
- ExecutionObjective: High-level operational objective with correlation tracking.
- TaskRecord: Discrete step within an objective.
- VerificationRecord: System-of-Record verification proof comparing provider vs SoR state.
- EscalationPackage: Structured dossier for human review (A1–A4 approvals).
- KillSwitchState: Emergency stop & suspension tracking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    KillSwitchScope,
    ObjectiveState,
    PilotWave,
    TaskState,
    ToolAuthorityClass,
    VerificationState,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SchemaValidationError(ValueError):
    """Raised when a BAE control schema invariant is violated."""
    pass


@dataclass(frozen=True)
class CapabilityRecord:
    """Ratified capability registry record."""
    capability_id: str
    capability_version: str
    capability_name: str
    wave: PilotWave
    authority_class: AuthorityClass | None
    current_certified_maturity: AutonomyMaturity | None
    target_pilot_entry_maturity: AutonomyMaturity | None
    maximum_governable_maturity: AutonomyMaturity | None
    approval_level: ApprovalLevel | None
    tool_authority: ToolAuthorityClass | None
    lifecycle_state: CapabilityLifecycleState
    specifically_authorized_bounded_write: bool = False
    certification_signature: str | None = None
    certified_at: str | None = None
    certified_by: str | None = None
    classification_state: str = "RESOLVED"  # RESOLVED or CONDITIONAL
    executable: bool = False
    allowed_environments: frozenset[str] = frozenset({"automated_test", "development", "prototype"})
    allowed_purposes: frozenset[str] = frozenset()
    allowed_channels: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not re.fullmatch(r"BAE-[A-Z]{3,4}-[A-Z]{3,8}-[0-9]{3}", self.capability_id):
            raise SchemaValidationError(f"Invalid capability_id format: {self.capability_id}")
        if not re.fullmatch(r"[0-9]+\.[0-9]+(\.[0-9]+)?", self.capability_version):
            raise SchemaValidationError(f"Invalid capability_version: {self.capability_version}")
        if self.executable and self.lifecycle_state not in {CapabilityLifecycleState.CERTIFIED, CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT}:
            raise SchemaValidationError(f"Capability cannot be executable with lifecycle_state {self.lifecycle_state}")
        if self.executable and (not self.certification_signature or self.current_certified_maturity is None):
            raise SchemaValidationError("Capability cannot be executable without a valid certification_signature and current_certified_maturity")
        if self.authority_class in {AuthorityClass.L3_H, AuthorityClass.L3_X} and self.executable:
            raise SchemaValidationError(f"Capability with authority class {self.authority_class} cannot be marked executable")
        if self.tool_authority == ToolAuthorityClass.TX and self.executable:
            raise SchemaValidationError("Capability with tool authority TX cannot be marked executable")
        if self.wave == PilotWave.WAVE_4 and self.executable:
            raise SchemaValidationError("Wave 4 capability must remain disabled and non-executable")


@dataclass(frozen=True)
class ExecutionObjective:
    """High-level BAE operational objective."""
    objective_id: str
    correlation_id: str
    objective_type: str
    target_system: str
    created_at: str
    state: ObjectiveState = ObjectiveState.CREATED
    parameters: dict[str, Any] = field(default_factory=dict)
    assigned_wave: PilotWave = PilotWave.WAVE_1
    escalation_reason: str | None = None

    def __post_init__(self) -> None:
        for name, val in (("objective_id", self.objective_id), ("correlation_id", self.correlation_id)):
            try:
                UUID(val)
            except (ValueError, TypeError, AttributeError) as exc:
                raise SchemaValidationError(f"{name} must be a valid UUID") from exc
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", self.objective_type):
            raise SchemaValidationError(f"Invalid objective_type: {self.objective_type}")


@dataclass(frozen=True)
class TaskRecord:
    """Discrete unit of work within a BAE objective."""
    task_id: str
    objective_id: str
    correlation_id: str
    step_number: int
    capability_id: str
    capability_version: str
    state: TaskState
    input_payload: dict[str, Any]
    idempotency_key: str
    created_at: str
    executed_at: str | None = None
    completed_at: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    result_payload: dict[str, Any] | None = None
    error_classification: str | None = None
    verification_id: str | None = None

    def __post_init__(self) -> None:
        for name, val in (("task_id", self.task_id), ("objective_id", self.objective_id), ("correlation_id", self.correlation_id)):
            try:
                UUID(val)
            except (ValueError, TypeError, AttributeError) as exc:
                raise SchemaValidationError(f"{name} must be a valid UUID") from exc
        if self.step_number < 1:
            raise SchemaValidationError("step_number must be >= 1")
        if self.retry_count < 0 or self.retry_count > self.max_retries:
            raise SchemaValidationError(f"retry_count ({self.retry_count}) must be between 0 and max_retries ({self.max_retries})")
        if not self.idempotency_key or len(self.idempotency_key) > 160:
            raise SchemaValidationError("idempotency_key must be non-empty and <= 160 chars")


@dataclass(frozen=True)
class VerificationRecord:
    """Proof of System-of-Record verification."""
    verification_id: str
    task_id: str
    objective_id: str
    correlation_id: str
    target_sor: str  # e.g., "postgresql_primary", "woocommerce_api"
    query_reference: str
    expected_state: dict[str, Any]
    observed_state: dict[str, Any] | None
    state: VerificationState
    verified_at: str | None
    evidence_reference: str | None
    discrepancy_details: str | None = None

    def __post_init__(self) -> None:
        for name, val in (("verification_id", self.verification_id), ("task_id", self.task_id), ("objective_id", self.objective_id), ("correlation_id", self.correlation_id)):
            try:
                UUID(val)
            except (ValueError, TypeError, AttributeError) as exc:
                raise SchemaValidationError(f"{name} must be a valid UUID") from exc
        if self.state == VerificationState.VERIFIED_MATCH and (not self.observed_state or not self.evidence_reference):
            raise SchemaValidationError("VERIFIED_MATCH requires observed_state and evidence_reference")


@dataclass(frozen=True)
class EscalationPackage:
    """Complete, self-contained dossier for human review."""
    escalation_id: str
    objective_id: str
    task_id: str | None
    correlation_id: str
    required_approval_level: ApprovalLevel
    authority_class: AuthorityClass
    reason_code: str
    summary: str
    context_data: dict[str, Any]
    evidence_references: tuple[str, ...]
    created_at: str
    status: str = "OPEN"  # OPEN, APPROVED, REJECTED, EXPIRED
    decision_by: str | None = None
    decided_at: str | None = None
    decision_rationale: str | None = None

    def __post_init__(self) -> None:
        for name, val in (("escalation_id", self.escalation_id), ("objective_id", self.objective_id), ("correlation_id", self.correlation_id)):
            try:
                UUID(val)
            except (ValueError, TypeError, AttributeError) as exc:
                raise SchemaValidationError(f"{name} must be a valid UUID") from exc
        if self.task_id is not None:
            try:
                UUID(self.task_id)
            except (ValueError, TypeError, AttributeError) as exc:
                raise SchemaValidationError("task_id must be a valid UUID if provided") from exc
        if not 10 <= len(self.summary) <= 1000:
            raise SchemaValidationError("summary must be between 10 and 1000 characters")
        if self.required_approval_level == ApprovalLevel.A0:
            raise SchemaValidationError("Escalation requires ApprovalLevel > A0")


@dataclass(frozen=True)
class KillSwitchState:
    """Status record for a kill switch or suspension rule."""
    switch_id: str
    scope: KillSwitchScope
    target_identifier: str  # e.g., "GLOBAL", "development", "BAE-OPS-TASK-001", "OBJ-123"
    is_active: bool
    triggered_at: str
    triggered_by: str
    reason: str

    def __post_init__(self) -> None:
        if not self.switch_id or not self.target_identifier:
            raise SchemaValidationError("switch_id and target_identifier cannot be empty")
        if not 5 <= len(self.reason) <= 500:
            raise SchemaValidationError("reason must be between 5 and 500 characters")
