"""BAE Pilot 001 Control Types.

Defines the multi-dimensional governance model:
- L: Authority Class (L1, L2, L3-H, L3-X)
- M: Autonomy Maturity (M0, M1, M2, M3, M4, M5) - Maturity never overrides Authority Class.
- A: Human Approval Level (A0, A1, A2, A3, A4)
- T: Tool Authority Class (T0, T1, T2, T3, TX)
- Lifecycle States: DEFINED, REGISTERED, IMPLEMENTED, TESTED, CERTIFICATION_PENDING,
                    CERTIFIED, AUTHORIZED_FOR_ENVIRONMENT, SUSPENDED, RESTRICTED, RETIRED
- Waves: Wave 1 (Observe/Detect/Verify/Package/Escalate), Wave 2 (Task/Retry),
         Wave 3 (CRM Activity - Conditional), Wave 4 (Follow-up - Disabled Default)
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Any


class AuthorityClass(str, Enum):
    """L - Authority Class. Defines the permissible scope of autonomous action."""
    L1 = "L1"          # Autonomous Authority (bounded, deterministic execution permitted)
    L2 = "L2"          # Human Approval Required (requires human approval before execution)
    L3_H = "L3-H"      # Human-Only (absolutely reserved for human actor)
    L3_X = "L3-X"      # Absolutely Prohibited (never permitted for any system or agent)


class AutonomyMaturity(str, Enum):
    """M - Autonomy Maturity. Defines capability progression.
    
    Rule: Maturity NEVER overrides Authority Class L. There is no M6.
    """
    M0 = "M0"  # Manual
    M1 = "M1"  # Observe
    M2 = "M2"  # Assist
    M3 = "M3"  # Execute
    M4 = "M4"  # Orchestrate
    M5 = "M5"  # Goal-Directed Autonomy


class ApprovalLevel(str, Enum):
    """A - Human Approval Level required before execution."""
    A0 = "A0"  # No case approval required (pre-authorized under L1)
    A1 = "A1"  # Routine operational approval
    A2 = "A2"  # Elevated operational approval
    A3 = "A3"  # Project Owner approval
    A4 = "A4"  # External / Multi-party authority approval


class ToolAuthorityClass(str, Enum):
    """T - Technical Tool Authority Class enforced through canonical Tool Gateway."""
    T0 = "T0"  # Read-only / Query
    T1 = "T1"  # Safe stateful transformation / compute
    T2 = "T2"  # Specifically authorized bounded write
    T3 = "T3"  # High-impact write / External mutation (requires elevated approval)
    TX = "TX"  # Prohibited tool invocation


class CapabilityLifecycleState(str, Enum):
    """Governed lifecycle state of a capability."""
    DEFINED = "DEFINED"
    REGISTERED = "REGISTERED"
    IMPLEMENTED = "IMPLEMENTED"
    TESTED = "TESTED"
    CERTIFICATION_PENDING = "CERTIFICATION_PENDING"
    CERTIFIED = "CERTIFIED"
    AUTHORIZED_FOR_ENVIRONMENT = "AUTHORIZED_FOR_ENVIRONMENT"
    SUSPENDED = "SUSPENDED"
    RESTRICTED = "RESTRICTED"
    RETIRED = "RETIRED"


class PilotWave(str, Enum):
    """BAE Pilot 001 rollout wave assignment."""
    WAVE_1 = "WAVE_1"  # Observe, Detect, Verify, Package, Escalate
    WAVE_2 = "WAVE_2"  # Task, Retry
    WAVE_3 = "WAVE_3"  # CRM Activity (Conditional)
    WAVE_4 = "WAVE_4"  # Customer Communication (Disabled Default)


class ObjectiveState(str, Enum):
    """Execution objective lifecycle state."""
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED_APPROVAL = "BLOCKED_APPROVAL"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"
    SUSPENDED = "SUSPENDED"


class TaskState(str, Enum):
    """Individual task execution state."""
    PENDING = "PENDING"
    AUTHORIZING = "AUTHORIZING"
    EXECUTING = "EXECUTING"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"
    VERIFIED_SUCCESS = "VERIFIED_SUCCESS"
    VERIFIED_FAILURE = "VERIFIED_FAILURE"
    RETRY_PENDING = "RETRY_PENDING"
    ESCALATED = "ESCALATED"
    DENIED = "DENIED"
    SUSPENDED = "SUSPENDED"


class VerificationState(str, Enum):
    """System-of-Record verification state."""
    UNVERIFIED = "UNVERIFIED"
    PENDING_SOR_QUERY = "PENDING_SOR_QUERY"
    VERIFIED_MATCH = "VERIFIED_MATCH"
    DISCREPANCY_DETECTED = "DISCREPANCY_DETECTED"
    VERIFICATION_TIMED_OUT = "VERIFICATION_TIMED_OUT"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"


class KillSwitchScope(str, Enum):
    """Scope of emergency kill-switch or suspension."""
    GLOBAL = "GLOBAL"
    ENVIRONMENT = "ENVIRONMENT"
    CAPABILITY = "CAPABILITY"
    TOOL = "TOOL"
    OBJECTIVE = "OBJECTIVE"


@dataclass(frozen=True)
class LMATReconciliation:
    """Evaluation result of the multidimensional L/M/A/T governance check."""
    permitted: bool
    requires_approval: bool
    approval_level: ApprovalLevel | None
    authority_class: AuthorityClass | None
    current_certified_maturity: AutonomyMaturity | None
    tool_authority: ToolAuthorityClass | None
    reason: str

    @classmethod
    def evaluate(
        cls,
        authority: AuthorityClass | None,
        current_certified_maturity: AutonomyMaturity | None,
        approval: ApprovalLevel | None,
        tool: ToolAuthorityClass | None,
        *,
        specifically_authorized_bounded_write: bool = False,
        lifecycle_state: CapabilityLifecycleState = CapabilityLifecycleState.DEFINED,
        is_certified: bool = False,
    ) -> "LMATReconciliation":
        """Reconcile L, M, A, and T dimensions deterministically.
        
        Core Invariants:
        1. Prohibited (TX or L3-X) is always denied.
        2. Unresolved authority/tool class (None) cannot execute autonomously.
        3. Uncertified capability or current_certified_maturity is None cannot execute autonomously.
        4. Inactive / un-authorized lifecycle state cannot execute.
        5. L3-H is human-only (autonomous execution prohibited).
        6. Maturity NEVER overrides Authority Class L.
        7. T2 requires specifically_authorized_bounded_write = True.
        8. L2 requires human approval.
        9. L1 with T0/T1/T2(authorized) and A0 permitted under valid certification and lifecycle state.
        """
        if tool == ToolAuthorityClass.TX or authority == AuthorityClass.L3_X:
            return cls(
                permitted=False,
                requires_approval=False,
                approval_level=approval,
                authority_class=authority,
                current_certified_maturity=current_certified_maturity,
                tool_authority=tool,
                reason="Prohibited authority class L3-X or tool class TX",
            )

        if authority is None or tool is None or approval is None:
            return cls(
                permitted=False,
                requires_approval=False,
                approval_level=approval,
                authority_class=authority,
                current_certified_maturity=current_certified_maturity,
                tool_authority=tool,
                reason="Classification is conditional or unresolved",
            )

        if authority == AuthorityClass.L3_H:
            return cls(
                permitted=False,
                requires_approval=True,
                approval_level=approval,
                authority_class=authority,
                current_certified_maturity=current_certified_maturity,
                tool_authority=tool,
                reason="L3-H reserved for Human-Only execution",
            )

        if not is_certified or current_certified_maturity is None:
            return cls(
                permitted=False,
                requires_approval=False,
                approval_level=approval,
                authority_class=authority,
                current_certified_maturity=current_certified_maturity,
                tool_authority=tool,
                reason="Capability lacks active certification or current certified maturity",
            )

        if lifecycle_state not in {CapabilityLifecycleState.CERTIFIED, CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT}:
            return cls(
                permitted=False,
                requires_approval=False,
                approval_level=approval,
                authority_class=authority,
                current_certified_maturity=current_certified_maturity,
                tool_authority=tool,
                reason=f"Lifecycle state {lifecycle_state} not eligible for autonomous execution",
            )

        if tool == ToolAuthorityClass.T2 and not specifically_authorized_bounded_write:
            return cls(
                permitted=False,
                requires_approval=False,
                approval_level=approval,
                authority_class=authority,
                current_certified_maturity=current_certified_maturity,
                tool_authority=tool,
                reason="Tool class T2 requires specific bounded write authorization",
            )

        if authority == AuthorityClass.L2 or approval != ApprovalLevel.A0:
            return cls(
                permitted=False,
                requires_approval=True,
                approval_level=approval,
                authority_class=authority,
                current_certified_maturity=current_certified_maturity,
                tool_authority=tool,
                reason="Human approval required (L2 or explicit approval level)",
            )

        if authority == AuthorityClass.L1 and tool in {ToolAuthorityClass.T0, ToolAuthorityClass.T1, ToolAuthorityClass.T2} and approval == ApprovalLevel.A0:
            return cls(
                permitted=True,
                requires_approval=False,
                approval_level=ApprovalLevel.A0,
                authority_class=authority,
                current_certified_maturity=current_certified_maturity,
                tool_authority=tool,
                reason="Autonomous execution permitted under L1/T0-T2/A0",
            )

        return cls(
            permitted=False,
            requires_approval=False,
            approval_level=approval,
            authority_class=authority,
            current_certified_maturity=current_certified_maturity,
            tool_authority=tool,
            reason="Unresolved authority configuration",
        )
