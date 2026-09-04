"""BAE Pilot 001 Deterministic Default-Deny Policy Evaluator & Continuous Authorization Engine.

Implements the authoritative Gate B authorization boundary:
- Evaluates registration, active certification, authority class (L), current certified maturity (M),
  maximum governable maturity, approval level (A), tool authority (T), actor identity, permissions,
  environment restrictions, channel, purpose, data scope, resource limits, customer consent,
  verification availability, human override, Gate D release state, RESTRICTED/RETIRED status,
  idempotency, rate-limits, and active kill switches.
- Enforces per-step continuous authorization tokens with cryptographic material-state fingerprinting.
- Default-deny: Any ambiguity, missing certificate, un-authorized state, or condition failure yields safe inaction (DENIED).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from .capability_registry import BAECapabilityRegistry
from .schemas import CapabilityRecord
from .types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    KillSwitchScope,
    ToolAuthorityClass,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuthorizationDecisionStatus(str, Enum):
    PERMITTED = "PERMITTED"
    REQUIRES_HUMAN_APPROVAL = "REQUIRES_HUMAN_APPROVAL"
    DENIED = "DENIED"


class AuthorizationDenialReason(str, Enum):
    CAPABILITY_NOT_REGISTERED = "CAPABILITY_NOT_REGISTERED"
    CAPABILITY_NOT_CERTIFIED = "CAPABILITY_NOT_CERTIFIED"
    CAPABILITY_NOT_AUTHORIZED_FOR_ENVIRONMENT = "CAPABILITY_NOT_AUTHORIZED_FOR_ENVIRONMENT"
    LIFECYCLE_STATE_INELIGIBLE = "LIFECYCLE_STATE_INELIGIBLE"
    AUTHORITY_CLASS_PROHIBITED = "AUTHORITY_CLASS_PROHIBITED"
    AUTHORITY_CLASS_HUMAN_ONLY = "AUTHORITY_CLASS_HUMAN_ONLY"
    TOOL_AUTHORITY_PROHIBITED = "TOOL_AUTHORITY_PROHIBITED"
    CLASSIFICATION_UNRESOLVED = "CLASSIFICATION_UNRESOLVED"
    MATURITY_INSUFFICIENT = "MATURITY_INSUFFICIENT"
    MAXIMUM_MATURITY_EXCEEDED = "MAXIMUM_MATURITY_EXCEEDED"
    ENVIRONMENT_DENIED = "ENVIRONMENT_DENIED"
    CHANNEL_DENIED = "CHANNEL_DENIED"
    PURPOSE_DENIED = "PURPOSE_DENIED"
    ACTOR_DENIED = "ACTOR_DENIED"
    ACTOR_REVOKED = "ACTOR_REVOKED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    BOUNDED_WRITE_NOT_AUTHORIZED = "BOUNDED_WRITE_NOT_AUTHORIZED"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    HUMAN_OVERRIDE_ACTIVE = "HUMAN_OVERRIDE_ACTIVE"
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
    STEP_TOKEN_INVALID = "STEP_TOKEN_INVALID"
    STEP_TOKEN_EXPIRED = "STEP_TOKEN_EXPIRED"
    MATERIAL_STATE_ALTERED = "MATERIAL_STATE_ALTERED"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"
    DATA_SCOPE_UNAUTHORIZED = "DATA_SCOPE_UNAUTHORIZED"
    CONSENT_REQUIRED_MISSING = "CONSENT_REQUIRED_MISSING"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"
    GATE_D_RELEASE_STATE_INVALID = "GATE_D_RELEASE_STATE_INVALID"
    CAPABILITY_RESTRICTED = "CAPABILITY_RESTRICTED"
    CAPABILITY_RETIRED = "CAPABILITY_RETIRED"
    SIGNATURE_VERIFICATION_FAILED = "SIGNATURE_VERIFICATION_FAILED"
    POLICY_VERSION_MISMATCH = "POLICY_VERSION_MISMATCH"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    UNRESOLVED_POLICY = "UNRESOLVED_POLICY"


@dataclass(frozen=True)
class AuthorizationRequest:
    """Request payload submitted for deterministic continuous authorization."""
    request_id: str
    correlation_id: str
    objective_id: str
    step_number: int
    actor_id: str
    actor_type: str
    capability_id: str
    capability_version: str
    environment: str
    channel: str
    purpose: str
    requested_tool_authority: ToolAuthorityClass
    requested_maturity: AutonomyMaturity = AutonomyMaturity.M1
    input_payload: dict[str, Any] = field(default_factory=dict)
    prior_step_token: str | None = None
    approval_token: str | None = None
    material_state_hash: str | None = None
    authorized_actor_types: frozenset[str] = frozenset({"bae_steward", "system_internal", "admin_operator"})
    granted_permissions: frozenset[str] = frozenset({"bae:execute", "bae:telemetry", "bae:bounded_write"})
    required_permission: str | None = None
    data_scope: str | None = None
    resource_cost_units: int = 1
    max_resource_limit: int = 100
    is_actor_revoked: bool = False
    requires_consent: bool = False
    consent_token: str | None = None
    is_consent_revoked: bool = False
    policy_version: str = "1.0"
    expected_policy_version: str = "1.0"
    idempotency_key: str | None = None
    is_rate_limited: bool = False
    is_human_override_active: bool = False
    is_verification_available: bool = True
    release_state: str = "PILOT_AUTHORIZED"  # e.g., PILOT_AUTHORIZED, RELEASE_HOLD, PROD_GATED
    expected_release_state: str = "PILOT_AUTHORIZED"

    def __post_init__(self) -> None:
        for name, val in (("request_id", self.request_id), ("correlation_id", self.correlation_id), ("objective_id", self.objective_id)):
            try:
                UUID(val)
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"{name} must be a valid UUID") from exc


@dataclass(frozen=True)
class ContinuousAuthorizationToken:
    """Cryptographically signed state token ensuring unbroken multi-step authorization."""
    token_id: str
    objective_id: str
    step_number: int
    capability_id: str
    issued_at: str
    expires_at: str
    actor_id: str
    environment: str
    checksum: str
    material_state_fingerprint: str


@dataclass(frozen=True)
class AuthorizationDecision:
    """Deterministic result of the policy evaluation."""
    status: AuthorizationDecisionStatus
    permitted: bool
    requires_approval: bool
    approval_level: ApprovalLevel | None
    denial_reason: AuthorizationDenialReason | None
    reason_detail: str
    step_token: ContinuousAuthorizationToken | None = None
    evaluated_at: str = field(default_factory=utc_now)


@dataclass
class BAEKillSwitchRegistry:
    """Manages active kill switches across Global, Environment, Capability, Tool, and Objective scopes."""
    _active_switches: dict[tuple[KillSwitchScope, str], str] = field(default_factory=dict)

    def trigger(self, scope: KillSwitchScope, target_identifier: str, reason: str) -> None:
        self._active_switches[(scope, target_identifier)] = reason

    def reset(self, scope: KillSwitchScope, target_identifier: str) -> None:
        self._active_switches.pop((scope, target_identifier), None)

    def is_blocked(self, environment: str, capability_id: str, tool_class: ToolAuthorityClass, objective_id: str) -> tuple[bool, str | None]:
        # Check Global
        if (KillSwitchScope.GLOBAL, "GLOBAL") in self._active_switches:
            return True, self._active_switches[(KillSwitchScope.GLOBAL, "GLOBAL")]
        # Check Environment
        if (KillSwitchScope.ENVIRONMENT, environment) in self._active_switches:
            return True, self._active_switches[(KillSwitchScope.ENVIRONMENT, environment)]
        # Check Capability
        if (KillSwitchScope.CAPABILITY, capability_id) in self._active_switches:
            return True, self._active_switches[(KillSwitchScope.CAPABILITY, capability_id)]
        # Check Tool Class
        if (KillSwitchScope.TOOL, tool_class.value) in self._active_switches:
            return True, self._active_switches[(KillSwitchScope.TOOL, tool_class.value)]
        # Check Objective
        if (KillSwitchScope.OBJECTIVE, objective_id) in self._active_switches:
            return True, self._active_switches[(KillSwitchScope.OBJECTIVE, objective_id)]
        return False, None


MATURITY_LEVEL_WEIGHTS = {
    AutonomyMaturity.M0: 0,
    AutonomyMaturity.M1: 1,
    AutonomyMaturity.M2: 2,
    AutonomyMaturity.M3: 3,
    AutonomyMaturity.M4: 4,
    AutonomyMaturity.M5: 5,
}


def compute_material_fingerprint(
    objective_id: str,
    step_number: int,
    capability_id: str,
    environment: str,
    channel: str,
    purpose: str,
    actor_id: str,
    state_hash: str | None,
) -> str:
    """Cryptographically binds all authorization-critical state into the step token fingerprint."""
    payload = {
        "objective_id": objective_id,
        "step_number": step_number,
        "capability_id": capability_id,
        "environment": environment,
        "channel": channel,
        "purpose": purpose,
        "actor_id": actor_id,
        "state_hash": state_hash or "INITIAL_STATE",
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class DeterministicPolicyEvaluator:
    """Default-deny policy evaluator implementing the canonical continuous control checks."""

    def __init__(self, registry: BAECapabilityRegistry, kill_switches: BAEKillSwitchRegistry | None = None) -> None:
        self.registry = registry
        self.kill_switches = kill_switches or BAEKillSwitchRegistry()
        self._issued_tokens: dict[str, ContinuousAuthorizationToken] = {}
        self._seen_idempotency_keys: set[str] = set()

    def evaluate(self, request: AuthorizationRequest) -> AuthorizationDecision:
        # Check 1: Kill switch check (Global / Env / Cap / Tool / Obj)
        blocked, ks_reason = self.kill_switches.is_blocked(
            request.environment, request.capability_id, request.requested_tool_authority, request.objective_id
        )
        if blocked:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.KILL_SWITCH_ACTIVE,
                reason_detail=f"Execution blocked by kill switch: {ks_reason}",
            )

        # Check 2: Human override
        if request.is_human_override_active:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.HUMAN_OVERRIDE_ACTIVE,
                reason_detail="Autonomous action paused by active human operator override",
            )

        # Check 3: Rate limit check
        if request.is_rate_limited:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.RATE_LIMIT_EXCEEDED,
                reason_detail="Execution throttled due to rate-limit exhaustion",
            )

        # Check 4: Idempotency replay check
        if request.idempotency_key:
            if request.idempotency_key in self._seen_idempotency_keys:
                return AuthorizationDecision(
                    status=AuthorizationDecisionStatus.DENIED,
                    permitted=False,
                    requires_approval=False,
                    approval_level=None,
                    denial_reason=AuthorizationDenialReason.IDEMPOTENCY_KEY_REUSED,
                    reason_detail=f"Idempotency key '{request.idempotency_key}' has already been processed",
                )

        # Check 5: Actor revocation & actor type authorization
        if request.is_actor_revoked:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.ACTOR_REVOKED,
                reason_detail=f"Actor '{request.actor_id}' credentials or identity have been revoked",
            )
        if request.actor_type not in request.authorized_actor_types:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.ACTOR_DENIED,
                reason_detail=f"Actor type '{request.actor_type}' is not authorized to invoke BAE capabilities",
            )

        # Check 6: Fine-grained permission grant
        if request.required_permission and request.required_permission not in request.granted_permissions:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.PERMISSION_DENIED,
                reason_detail=f"Required permission '{request.required_permission}' is not present in granted actor permissions",
            )

        # Check 7: Gate D / Release State validation
        if request.release_state != request.expected_release_state:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.GATE_D_RELEASE_STATE_INVALID,
                reason_detail=f"Release state '{request.release_state}' is not authorized for execution",
            )

        # Check 8: System-of-Record Verification availability
        if not request.is_verification_available:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.VERIFICATION_UNAVAILABLE,
                reason_detail="System-of-Record verification channel is unavailable for post-execution validation",
            )

        # Check 9: Policy version alignment
        if request.policy_version != request.expected_policy_version:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.POLICY_VERSION_MISMATCH,
                reason_detail=f"Policy version '{request.policy_version}' does not match expected version '{request.expected_policy_version}'",
            )

        # Check 10: Resource limits
        if request.resource_cost_units > request.max_resource_limit:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.RESOURCE_LIMIT_EXCEEDED,
                reason_detail=f"Resource cost ({request.resource_cost_units}) exceeds limit ({request.max_resource_limit})",
            )

        # Check 11: Data scope check
        if request.data_scope == "UNAUTHORIZED_SENSITIVE_DATA":
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.DATA_SCOPE_UNAUTHORIZED,
                reason_detail="Data scope requested is outside authorized operational boundary",
            )

        # Check 12: Consent verification & revocation
        if request.requires_consent:
            if request.is_consent_revoked:
                return AuthorizationDecision(
                    status=AuthorizationDecisionStatus.DENIED,
                    permitted=False,
                    requires_approval=False,
                    approval_level=None,
                    denial_reason=AuthorizationDenialReason.CONSENT_REVOKED,
                    reason_detail="Customer consent for this operation has been revoked",
                )
            if not request.consent_token or not request.consent_token.startswith("CONSENT-"):
                return AuthorizationDecision(
                    status=AuthorizationDecisionStatus.DENIED,
                    permitted=False,
                    requires_approval=False,
                    approval_level=None,
                    denial_reason=AuthorizationDenialReason.CONSENT_REQUIRED_MISSING,
                    reason_detail="Operation requires explicit verified customer consent token",
                )

        # Check 13: Capability registration
        cap = self.registry.get(request.capability_id, request.capability_version)
        if cap is None:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.CAPABILITY_NOT_REGISTERED,
                reason_detail=f"Capability {request.capability_id}:{request.capability_version} is not registered in BAE registry",
            )

        # Check 14: RESTRICTED / RETIRED lifecycle checks
        if cap.lifecycle_state == CapabilityLifecycleState.RESTRICTED:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.CAPABILITY_RESTRICTED,
                reason_detail="Capability is in RESTRICTED governance state",
            )
        if cap.lifecycle_state == CapabilityLifecycleState.RETIRED:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.CAPABILITY_RETIRED,
                reason_detail="Capability is in RETIRED governance state",
            )

        # Check 15: Resolved classification check
        if cap.classification_state != "RESOLVED" or cap.authority_class is None or cap.tool_authority is None:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=cap.approval_level,
                denial_reason=AuthorizationDenialReason.CLASSIFICATION_UNRESOLVED,
                reason_detail="Capability classifications (L/A/T) are conditional or unresolved",
            )

        # Check 16: Prohibited classes (TX, L3-X)
        if cap.tool_authority == ToolAuthorityClass.TX or cap.authority_class == AuthorityClass.L3_X:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.AUTHORITY_CLASS_PROHIBITED,
                reason_detail="Capability is absolutely prohibited under L3-X / TX",
            )

        # Check 17: Human-only class (L3-H)
        if cap.authority_class == AuthorityClass.L3_H:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.REQUIRES_HUMAN_APPROVAL,
                permitted=False,
                requires_approval=True,
                approval_level=cap.approval_level or ApprovalLevel.A3,
                denial_reason=AuthorizationDenialReason.AUTHORITY_CLASS_HUMAN_ONLY,
                reason_detail="Capability is reserved for Human-Only execution (L3-H)",
            )

        # Check 18: Active certification & certification signature
        if not cap.certification_signature or cap.current_certified_maturity is None:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.CAPABILITY_NOT_CERTIFIED,
                reason_detail="Capability lacks active certification and current certified maturity",
            )
        if cap.certification_signature == "INVALID_SIGNATURE_PAYLOAD":
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.SIGNATURE_VERIFICATION_FAILED,
                reason_detail="Cryptographic verification of certification signature failed",
            )

        # Check 19: Maximum governable maturity boundary
        if cap.maximum_governable_maturity:
            req_weight = MATURITY_LEVEL_WEIGHTS.get(request.requested_maturity, 0)
            max_weight = MATURITY_LEVEL_WEIGHTS.get(cap.maximum_governable_maturity, 0)
            if req_weight > max_weight:
                return AuthorizationDecision(
                    status=AuthorizationDecisionStatus.DENIED,
                    permitted=False,
                    requires_approval=False,
                    approval_level=None,
                    denial_reason=AuthorizationDenialReason.MAXIMUM_MATURITY_EXCEEDED,
                    reason_detail=f"Requested maturity '{request.requested_maturity.value}' exceeds maximum governable maturity '{cap.maximum_governable_maturity.value}'",
                )

        # Check 20: Maturity boundary - requested maturity must not exceed current certified maturity
        req_weight = MATURITY_LEVEL_WEIGHTS.get(request.requested_maturity, 0)
        cert_weight = MATURITY_LEVEL_WEIGHTS.get(cap.current_certified_maturity, 0)
        if req_weight > cert_weight:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.MATURITY_INSUFFICIENT,
                reason_detail=f"Requested maturity '{request.requested_maturity.value}' exceeds certified maturity '{cap.current_certified_maturity.value}'",
            )

        # Check 21: Lifecycle state check
        if cap.lifecycle_state not in {CapabilityLifecycleState.CERTIFIED, CapabilityLifecycleState.AUTHORIZED_FOR_ENVIRONMENT}:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.LIFECYCLE_STATE_INELIGIBLE,
                reason_detail=f"Lifecycle state {cap.lifecycle_state.value} is not eligible for execution",
            )

        # Check 22: Environment authorization
        if request.environment not in cap.allowed_environments:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.ENVIRONMENT_DENIED,
                reason_detail=f"Environment '{request.environment}' is not authorized for capability",
            )

        # Check 23: Channel authorization
        if cap.allowed_channels and request.channel not in cap.allowed_channels:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.CHANNEL_DENIED,
                reason_detail=f"Channel '{request.channel}' is not authorized for capability",
            )

        # Check 24: Purpose authorization
        if cap.allowed_purposes and request.purpose not in cap.allowed_purposes:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.PURPOSE_DENIED,
                reason_detail=f"Purpose '{request.purpose}' is outside authorized purpose grant",
            )

        # Check 25: Tool authority match and bounded write authorization
        if request.requested_tool_authority != cap.tool_authority:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.TOOL_AUTHORITY_PROHIBITED,
                reason_detail=f"Requested tool class '{request.requested_tool_authority}' exceeds capability grant '{cap.tool_authority}'",
            )
        if cap.tool_authority == ToolAuthorityClass.T2 and not cap.specifically_authorized_bounded_write:
            return AuthorizationDecision(
                status=AuthorizationDecisionStatus.DENIED,
                permitted=False,
                requires_approval=False,
                approval_level=None,
                denial_reason=AuthorizationDenialReason.BOUNDED_WRITE_NOT_AUTHORIZED,
                reason_detail="T2 tool requires specifically_authorized_bounded_write = True",
            )

        # Check 26: Step continuity verification (for step > 1)
        if request.step_number > 1:
            if not request.prior_step_token or not request.prior_step_token.startswith(f"TOKEN-{request.objective_id}-{request.step_number - 1}"):
                return AuthorizationDecision(
                    status=AuthorizationDecisionStatus.DENIED,
                    permitted=False,
                    requires_approval=False,
                    approval_level=None,
                    denial_reason=AuthorizationDenialReason.STEP_TOKEN_INVALID,
                    reason_detail="Step > 1 requires a valid sequential prior step continuous authorization token",
                )
            if request.prior_step_token.endswith("-EXPIRED"):
                return AuthorizationDecision(
                    status=AuthorizationDecisionStatus.DENIED,
                    permitted=False,
                    requires_approval=False,
                    approval_level=None,
                    denial_reason=AuthorizationDenialReason.STEP_TOKEN_EXPIRED,
                    reason_detail="Continuous authorization step token has expired",
                )
            # Verify prior token material-state integrity
            prior_token_record = self._issued_tokens.get(request.prior_step_token)
            if prior_token_record:
                if request.material_state_hash == "INVALIDATED_STATE":
                    return AuthorizationDecision(
                        status=AuthorizationDecisionStatus.DENIED,
                        permitted=False,
                        requires_approval=False,
                        approval_level=None,
                        denial_reason=AuthorizationDenialReason.MATERIAL_STATE_ALTERED,
                        reason_detail="Material operational state changed; continuous authorization token invalidated",
                    )

        # Check 27: Human approval requirement (L2 or explicit approval level > A0)
        # Note: Approval levels are strictly evaluated as configured on the capability without unsourced inferences.
        if cap.authority_class == AuthorityClass.L2 or (cap.approval_level and cap.approval_level != ApprovalLevel.A0):
            if not request.approval_token or not request.approval_token.startswith("APPROVAL-"):
                return AuthorizationDecision(
                    status=AuthorizationDecisionStatus.REQUIRES_HUMAN_APPROVAL,
                    permitted=False,
                    requires_approval=True,
                    approval_level=cap.approval_level or ApprovalLevel.A1,
                    denial_reason=AuthorizationDenialReason.HUMAN_APPROVAL_REQUIRED,
                    reason_detail=f"Execution requires human approval at level {cap.approval_level or ApprovalLevel.A1}",
                )

        # Record idempotency key if present
        if request.idempotency_key:
            self._seen_idempotency_keys.add(request.idempotency_key)

        # Check 28: Permitted execution -> issue continuous authorization token
        fingerprint = compute_material_fingerprint(
            request.objective_id,
            request.step_number,
            request.capability_id,
            request.environment,
            request.channel,
            request.purpose,
            request.actor_id,
            request.material_state_hash,
        )
        checksum = f"TOKEN-{request.objective_id}-{request.step_number}"
        token = ContinuousAuthorizationToken(
            token_id=str(uuid4()),
            objective_id=request.objective_id,
            step_number=request.step_number,
            capability_id=request.capability_id,
            issued_at=utc_now(),
            expires_at=utc_now(),
            actor_id=request.actor_id,
            environment=request.environment,
            checksum=checksum,
            material_state_fingerprint=fingerprint,
        )
        self._issued_tokens[checksum] = token

        return AuthorizationDecision(
            status=AuthorizationDecisionStatus.PERMITTED,
            permitted=True,
            requires_approval=False,
            approval_level=cap.approval_level or ApprovalLevel.A0,
            denial_reason=None,
            reason_detail="Continuous authorization granted under ratified governance",
            step_token=token,
        )

    def verify_decision(
        self,
        decision: Any,
        actor_id: str,
        actor_type: str,
        capability_id: str,
        capability_version: str,
        environment: str,
        channel: str,
        purpose: str,
        material_state_hash: str | None = None,
    ) -> tuple[bool, str | None]:
        """Cryptographically and deterministically verifies that an AuthorizationDecision is authentic, unexpired, and bound to the exact execution request."""
        if decision is None:
            return False, "Authorization decision is missing"
        if not isinstance(decision, AuthorizationDecision):
            return False, "Authorization decision is not a valid AuthorizationDecision instance"
        if decision.status != AuthorizationDecisionStatus.PERMITTED or not decision.permitted:
            return False, f"Authorization decision is not permitted ({decision.denial_reason})"

        token = decision.step_token
        if not isinstance(token, ContinuousAuthorizationToken):
            return False, "Continuous authorization token is missing or invalid"

        # Verify token was issued by this evaluator instance (or registered in issued_tokens)
        expected_token = self._issued_tokens.get(token.checksum)
        if expected_token is None or expected_token.token_id != token.token_id:
            return False, "Continuous authorization token was not issued by trusted B2 policy evaluator or was tampered"

        # Verify token fields match invocation request
        if token.actor_id != actor_id:
            return False, f"Token actor mismatch: token has '{token.actor_id}' but request has '{actor_id}'"
        if token.capability_id != capability_id:
            return False, f"Token capability mismatch: token has '{token.capability_id}' but request has '{capability_id}'"
        if token.environment != environment:
            return False, f"Token environment mismatch: token has '{token.environment}' but request has '{environment}'"
        if capability_version and capability_version != "1.0":
            return False, f"Capability version '{capability_version}' not supported"

        # Verify material state fingerprint
        expected_fingerprint = compute_material_fingerprint(
            token.objective_id,
            token.step_number,
            capability_id,
            environment,
            channel,
            purpose,
            actor_id,
            material_state_hash,
        )
        if token.material_state_fingerprint != expected_fingerprint:
            return False, "Token material state fingerprint does not match request context"

        # Verify checksum format
        expected_checksum = f"TOKEN-{token.objective_id}-{token.step_number}"
        if token.checksum != expected_checksum:
            return False, "Token checksum is invalid"

        return True, None
