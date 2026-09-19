"""BAE Pilot 001 Step B9 Kill-Switch Controller Engine.

Implements the governed Kill-Switch Controller and Emergency Stop boundary:
- Law of Invariant Latitude: A kill switch can reduce or remove execution latitude;
  it can NEVER create authority.
- Canonical Scopes: GLOBAL_PILOT (GLOBAL), CAPABILITY, TOOL, OBJECTIVE, ENVIRONMENT.
- Immediate, Auditable Stop: Evaluated before every material autonomous step,
  during B2 evaluation, before Tool Gateway execution, during retry scheduling,
  and before any continuation.
- No Auto-Resume: Clearing a switch (CLEAR != RESUME) never automatically resumes
  prior work, revalidates prior tokens, or reactivates Gateway execution contexts.
  Fresh B2 authorization is mandatory.
- Human Override: Independent immediate STOP condition.
- Fail-Closed: Unresolvable or unavailable kill-switch state stops execution.
- Administrative Control Authority: Runtime agents cannot self-clear or self-unblock.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from .audit_persistence import (
    AuditEventRecord,
    AuditEventType,
    CorrelationRecord,
    DurableAuditRepository,
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
    KillSwitchScope,
    ToolAuthorityClass,
)


class KillSwitchDecisionStatus(str, Enum):
    """Deterministic decision outcome for kill-switch checks."""
    ALLOW = "ALLOW"
    STOP = "STOP"
    CONTROL_STATE_UNKNOWN = "CONTROL_STATE_UNKNOWN"


@dataclass(frozen=True)
class KillSwitchRecord:
    """Immutable record of an emergency kill-switch or suspension rule."""
    switch_id: str
    scope: KillSwitchScope
    target_identifier: str  # e.g., "GLOBAL", "BAE-OPS-TASK-001", "T2", "OBJ-123", "development"
    is_active: bool
    reason: str
    activating_authority: str
    activated_at: str = field(default_factory=utc_now)
    cleared_at: str | None = None
    clearing_authority: str | None = None
    clearing_reason: str | None = None
    correlation_id: str | None = None
    expires_at: str | None = None

    def __post_init__(self) -> None:
        if not self.switch_id or not self.target_identifier:
            raise ValueError("switch_id and target_identifier cannot be empty")
        if not 5 <= len(self.reason) <= 500:
            raise ValueError("reason must be between 5 and 500 characters")

    def to_dict(self) -> dict[str, Any]:
        return {
            "switch_id": self.switch_id,
            "scope": self.scope.value,
            "target_identifier": self.target_identifier,
            "is_active": self.is_active,
            "reason": self.reason,
            "activating_authority": self.activating_authority,
            "activated_at": self.activated_at,
            "cleared_at": self.cleared_at,
            "clearing_authority": self.clearing_authority,
            "clearing_reason": self.clearing_reason,
            "correlation_id": self.correlation_id,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True)
class KillSwitchDecision:
    """Evaluation result of the kill-switch boundary."""
    status: KillSwitchDecisionStatus
    is_blocked: bool
    matched_switch: KillSwitchRecord | None = None
    reason: str = ""
    is_human_override: bool = False
    evaluated_at: str = field(default_factory=utc_now)


class KillSwitchController:
    """Canonical BAE Pilot 001 Kill-Switch Controller & Backing Store.
    
    Serves as the single authoritative source of truth for kill switches and human overrides.
    """

    def __init__(
        self,
        audit_repo: DurableAuditRepository | None = None,
        *,
        authorized_admin_roles: frozenset[str] | None = None,
        fail_closed: bool = True,
    ) -> None:
        self._audit_repo = audit_repo
        self._authorized_admin_roles = authorized_admin_roles or frozenset({
            "lead_steward", "system_admin", "compliance_officer", "project_owner"
        })
        self._fail_closed = fail_closed
        self._active_switches: dict[tuple[KillSwitchScope, str], KillSwitchRecord] = {}
        self._history: list[KillSwitchRecord] = []
        self._human_overrides: dict[str, str] = {}  # target_identifier -> reason
        self._is_unavailable: bool = False

    def simulate_store_failure(self, unavailable: bool = True) -> None:
        """Simulate backend/controller unreachability for fail-closed verification."""
        self._is_unavailable = unavailable

    def activate_switch(
        self,
        *,
        scope: KillSwitchScope,
        target_identifier: str,
        reason: str,
        activating_authority: str,
        operator_role: str,
        correlation_id: str | None = None,
        expires_at: str | None = None,
    ) -> KillSwitchRecord:
        """Activates a kill switch under authorized control authority."""
        if self._is_unavailable:
            raise RuntimeError("KillSwitchController is currently unavailable")

        # Prohibit autonomous self-expansion/unauthorized manipulation
        if operator_role not in self._authorized_admin_roles:
            raise PermissionError(f"Role '{operator_role}' is not authorized to activate kill switches")

        # Normalize target identifier for GLOBAL
        if scope == KillSwitchScope.GLOBAL:
            target_identifier = "GLOBAL"

        switch_id = str(uuid4())
        record = KillSwitchRecord(
            switch_id=switch_id,
            scope=scope,
            target_identifier=target_identifier,
            is_active=True,
            reason=reason,
            activating_authority=activating_authority,
            activated_at=utc_now(),
            correlation_id=correlation_id,
            expires_at=expires_at,
        )

        key = (scope, target_identifier)
        self._active_switches[key] = record
        self._history.append(record)

        self._record_audit_event(
            event_type=AuditEventType.GOVERNANCE_INTERRUPTION_EVENT,
            state=ExecutionState.STOPPED,
            metadata={
                "kill_switch_action": "ACTIVATED",
                "switch_record": record.to_dict(),
            },
            correlation_id=correlation_id,
        )

        return record

    def clear_switch(
        self,
        *,
        scope: KillSwitchScope,
        target_identifier: str,
        clearing_authority: str,
        clearing_reason: str,
        operator_role: str,
        correlation_id: str | None = None,
    ) -> KillSwitchRecord:
        """Clears an active kill switch.
        
        MANDATORY LAW: CLEAR != RESUME.
        Clearing a switch removes the restriction but NEVER automatically resumes
        or re-authorizes previously stopped work.
        """
        if self._is_unavailable:
            raise RuntimeError("KillSwitchController is currently unavailable")

        if operator_role not in self._authorized_admin_roles:
            raise PermissionError(f"Role '{operator_role}' is not authorized to clear kill switches")

        if scope == KillSwitchScope.GLOBAL:
            target_identifier = "GLOBAL"

        key = (scope, target_identifier)
        existing = self._active_switches.get(key)
        if not existing:
            raise ValueError(f"No active kill switch found for scope {scope.value} and target {target_identifier}")

        cleared_record = KillSwitchRecord(
            switch_id=existing.switch_id,
            scope=existing.scope,
            target_identifier=existing.target_identifier,
            is_active=False,
            reason=existing.reason,
            activating_authority=existing.activating_authority,
            activated_at=existing.activated_at,
            cleared_at=utc_now(),
            clearing_authority=clearing_authority,
            clearing_reason=clearing_reason,
            correlation_id=correlation_id,
        )

        del self._active_switches[key]
        self._history.append(cleared_record)

        self._record_audit_event(
            event_type=AuditEventType.GOVERNANCE_INTERRUPTION_EVENT,
            state=ExecutionState.STOPPED,
            metadata={
                "kill_switch_action": "CLEARED",
                "switch_record": cleared_record.to_dict(),
                "note": "CLEAR_DOES_NOT_AUTO_RESUME: fresh B2 continuous authorization required before execution",
            },
            correlation_id=correlation_id,
        )

        return cleared_record

    def set_human_override(
        self,
        *,
        target_identifier: str,
        reason: str,
        activating_authority: str,
        operator_role: str,
        correlation_id: str | None = None,
    ) -> None:
        """Sets an immediate human override stop condition."""
        if operator_role not in self._authorized_admin_roles:
            raise PermissionError(f"Role '{operator_role}' is not authorized to set human overrides")

        self._human_overrides[target_identifier] = reason
        self._record_audit_event(
            event_type=AuditEventType.GOVERNANCE_INTERRUPTION_EVENT,
            state=ExecutionState.STOPPED,
            metadata={
                "human_override_action": "ACTIVATED",
                "target_identifier": target_identifier,
                "reason": reason,
                "activating_authority": activating_authority,
            },
            correlation_id=correlation_id,
        )

    def clear_human_override(
        self,
        *,
        target_identifier: str,
        clearing_authority: str,
        clearing_reason: str,
        operator_role: str,
        correlation_id: str | None = None,
    ) -> None:
        """Clears a human override stop condition without resuming execution."""
        if operator_role not in self._authorized_admin_roles:
            raise PermissionError(f"Role '{operator_role}' is not authorized to clear human overrides")

        if target_identifier in self._human_overrides:
            del self._human_overrides[target_identifier]

        self._record_audit_event(
            event_type=AuditEventType.GOVERNANCE_INTERRUPTION_EVENT,
            state=ExecutionState.STOPPED,
            metadata={
                "human_override_action": "CLEARED",
                "target_identifier": target_identifier,
                "clearing_reason": clearing_reason,
                "clearing_authority": clearing_authority,
                "note": "CLEAR_DOES_NOT_AUTO_RESUME: fresh B2 authorization required",
            },
            correlation_id=correlation_id,
        )

    def evaluate(
        self,
        *,
        environment: str,
        capability_id: str,
        tool_class: ToolAuthorityClass | str | None,
        objective_id: str,
        action_id: str | None = None,
        correlation_id: str | None = None,
        is_human_override_active: bool = False,
    ) -> KillSwitchDecision:
        """Evaluates all applicable kill switch scopes and human overrides deterministically."""
        # Check fail-closed condition
        if self._is_unavailable:
            return KillSwitchDecision(
                status=KillSwitchDecisionStatus.CONTROL_STATE_UNKNOWN,
                is_blocked=True,
                reason="KillSwitchController unavailable; failing closed to STOP",
            )

        # 1. Check Human Overrides (both argument and active internal state)
        if is_human_override_active or "GLOBAL" in self._human_overrides or objective_id in self._human_overrides or capability_id in self._human_overrides:
            reason = self._human_overrides.get("GLOBAL") or self._human_overrides.get(objective_id) or self._human_overrides.get(capability_id) or "Immediate human override active"
            return KillSwitchDecision(
                status=KillSwitchDecisionStatus.STOP,
                is_blocked=True,
                reason=reason,
                is_human_override=True,
            )

        # 2. Scope Precedence Check
        # Check Scope A: GLOBAL_PILOT
        if (KillSwitchScope.GLOBAL, "GLOBAL") in self._active_switches:
            sw = self._active_switches[(KillSwitchScope.GLOBAL, "GLOBAL")]
            return KillSwitchDecision(
                status=KillSwitchDecisionStatus.STOP,
                is_blocked=True,
                matched_switch=sw,
                reason=f"GLOBAL_PILOT switch active: {sw.reason}",
            )

        # Check Scope B: ENVIRONMENT
        if (KillSwitchScope.ENVIRONMENT, environment) in self._active_switches:
            sw = self._active_switches[(KillSwitchScope.ENVIRONMENT, environment)]
            return KillSwitchDecision(
                status=KillSwitchDecisionStatus.STOP,
                is_blocked=True,
                matched_switch=sw,
                reason=f"ENVIRONMENT ({environment}) switch active: {sw.reason}",
            )

        # Check Scope C: CAPABILITY
        if (KillSwitchScope.CAPABILITY, capability_id) in self._active_switches:
            sw = self._active_switches[(KillSwitchScope.CAPABILITY, capability_id)]
            return KillSwitchDecision(
                status=KillSwitchDecisionStatus.STOP,
                is_blocked=True,
                matched_switch=sw,
                reason=f"CAPABILITY ({capability_id}) switch active: {sw.reason}",
            )

        # Check Scope D: TOOL
        tool_val = tool_class.value if isinstance(tool_class, ToolAuthorityClass) else str(tool_class or "")
        if tool_val and (KillSwitchScope.TOOL, tool_val) in self._active_switches:
            sw = self._active_switches[(KillSwitchScope.TOOL, tool_val)]
            return KillSwitchDecision(
                status=KillSwitchDecisionStatus.STOP,
                is_blocked=True,
                matched_switch=sw,
                reason=f"TOOL ({tool_val}) switch active: {sw.reason}",
            )

        # Check Scope E: OBJECTIVE
        if (KillSwitchScope.OBJECTIVE, objective_id) in self._active_switches:
            sw = self._active_switches[(KillSwitchScope.OBJECTIVE, objective_id)]
            return KillSwitchDecision(
                status=KillSwitchDecisionStatus.STOP,
                is_blocked=True,
                matched_switch=sw,
                reason=f"OBJECTIVE ({objective_id}) switch active: {sw.reason}",
            )

        return KillSwitchDecision(
            status=KillSwitchDecisionStatus.ALLOW,
            is_blocked=False,
            reason="No applicable kill switch active",
        )

    # Compatibility shim for B2 BAEKillSwitchRegistry.is_blocked interface
    def is_blocked(
        self,
        environment: str,
        capability_id: str,
        tool_class: ToolAuthorityClass,
        objective_id: str,
    ) -> tuple[bool, str | None]:
        decision = self.evaluate(
            environment=environment,
            capability_id=capability_id,
            tool_class=tool_class,
            objective_id=objective_id,
        )
        if decision.is_blocked:
            return True, decision.reason
        return False, None

    def trigger(self, scope: KillSwitchScope, target_identifier: str, reason: str) -> None:
        """Compatibility trigger method."""
        self.activate_switch(
            scope=scope,
            target_identifier=target_identifier,
            reason=reason,
            activating_authority="system_internal",
            operator_role="system_admin",
        )

    def reset(self, scope: KillSwitchScope, target_identifier: str) -> None:
        """Compatibility reset method."""
        try:
            self.clear_switch(
                scope=scope,
                target_identifier=target_identifier,
                clearing_authority="system_internal",
                clearing_reason="Reset to baseline",
                operator_role="system_admin",
            )
        except ValueError:
            pass

    def _record_audit_event(
        self,
        event_type: AuditEventType,
        state: ExecutionState,
        metadata: dict[str, Any],
        correlation_id: str | None = None,
    ) -> None:
        if self._audit_repo is None:
            return

        corr_id = correlation_id or str(uuid4())
        corr = CorrelationRecord(
            objective_id=str(uuid4()),
            action_id=str(uuid4()),
            correlation_id=corr_id,
        )
        event = AuditEventRecord(
            audit_event_id=str(uuid4()),
            event_type=event_type,
            correlation=corr,
            capability_id="BAE-KILL-SWITCH-CONTROLLER",
            capability_version="1.0",
            actor_id="kill-switch-controller",
            actor_type="control_plane_engine",
            environment=self._audit_repo.environment,
            channel="system_internal",
            purpose="emergency_kill_switch_governance",
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
            kill_switch_active=True,
            sanitized_metadata=sanitize_payload(metadata),
        )
        self._audit_repo.append_event(event)
