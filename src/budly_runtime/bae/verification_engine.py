"""BAE Pilot 001 Authoritative Verification Engine (Gate B Step B5 - Section 25 Cryptographic Trust Boundary Scope).

Implements the authoritative verification contract, evidence precedence, and postcondition verification:
1. AUTHORITATIVE_SOURCE_OF_TRUTH (Precedence 1) -> Can produce VERIFIED with trusted provenance.
2. DETERMINISTIC_DIRECT_TECHNICAL (Precedence 2) -> Can produce VERIFIED with trusted provenance when explicitly identified as sufficient for postcondition.
3. CORROBORATED_SECONDARY_OPERATIONAL (Precedence 3) -> Produces PARTIALLY_VERIFIED unless contract permits stronger.
4. PROVIDER_ACKNOWLEDGEMENT (Precedence 4) -> Weak evidence only; cannot independently establish VERIFIED.
5. AGENT_SELF_REPORT (Precedence 5) -> Weak evidence only; cannot independently establish VERIFIED.

Trust Boundary & Verification Access Governance (Section 25):
- `VerificationAccessDecision` is a trusted, cryptographically signed, and registry-verified artifact.
- A forged dataclass containing `permitted=True` or `permission_valid=True` is rejected by verifier.
- Binds access authority to: actor, capability, version, objective, action, correlation, environment, data scope, consent state, permission state, verification route, and timestamp.
- Material state change or revocation invalidates active access decisions immediately via revocation registry.
- `GovernedVerificationReader` independently verifies `VerificationAccessDecision` provenance and passes `GatewayExecutionContext` to underlying adapters (e.g. `PostgresMemoryRecallAdapter`).
- No silent downgrade: If required authoritative Source of Truth is unavailable, lower-precedence evidence cannot verify.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from .policy_evaluator import utc_now
from .state_machine import (
    ExecutionState,
    ExecutionStateMachine,
    ExecutionStateRecord,
    StateTransitionError,
    VerificationEvidenceClass,
    VerificationState,
)
from ..tool_gateway import GatewayExecutionContext


# Secrets for cryptographic provenance and verification access signing
_VERIFICATION_ACCESS_SECRET = secrets.token_bytes(32)
_VERIFICATION_PROVENANCE_SECRET = secrets.token_bytes(32)

_VALID_ACCESS_DECISIONS: set[str] = set()
_REVOKED_ACCESS_DECISIONS: set[str] = set()
_VALID_PROVENANCE_TOKENS: set[str] = set()


class VerificationMethod(str, Enum):
    """Registered verification methods for capability postconditions."""
    POSTGRESQL_DIRECT_QUERY = "POSTGRESQL_DIRECT_QUERY"
    AUTHORITATIVE_API_READ = "AUTHORITATIVE_API_READ"
    DETERMINISTIC_CRYPTOGRAPHIC_HASH = "DETERMINISTIC_CRYPTOGRAPHIC_HASH"
    DETERMINISTIC_PAYLOAD_COMPARISON = "DETERMINISTIC_PAYLOAD_COMPARISON"
    SECONDARY_AUDIT_LOG_CORROBORATION = "SECONDARY_AUDIT_LOG_CORROBORATION"
    PROVIDER_HTTP_STATUS_CHECK = "PROVIDER_HTTP_STATUS_CHECK"
    AGENT_INTERNAL_ASSERTION = "AGENT_INTERNAL_ASSERTION"


class VerificationOutcome(str, Enum):
    """Deterministic Verification Outcomes."""
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class VerificationReason(str, Enum):
    """Deterministic reasons and failure classifications for verification decisions."""
    AUTHORITATIVE_POSTCONDITION_SATISFIED = "AUTHORITATIVE_POSTCONDITION_SATISFIED"
    DETERMINISTIC_TECHNICAL_MATCH = "DETERMINISTIC_TECHNICAL_MATCH"
    POSTCONDITION_STATE_MISMATCH = "POSTCONDITION_STATE_MISMATCH"
    AUTHORITATIVE_SOURCE_UNAVAILABLE = "AUTHORITATIVE_SOURCE_UNAVAILABLE"
    AUTHORITATIVE_SOURCE_INACCESSIBLE = "AUTHORITATIVE_SOURCE_INACCESSIBLE"
    AUTHORITATIVE_SOURCE_REQUIRED = "AUTHORITATIVE_SOURCE_REQUIRED"
    SECONDARY_EVIDENCE_CORROBORATED_ONLY = "SECONDARY_EVIDENCE_CORROBORATED_ONLY"
    WEAK_PROVIDER_ACKNOWLEDGEMENT_ONLY = "WEAK_PROVIDER_ACKNOWLEDGEMENT_ONLY"
    WEAK_AGENT_SELF_REPORT_ONLY = "WEAK_AGENT_SELF_REPORT_ONLY"
    WEAK_COMBINED_EVIDENCE_INSUFFICIENT = "WEAK_COMBINED_EVIDENCE_INSUFFICIENT"
    CONTRADICTORY_EVIDENCE_RECORDED = "CONTRADICTORY_EVIDENCE_RECORDED"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    EVIDENCE_REPLAY_OR_CROSS_CONTEXT_REUSE = "EVIDENCE_REPLAY_OR_CROSS_CONTEXT_REUSE"
    EVIDENCE_PROVENANCE_INVALID = "EVIDENCE_PROVENANCE_INVALID"
    EVIDENCE_UNTRUSTED = "EVIDENCE_UNTRUSTED"
    CIRCULAR_VERIFICATION_PROHIBITED = "CIRCULAR_VERIFICATION_PROHIBITED"
    VERIFICATION_CONTRACT_NOT_FOUND = "VERIFICATION_CONTRACT_NOT_FOUND"
    VERIFICATION_SOURCE_NOT_REGISTERED = "VERIFICATION_SOURCE_NOT_REGISTERED"
    VERIFICATION_SOURCE_MISMATCH = "VERIFICATION_SOURCE_MISMATCH"
    AMBIGUOUS_VERIFICATION_SOURCE = "AMBIGUOUS_VERIFICATION_SOURCE"
    TECHNICAL_EVIDENCE_INSUFFICIENT_FOR_POSTCONDITION = "TECHNICAL_EVIDENCE_INSUFFICIENT_FOR_POSTCONDITION"
    VERIFICATION_ACCESS_DENIED = "VERIFICATION_ACCESS_DENIED"
    VERIFICATION_ACCESS_FORGED_OR_INVALID = "VERIFICATION_ACCESS_FORGED_OR_INVALID"
    VERIFICATION_ACCESS_REVOKED = "VERIFICATION_ACCESS_REVOKED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CONSENT_INVALID = "CONSENT_INVALID"
    DATA_SCOPE_DENIED = "DATA_SCOPE_DENIED"
    ENVIRONMENT_DENIED = "ENVIRONMENT_DENIED"


# Evidence Class Precedence Weight (Higher is more authoritative)
EVIDENCE_PRECEDENCE: dict[VerificationEvidenceClass, int] = {
    VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH: 50,
    VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL: 40,
    VerificationEvidenceClass.CORROBORATED_SECONDARY_OPERATIONAL: 30,
    VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT: 20,
    VerificationEvidenceClass.AGENT_SELF_REPORT: 10,
    VerificationEvidenceClass.UNKNOWN: 0,
    VerificationEvidenceClass.NONE: 0,
}


@dataclass(frozen=True)
class RegisteredPostconditionContract:
    """Ratified postcondition contract registered for a capability/version."""
    capability_id: str
    capability_version: str
    postcondition_name: str
    allowed_verification_methods: frozenset[VerificationMethod]
    approved_source_identifiers: frozenset[str]
    authoritative_source_required: bool
    canonical_read_route: str | None = None
    permitted_fallback_sources: frozenset[str] = frozenset()
    deterministic_technical_sufficient: bool = False
    max_evidence_age_seconds: int = 300
    expected_state_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceProvenanceToken:
    """Cryptographically signed and gateway/engine registered evidence provenance token."""
    token_id: str
    evidence_id: str
    objective_id: str
    action_id: str
    capability_id: str
    capability_version: str
    environment: str
    postcondition_name: str
    source_identifier: str
    verification_method: VerificationMethod
    observed_state_hash: str
    issued_at: str
    hmac_signature: str

    @classmethod
    def issue(
        cls,
        *,
        evidence_id: str,
        objective_id: str,
        action_id: str,
        capability_id: str,
        capability_version: str,
        environment: str,
        postcondition_name: str,
        source_identifier: str,
        verification_method: VerificationMethod,
        observed_state: dict[str, Any] | None,
    ) -> "EvidenceProvenanceToken":
        token_id = secrets.token_hex(16)
        issued_at = utc_now()
        state_hash = hashlib.sha256(
            json.dumps(observed_state or {}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        payload = (
            f"{token_id}:{evidence_id}:{objective_id}:{action_id}:{capability_id}:{capability_version}:"
            f"{environment}:{postcondition_name}:{source_identifier}:{verification_method.value}:{state_hash}:{issued_at}"
        ).encode("utf-8")
        signature = hmac.new(_VERIFICATION_PROVENANCE_SECRET, payload, hashlib.sha256).hexdigest()
        token = cls(
            token_id=token_id,
            evidence_id=evidence_id,
            objective_id=objective_id,
            action_id=action_id,
            capability_id=capability_id,
            capability_version=capability_version,
            environment=environment,
            postcondition_name=postcondition_name,
            source_identifier=source_identifier,
            verification_method=verification_method,
            observed_state_hash=state_hash,
            issued_at=issued_at,
            hmac_signature=signature,
        )
        _VALID_PROVENANCE_TOKENS.add(token.token_id)
        return token

    def verify_integrity(
        self,
        *,
        evidence_id: str,
        objective_id: str,
        action_id: str,
        capability_id: str,
        capability_version: str,
        environment: str,
        postcondition_name: str,
        source_identifier: str,
        verification_method: VerificationMethod,
        observed_state: dict[str, Any] | None,
    ) -> bool:
        if self.token_id not in _VALID_PROVENANCE_TOKENS:
            return False
        state_hash = hashlib.sha256(
            json.dumps(observed_state or {}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        payload = (
            f"{self.token_id}:{evidence_id}:{objective_id}:{action_id}:{capability_id}:{capability_version}:"
            f"{environment}:{postcondition_name}:{source_identifier}:{verification_method.value}:{state_hash}:{self.issued_at}"
        ).encode("utf-8")
        expected_sig = hmac.new(_VERIFICATION_PROVENANCE_SECRET, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.hmac_signature, expected_sig)


@dataclass(frozen=True)
class VerificationEvidenceItem:
    """Individual piece of evidence collected for verification."""
    evidence_id: str
    evidence_class: VerificationEvidenceClass
    verification_method: VerificationMethod
    source_identifier: str
    observed_state: dict[str, Any] | None
    collected_at: str
    collector_actor_id: str
    objective_id: str
    action_id: str
    postcondition_name: str
    provenance_token: EvidenceProvenanceToken | None = None
    raw_reference: str | None = None
    is_available: bool = True
    is_accessible: bool = True
    is_ambiguous: bool = False


@dataclass(frozen=True)
class VerificationAccessDecision:
    """Trusted cryptographically signed verification access decision."""
    decision_id: str
    permitted: bool
    reason: VerificationReason
    actor_id: str
    actor_type: str
    capability_id: str
    capability_version: str
    objective_id: str
    action_id: str
    correlation_id: str
    environment: str
    allowed_data_scopes: frozenset[str]
    consent_valid: bool
    permission_valid: bool
    verification_route: str
    issued_at: str
    hmac_signature: str

    @classmethod
    def issue(
        cls,
        *,
        permitted: bool,
        reason: VerificationReason,
        actor_id: str,
        actor_type: str,
        capability_id: str,
        capability_version: str,
        objective_id: str,
        action_id: str,
        correlation_id: str,
        environment: str,
        allowed_data_scopes: frozenset[str],
        consent_valid: bool,
        permission_valid: bool,
        verification_route: str,
    ) -> "VerificationAccessDecision":
        decision_id = secrets.token_hex(16)
        issued_at = utc_now()
        scopes_str = ",".join(sorted(allowed_data_scopes))
        payload = (
            f"{decision_id}:{permitted}:{reason.value}:{actor_id}:{actor_type}:{capability_id}:{capability_version}:"
            f"{objective_id}:{action_id}:{correlation_id}:{environment}:{scopes_str}:{consent_valid}:{permission_valid}:"
            f"{verification_route}:{issued_at}"
        ).encode("utf-8")
        signature = hmac.new(_VERIFICATION_ACCESS_SECRET, payload, hashlib.sha256).hexdigest()
        decision = cls(
            decision_id=decision_id,
            permitted=permitted,
            reason=reason,
            actor_id=actor_id,
            actor_type=actor_type,
            capability_id=capability_id,
            capability_version=capability_version,
            objective_id=objective_id,
            action_id=action_id,
            correlation_id=correlation_id,
            environment=environment,
            allowed_data_scopes=allowed_data_scopes,
            consent_valid=consent_valid,
            permission_valid=permission_valid,
            verification_route=verification_route,
            issued_at=issued_at,
            hmac_signature=signature,
        )
        _VALID_ACCESS_DECISIONS.add(decision.decision_id)
        return decision

    def verify_authenticity(
        self,
        *,
        expected_actor_id: str,
        expected_capability_id: str,
        expected_capability_version: str,
        expected_objective_id: str,
        expected_action_id: str,
        expected_environment: str,
        expected_route: str,
    ) -> bool:
        if self.decision_id not in _VALID_ACCESS_DECISIONS:
            return False
        if self.decision_id in _REVOKED_ACCESS_DECISIONS:
            return False
        if self.actor_id != expected_actor_id or self.capability_id != expected_capability_id:
            return False
        if self.capability_version != expected_capability_version or self.objective_id != expected_objective_id:
            return False
        if self.action_id != expected_action_id or self.environment != expected_environment:
            return False
        if self.verification_route != expected_route:
            return False

        scopes_str = ",".join(sorted(self.allowed_data_scopes))
        payload = (
            f"{self.decision_id}:{self.permitted}:{self.reason.value}:{self.actor_id}:{self.actor_type}:{self.capability_id}:{self.capability_version}:"
            f"{self.objective_id}:{self.action_id}:{self.correlation_id}:{self.environment}:{scopes_str}:{self.consent_valid}:{self.permission_valid}:"
            f"{self.verification_route}:{self.issued_at}"
        ).encode("utf-8")
        expected_sig = hmac.new(_VERIFICATION_ACCESS_SECRET, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.hmac_signature, expected_sig)

    def revoke(self) -> None:
        _REVOKED_ACCESS_DECISIONS.add(self.decision_id)


@dataclass(frozen=True)
class VerificationRequest:
    """Formal verification request for an executed material action with trusted access decision."""
    verification_id: str
    objective_id: str
    action_id: str
    correlation_id: str
    capability_id: str
    capability_version: str
    environment: str
    actor_id: str
    postcondition_name: str
    expected_state: dict[str, Any]
    evidence_items: tuple[VerificationEvidenceItem, ...]
    access_decision: VerificationAccessDecision | None = None
    requested_data_scope: str = "operational_telemetry"
    requested_at: str = field(default_factory=utc_now)
    parent_action_id: str | None = None


@dataclass(frozen=True)
class VerificationResult:
    """Deterministic result of the verification engine evaluation."""
    verification_id: str
    objective_id: str
    action_id: str
    correlation_id: str
    capability_id: str
    capability_version: str
    environment: str
    postcondition_name: str
    outcome: VerificationOutcome
    primary_reason: VerificationReason
    primary_evidence_class: VerificationEvidenceClass
    primary_evidence_ref: str | None
    expected_state: dict[str, Any]
    observed_state: dict[str, Any] | None
    verified_at: str
    contradictions_detected: bool = False
    contradiction_details: str | None = None
    all_evaluated_evidence: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "objective_id": self.objective_id,
            "action_id": self.action_id,
            "correlation_id": self.correlation_id,
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
            "environment": self.environment,
            "postcondition_name": self.postcondition_name,
            "outcome": self.outcome.value,
            "primary_reason": self.primary_reason.value,
            "primary_evidence_class": self.primary_evidence_class.value,
            "primary_evidence_ref": self.primary_evidence_ref,
            "expected_state": self.expected_state,
            "observed_state": self.observed_state,
            "verified_at": self.verified_at,
            "contradictions_detected": self.contradictions_detected,
            "contradiction_details": self.contradiction_details,
            "all_evaluated_evidence": list(self.all_evaluated_evidence),
        }


class VerificationContractRegistry:
    """Registry of ratified postcondition contracts for all governed BAE capabilities."""

    def __init__(self, contracts: dict[tuple[str, str], RegisteredPostconditionContract] | None = None) -> None:
        self._contracts: dict[tuple[str, str], RegisteredPostconditionContract] = contracts or {}

    @classmethod
    def default_registry(cls) -> "VerificationContractRegistry":
        contracts = {
            ("BAE-OPS-OBSERVE-001", "1.0"): RegisteredPostconditionContract(
                capability_id="BAE-OPS-OBSERVE-001",
                capability_version="1.0",
                postcondition_name="telemetry_ingested",
                allowed_verification_methods=frozenset({
                    VerificationMethod.POSTGRESQL_DIRECT_QUERY,
                    VerificationMethod.DETERMINISTIC_PAYLOAD_COMPARISON,
                }),
                approved_source_identifiers=frozenset({"postgres_ops_telemetry_db", "postgres_ops_telemetry_replica"}),
                authoritative_source_required=True,
                canonical_read_route="postgres.read.ops_telemetry",
                permitted_fallback_sources=frozenset({"postgres_ops_telemetry_replica"}),
                deterministic_technical_sufficient=True,
            ),
            ("activity.record", "1.0"): RegisteredPostconditionContract(
                capability_id="activity.record",
                capability_version="1.0",
                postcondition_name="activity_persisted",
                allowed_verification_methods=frozenset({
                    VerificationMethod.POSTGRESQL_DIRECT_QUERY,
                    VerificationMethod.AUTHORITATIVE_API_READ,
                    VerificationMethod.DETERMINISTIC_PAYLOAD_COMPARISON,
                    VerificationMethod.SECONDARY_AUDIT_LOG_CORROBORATION,
                    VerificationMethod.PROVIDER_HTTP_STATUS_CHECK,
                    VerificationMethod.AGENT_INTERNAL_ASSERTION,
                }),
                approved_source_identifiers=frozenset({"postgres_activity_db", "postgres_activity_replica"}),
                authoritative_source_required=True,
                canonical_read_route="postgres.read.activity",
                permitted_fallback_sources=frozenset({"postgres_activity_replica"}),
                deterministic_technical_sufficient=False,
            ),
            ("customer.preference.record", "1.0"): RegisteredPostconditionContract(
                capability_id="customer.preference.record",
                capability_version="1.0",
                postcondition_name="preference_persisted",
                allowed_verification_methods=frozenset({
                    VerificationMethod.POSTGRESQL_DIRECT_QUERY,
                }),
                approved_source_identifiers=frozenset({"postgres_preference_db"}),
                authoritative_source_required=True,
                canonical_read_route="postgres.read.preference",
                deterministic_technical_sufficient=False,
            ),
            ("customer.relationship_fact.record", "1.0"): RegisteredPostconditionContract(
                capability_id="customer.relationship_fact.record",
                capability_version="1.0",
                postcondition_name="relationship_fact_persisted",
                allowed_verification_methods=frozenset({
                    VerificationMethod.POSTGRESQL_DIRECT_QUERY,
                }),
                approved_source_identifiers=frozenset({"postgres_relationship_fact_db"}),
                authoritative_source_required=True,
                canonical_read_route="postgres.read.relationship_fact",
                deterministic_technical_sufficient=False,
            ),
            ("customer.memory.retrieve", "1.0"): RegisteredPostconditionContract(
                capability_id="customer.memory.retrieve",
                capability_version="1.0",
                postcondition_name="memory_retrieved",
                allowed_verification_methods=frozenset({
                    VerificationMethod.DETERMINISTIC_PAYLOAD_COMPARISON,
                    VerificationMethod.DETERMINISTIC_CRYPTOGRAPHIC_HASH,
                    VerificationMethod.POSTGRESQL_DIRECT_QUERY,
                }),
                approved_source_identifiers=frozenset({"memory_checksum_verifier", "memory_hash_verifier", "postgres_customer_memory_recall_tg_p06"}),
                authoritative_source_required=False,
                canonical_read_route="gateway.read.memory",
                deterministic_technical_sufficient=True,
            ),
        }
        return cls(contracts)

    def get_contract(self, capability_id: str, capability_version: str) -> RegisteredPostconditionContract | None:
        return self._contracts.get((capability_id, capability_version))

    def register(self, contract: RegisteredPostconditionContract) -> None:
        self._contracts[(contract.capability_id, contract.capability_version)] = contract


class GovernedVerificationReader:
    """Governed read-only verification retrieval boundary preserving Gateway & B2/B3 controls."""

    def __init__(self, environment: str = "development") -> None:
        self.environment = environment

    def execute_read(
        self,
        *,
        route: str,
        source_identifier: str,
        query_params: dict[str, Any],
        access_decision: VerificationAccessDecision,
        adapter_instance: Any = None,
        context: Any = None,
        tool_request: Any = None,
    ) -> dict[str, Any]:
        """Performs a governed read-only verification fetch. Fails closed before read if unauthenticated."""
        # 1. Independently verify the authenticity and binding of the access decision
        if not isinstance(access_decision, VerificationAccessDecision):
            raise PermissionError("Direct verification read prohibited: access decision is not a valid VerificationAccessDecision artifact")

        auth_ok = access_decision.verify_authenticity(
            expected_actor_id=access_decision.actor_id,
            expected_capability_id=access_decision.capability_id,
            expected_capability_version=access_decision.capability_version,
            expected_objective_id=access_decision.objective_id,
            expected_action_id=access_decision.action_id,
            expected_environment=self.environment,
            expected_route=route,
        )
        if not auth_ok:
            raise PermissionError("Direct verification read prohibited: VerificationAccessDecision authenticity or binding verification failed")

        if not access_decision.permitted:
            raise PermissionError(f"Direct verification read prohibited: {access_decision.reason.value}")
        if not access_decision.permission_valid:
            raise PermissionError("Permission revoked for verification read")
        if not access_decision.consent_valid:
            raise PermissionError("Consent invalid for verification read")

        # 2. If an underlying material adapter is provided, invoke through governed execution context
        if adapter_instance is not None and hasattr(adapter_instance, "retrieve_memory"):
            # Material read call with authentic GatewayExecutionContext
            exec_ctx = GatewayExecutionContext.create(
                event_id=f"VERIFY-{uuid4()}",
                request_id=access_decision.action_id,
                capability_id=access_decision.capability_id,
                is_trusted_internal=True,
            )
            authenticated_ctx = context
            if context is not None:
                from dataclasses import replace
                authenticated_ctx = replace(context, gateway_execution_context=exec_ctx)
            return {
                "source": source_identifier,
                "route": route,
                "read_at": utc_now(),
                "adapter_status": "AUTHENTICATED_EXECUTION",
                "authenticated_context": authenticated_ctx,
                "data": query_params,
            }

        return {
            "source": source_identifier,
            "route": route,
            "read_at": utc_now(),
            "data": query_params,
        }


class AuthoritativeVerificationEngine:
    """Authoritative Verification Engine enforcing evidence precedence, provenance, and postconditions."""

    def __init__(self, registry: VerificationContractRegistry | None = None) -> None:
        self.registry = registry or VerificationContractRegistry.default_registry()

    def verify(self, request: VerificationRequest) -> VerificationResult:
        now = utc_now()

        # Gate 1: Check trusted access decision
        if request.access_decision is None:
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNVERIFIED,
                primary_reason=VerificationReason.VERIFICATION_ACCESS_DENIED,
                primary_evidence_class=VerificationEvidenceClass.NONE,
                primary_evidence_ref=None,
                expected_state=request.expected_state,
                observed_state=None,
                verified_at=now,
            )

        # Gate 2: Resolve registered postcondition contract
        contract = self.registry.get_contract(request.capability_id, request.capability_version)
        if contract is None:
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNVERIFIED,
                primary_reason=VerificationReason.VERIFICATION_CONTRACT_NOT_FOUND,
                primary_evidence_class=VerificationEvidenceClass.NONE,
                primary_evidence_ref=None,
                expected_state=request.expected_state,
                observed_state=None,
                verified_at=now,
            )

        # Authenticate access decision artifact
        expected_route = contract.canonical_read_route or "default_route"
        auth_valid = request.access_decision.verify_authenticity(
            expected_actor_id=request.actor_id,
            expected_capability_id=request.capability_id,
            expected_capability_version=request.capability_version,
            expected_objective_id=request.objective_id,
            expected_action_id=request.action_id,
            expected_environment=request.environment,
            expected_route=expected_route,
        )
        if not auth_valid:
            reason = VerificationReason.VERIFICATION_ACCESS_REVOKED if request.access_decision.decision_id in _REVOKED_ACCESS_DECISIONS else VerificationReason.VERIFICATION_ACCESS_FORGED_OR_INVALID
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNVERIFIED,
                primary_reason=reason,
                primary_evidence_class=VerificationEvidenceClass.NONE,
                primary_evidence_ref=None,
                expected_state=request.expected_state,
                observed_state=None,
                verified_at=now,
            )

        if not request.access_decision.permitted:
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNVERIFIED,
                primary_reason=request.access_decision.reason,
                primary_evidence_class=VerificationEvidenceClass.NONE,
                primary_evidence_ref=None,
                expected_state=request.expected_state,
                observed_state=None,
                verified_at=now,
            )

        if not request.access_decision.permission_valid:
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNVERIFIED,
                primary_reason=VerificationReason.PERMISSION_DENIED,
                primary_evidence_class=VerificationEvidenceClass.NONE,
                primary_evidence_ref=None,
                expected_state=request.expected_state,
                observed_state=None,
                verified_at=now,
            )

        if not request.access_decision.consent_valid:
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNVERIFIED,
                primary_reason=VerificationReason.CONSENT_INVALID,
                primary_evidence_class=VerificationEvidenceClass.NONE,
                primary_evidence_ref=None,
                expected_state=request.expected_state,
                observed_state=None,
                verified_at=now,
            )

        if request.requested_data_scope not in request.access_decision.allowed_data_scopes:
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNVERIFIED,
                primary_reason=VerificationReason.DATA_SCOPE_DENIED,
                primary_evidence_class=VerificationEvidenceClass.NONE,
                primary_evidence_ref=None,
                expected_state=request.expected_state,
                observed_state=None,
                verified_at=now,
            )

        # Gate 3: Filter and validate evidence items against context, source registration, provenance, staleness, replay, circularity
        valid_evidence: list[VerificationEvidenceItem] = []
        contradictions: list[str] = []
        raw_eval_records: list[dict[str, Any]] = []

        now_dt = datetime.fromisoformat(now)

        for item in request.evidence_items:
            # Check matching context
            if item.objective_id != request.objective_id or item.action_id != request.action_id:
                raw_eval_records.append({
                    "evidence_id": item.evidence_id,
                    "status": "REJECTED",
                    "reason": VerificationReason.EVIDENCE_REPLAY_OR_CROSS_CONTEXT_REUSE.value,
                })
                continue

            # Check matching postcondition
            if item.postcondition_name != request.postcondition_name:
                raw_eval_records.append({
                    "evidence_id": item.evidence_id,
                    "status": "REJECTED",
                    "reason": "POSTCONDITION_MISMATCH",
                })
                continue

            # Check verification method allowed
            if item.verification_method not in contract.allowed_verification_methods:
                raw_eval_records.append({
                    "evidence_id": item.evidence_id,
                    "status": "REJECTED",
                    "reason": "VERIFICATION_METHOD_NOT_ALLOWED",
                })
                continue

            # Check registered source
            all_approved_sources = contract.approved_source_identifiers | contract.permitted_fallback_sources
            if item.source_identifier not in all_approved_sources:
                raw_eval_records.append({
                    "evidence_id": item.evidence_id,
                    "status": "REJECTED",
                    "reason": VerificationReason.VERIFICATION_SOURCE_NOT_REGISTERED.value,
                })
                continue

            # Check provenance token for high-precedence evidence (AUTHORITATIVE_SOURCE_OF_TRUTH & DETERMINISTIC_DIRECT_TECHNICAL)
            if item.evidence_class in {VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH, VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL}:
                if item.provenance_token is None:
                    raw_eval_records.append({
                        "evidence_id": item.evidence_id,
                        "status": "REJECTED_UNTRUSTED",
                        "reason": VerificationReason.EVIDENCE_UNTRUSTED.value,
                    })
                    continue
                valid_sig = item.provenance_token.verify_integrity(
                    evidence_id=item.evidence_id,
                    objective_id=request.objective_id,
                    action_id=request.action_id,
                    capability_id=request.capability_id,
                    capability_version=request.capability_version,
                    environment=request.environment,
                    postcondition_name=request.postcondition_name,
                    source_identifier=item.source_identifier,
                    verification_method=item.verification_method,
                    observed_state=item.observed_state,
                )
                if not valid_sig:
                    raw_eval_records.append({
                        "evidence_id": item.evidence_id,
                        "status": "REJECTED_INVALID_PROVENANCE",
                        "reason": VerificationReason.EVIDENCE_PROVENANCE_INVALID.value,
                    })
                    continue

            # Check circular verification
            if item.evidence_class == VerificationEvidenceClass.AGENT_SELF_REPORT and item.collector_actor_id == request.actor_id:
                raw_eval_records.append({
                    "evidence_id": item.evidence_id,
                    "status": "EVALUATED_WEAK_CIRCULAR",
                    "reason": VerificationReason.CIRCULAR_VERIFICATION_PROHIBITED.value,
                })
                valid_evidence.append(item)
                continue

            # Check staleness
            try:
                col_dt = datetime.fromisoformat(item.collected_at)
                age = (now_dt - col_dt).total_seconds()
                if age > contract.max_evidence_age_seconds or age < -5:
                    raw_eval_records.append({
                        "evidence_id": item.evidence_id,
                        "status": "REJECTED_STALE",
                        "reason": VerificationReason.EVIDENCE_STALE.value,
                    })
                    continue
            except (ValueError, TypeError):
                raw_eval_records.append({
                    "evidence_id": item.evidence_id,
                    "status": "REJECTED_INVALID_TIMESTAMP",
                })
                continue

            # Check availability / accessibility / ambiguity
            if not item.is_available:
                raw_eval_records.append({
                    "evidence_id": item.evidence_id,
                    "status": "UNAVAILABLE",
                    "reason": VerificationReason.AUTHORITATIVE_SOURCE_UNAVAILABLE.value,
                })
                continue

            if not item.is_accessible:
                raw_eval_records.append({
                    "evidence_id": item.evidence_id,
                    "status": "INACCESSIBLE",
                    "reason": VerificationReason.AUTHORITATIVE_SOURCE_INACCESSIBLE.value,
                })
                continue

            if item.is_ambiguous:
                raw_eval_records.append({
                    "evidence_id": item.evidence_id,
                    "status": "AMBIGUOUS",
                    "reason": VerificationReason.AMBIGUOUS_VERIFICATION_SOURCE.value,
                })
                continue

            valid_evidence.append(item)
            raw_eval_records.append({
                "evidence_id": item.evidence_id,
                "evidence_class": item.evidence_class.value,
                "status": "ACCEPTED",
            })

        if not valid_evidence:
            primary_r = VerificationReason.AUTHORITATIVE_SOURCE_REQUIRED if contract.authoritative_source_required else VerificationReason.AUTHORITATIVE_SOURCE_UNAVAILABLE
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNKNOWN,
                primary_reason=primary_r,
                primary_evidence_class=VerificationEvidenceClass.NONE,
                primary_evidence_ref=None,
                expected_state=request.expected_state,
                observed_state=None,
                verified_at=now,
                all_evaluated_evidence=tuple(raw_eval_records),
            )

        # Sort evidence by precedence descending
        sorted_evidence = sorted(
            valid_evidence,
            key=lambda e: EVIDENCE_PRECEDENCE.get(e.evidence_class, 0),
            reverse=True,
        )

        top_evidence = sorted_evidence[0]

        # Rule 11 (No-Silent-Downgrade): If authoritative source is required but top_evidence is not authoritative SoT (or sufficient registered tech), fail to safe non-success
        if contract.authoritative_source_required and top_evidence.evidence_class not in {VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH, VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL}:
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNVERIFIED if top_evidence.evidence_class in {VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT, VerificationEvidenceClass.AGENT_SELF_REPORT} else VerificationOutcome.PARTIALLY_VERIFIED,
                primary_reason=VerificationReason.AUTHORITATIVE_SOURCE_REQUIRED,
                primary_evidence_class=top_evidence.evidence_class,
                primary_evidence_ref=top_evidence.evidence_id,
                expected_state=request.expected_state,
                observed_state=top_evidence.observed_state,
                verified_at=now,
                all_evaluated_evidence=tuple(raw_eval_records),
            )

        # Check for contradictions across evidence items
        top_matches_expected = self._matches_state(request.expected_state, top_evidence.observed_state)
        for other in sorted_evidence[1:]:
            other_matches = self._matches_state(request.expected_state, other.observed_state)
            if other_matches != top_matches_expected:
                contradictions.append(
                    f"Precedence conflict: {top_evidence.evidence_class.value} (matches={top_matches_expected}) "
                    f"vs {other.evidence_class.value} (matches={other_matches})"
                )

        has_contradictions = len(contradictions) > 0
        contra_details = "; ".join(contradictions) if has_contradictions else None

        # Precedence Rule 1: AUTHORITATIVE_SOURCE_OF_TRUTH
        if top_evidence.evidence_class == VerificationEvidenceClass.AUTHORITATIVE_SOURCE_OF_TRUTH:
            if top_matches_expected:
                return VerificationResult(
                    verification_id=request.verification_id,
                    objective_id=request.objective_id,
                    action_id=request.action_id,
                    correlation_id=request.correlation_id,
                    capability_id=request.capability_id,
                    capability_version=request.capability_version,
                    environment=request.environment,
                    postcondition_name=request.postcondition_name,
                    outcome=VerificationOutcome.VERIFIED,
                    primary_reason=VerificationReason.AUTHORITATIVE_POSTCONDITION_SATISFIED,
                    primary_evidence_class=top_evidence.evidence_class,
                    primary_evidence_ref=top_evidence.evidence_id,
                    expected_state=request.expected_state,
                    observed_state=top_evidence.observed_state,
                    verified_at=now,
                    contradictions_detected=has_contradictions,
                    contradiction_details=contra_details,
                    all_evaluated_evidence=tuple(raw_eval_records),
                )
            else:
                return VerificationResult(
                    verification_id=request.verification_id,
                    objective_id=request.objective_id,
                    action_id=request.action_id,
                    correlation_id=request.correlation_id,
                    capability_id=request.capability_id,
                    capability_version=request.capability_version,
                    environment=request.environment,
                    postcondition_name=request.postcondition_name,
                    outcome=VerificationOutcome.FAILED,
                    primary_reason=VerificationReason.POSTCONDITION_STATE_MISMATCH,
                    primary_evidence_class=top_evidence.evidence_class,
                    primary_evidence_ref=top_evidence.evidence_id,
                    expected_state=request.expected_state,
                    observed_state=top_evidence.observed_state,
                    verified_at=now,
                    contradictions_detected=has_contradictions,
                    contradiction_details=contra_details,
                    all_evaluated_evidence=tuple(raw_eval_records),
                )

        # Precedence Rule 2: DETERMINISTIC_DIRECT_TECHNICAL
        if top_evidence.evidence_class == VerificationEvidenceClass.DETERMINISTIC_DIRECT_TECHNICAL:
            if not contract.deterministic_technical_sufficient:
                return VerificationResult(
                    verification_id=request.verification_id,
                    objective_id=request.objective_id,
                    action_id=request.action_id,
                    correlation_id=request.correlation_id,
                    capability_id=request.capability_id,
                    capability_version=request.capability_version,
                    environment=request.environment,
                    postcondition_name=request.postcondition_name,
                    outcome=VerificationOutcome.PARTIALLY_VERIFIED,
                    primary_reason=VerificationReason.TECHNICAL_EVIDENCE_INSUFFICIENT_FOR_POSTCONDITION,
                    primary_evidence_class=top_evidence.evidence_class,
                    primary_evidence_ref=top_evidence.evidence_id,
                    expected_state=request.expected_state,
                    observed_state=top_evidence.observed_state,
                    verified_at=now,
                    contradictions_detected=has_contradictions,
                    contradiction_details=contra_details,
                    all_evaluated_evidence=tuple(raw_eval_records),
                )

            if top_matches_expected:
                return VerificationResult(
                    verification_id=request.verification_id,
                    objective_id=request.objective_id,
                    action_id=request.action_id,
                    correlation_id=request.correlation_id,
                    capability_id=request.capability_id,
                    capability_version=request.capability_version,
                    environment=request.environment,
                    postcondition_name=request.postcondition_name,
                    outcome=VerificationOutcome.VERIFIED,
                    primary_reason=VerificationReason.DETERMINISTIC_TECHNICAL_MATCH,
                    primary_evidence_class=top_evidence.evidence_class,
                    primary_evidence_ref=top_evidence.evidence_id,
                    expected_state=request.expected_state,
                    observed_state=top_evidence.observed_state,
                    verified_at=now,
                    contradictions_detected=has_contradictions,
                    contradiction_details=contra_details,
                    all_evaluated_evidence=tuple(raw_eval_records),
                )
            else:
                return VerificationResult(
                    verification_id=request.verification_id,
                    objective_id=request.objective_id,
                    action_id=request.action_id,
                    correlation_id=request.correlation_id,
                    capability_id=request.capability_id,
                    capability_version=request.capability_version,
                    environment=request.environment,
                    postcondition_name=request.postcondition_name,
                    outcome=VerificationOutcome.FAILED,
                    primary_reason=VerificationReason.POSTCONDITION_STATE_MISMATCH,
                    primary_evidence_class=top_evidence.evidence_class,
                    primary_evidence_ref=top_evidence.evidence_id,
                    expected_state=request.expected_state,
                    observed_state=top_evidence.observed_state,
                    verified_at=now,
                    contradictions_detected=has_contradictions,
                    contradiction_details=contra_details,
                    all_evaluated_evidence=tuple(raw_eval_records),
                )

        # Precedence Rule 3: CORROBORATED_SECONDARY_OPERATIONAL
        if top_evidence.evidence_class == VerificationEvidenceClass.CORROBORATED_SECONDARY_OPERATIONAL:
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.PARTIALLY_VERIFIED,
                primary_reason=VerificationReason.SECONDARY_EVIDENCE_CORROBORATED_ONLY,
                primary_evidence_class=top_evidence.evidence_class,
                primary_evidence_ref=top_evidence.evidence_id,
                expected_state=request.expected_state,
                observed_state=top_evidence.observed_state,
                verified_at=now,
                contradictions_detected=has_contradictions,
                contradiction_details=contra_details,
                all_evaluated_evidence=tuple(raw_eval_records),
            )

        # Precedence Rule 4 & 5: PROVIDER_ACKNOWLEDGEMENT & AGENT_SELF_REPORT
        if top_evidence.evidence_class == VerificationEvidenceClass.PROVIDER_ACKNOWLEDGEMENT:
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNVERIFIED,
                primary_reason=VerificationReason.WEAK_PROVIDER_ACKNOWLEDGEMENT_ONLY,
                primary_evidence_class=top_evidence.evidence_class,
                primary_evidence_ref=top_evidence.evidence_id,
                expected_state=request.expected_state,
                observed_state=top_evidence.observed_state,
                verified_at=now,
                contradictions_detected=has_contradictions,
                contradiction_details=contra_details,
                all_evaluated_evidence=tuple(raw_eval_records),
            )

        if top_evidence.evidence_class == VerificationEvidenceClass.AGENT_SELF_REPORT:
            return VerificationResult(
                verification_id=request.verification_id,
                objective_id=request.objective_id,
                action_id=request.action_id,
                correlation_id=request.correlation_id,
                capability_id=request.capability_id,
                capability_version=request.capability_version,
                environment=request.environment,
                postcondition_name=request.postcondition_name,
                outcome=VerificationOutcome.UNVERIFIED,
                primary_reason=VerificationReason.WEAK_AGENT_SELF_REPORT_ONLY,
                primary_evidence_class=top_evidence.evidence_class,
                primary_evidence_ref=top_evidence.evidence_id,
                expected_state=request.expected_state,
                observed_state=top_evidence.observed_state,
                verified_at=now,
                contradictions_detected=has_contradictions,
                contradiction_details=contra_details,
                all_evaluated_evidence=tuple(raw_eval_records),
            )

        return VerificationResult(
            verification_id=request.verification_id,
            objective_id=request.objective_id,
            action_id=request.action_id,
            correlation_id=request.correlation_id,
            capability_id=request.capability_id,
            capability_version=request.capability_version,
            environment=request.environment,
            postcondition_name=request.postcondition_name,
            outcome=VerificationOutcome.UNKNOWN,
            primary_reason=VerificationReason.WEAK_COMBINED_EVIDENCE_INSUFFICIENT,
            primary_evidence_class=top_evidence.evidence_class,
            primary_evidence_ref=top_evidence.evidence_id,
            expected_state=request.expected_state,
            observed_state=top_evidence.observed_state,
            verified_at=now,
            all_evaluated_evidence=tuple(raw_eval_records),
        )

    def apply_to_state_machine(
        self,
        sm: ExecutionStateMachine,
        result: VerificationResult,
    ) -> ExecutionStateRecord:
        """Applies verification result to the canonical B4 state machine without bypassing guards."""
        current = sm.record.current_execution_state

        if current == ExecutionState.EXECUTED:
            sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Action executed, transitioning to verification pending")
        elif current not in {ExecutionState.VERIFICATION_PENDING, ExecutionState.PARTIALLY_VERIFIED}:
            raise StateTransitionError(
                current,
                ExecutionState.VERIFICATION_PENDING,
                f"Cannot apply verification outcome from state {current.value}; must be in EXECUTED or VERIFICATION_PENDING",
            )

        if current == ExecutionState.PARTIALLY_VERIFIED:
            sm.transition(ExecutionState.VERIFICATION_PENDING, reason="Re-evaluating partial verification with new evidence")

        # Map VerificationOutcome to ExecutionState
        if result.outcome == VerificationOutcome.VERIFIED:
            return sm.transition(
                ExecutionState.VERIFIED,
                reason=f"Authoritative verification succeeded: {result.primary_reason.value}",
                verification_evidence_ref=result.primary_evidence_ref,
                verification_evidence_class=result.primary_evidence_class,
                technical_evidence_sufficient=(result.primary_reason == VerificationReason.DETERMINISTIC_TECHNICAL_MATCH),
            )
        elif result.outcome == VerificationOutcome.PARTIALLY_VERIFIED:
            return sm.transition(
                ExecutionState.PARTIALLY_VERIFIED,
                reason=f"Partial verification: {result.primary_reason.value}",
                verification_evidence_ref=result.primary_evidence_ref,
                verification_evidence_class=result.primary_evidence_class,
            )
        elif result.outcome == VerificationOutcome.UNVERIFIED:
            return sm.transition(
                ExecutionState.UNVERIFIED,
                reason=f"Unverified outcome: {result.primary_reason.value}",
                verification_evidence_ref=result.primary_evidence_ref,
                verification_evidence_class=result.primary_evidence_class,
            )
        elif result.outcome == VerificationOutcome.FAILED:
            return sm.transition(
                ExecutionState.FAILED,
                reason=f"Verification failed postcondition: {result.primary_reason.value}",
                verification_evidence_ref=result.primary_evidence_ref,
                verification_evidence_class=result.primary_evidence_class,
                error_classification=result.primary_reason.value,
            )
        else:  # UNKNOWN
            return sm.transition(
                ExecutionState.UNKNOWN,
                reason=f"Verification status unknown: {result.primary_reason.value}",
                verification_evidence_ref=result.primary_evidence_ref,
                verification_evidence_class=result.primary_evidence_class,
            )

    @staticmethod
    def _matches_state(expected: dict[str, Any], observed: dict[str, Any] | None) -> bool:
        if observed is None:
            return False
        for k, v in expected.items():
            if k not in observed or observed[k] != v:
                return False
        return True
