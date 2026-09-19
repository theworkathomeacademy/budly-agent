"""BAE Pilot 001 Wave 1 Certification Evidence Packaging (Gate B Step B12).

Defines the formal certification evidence packaging data structures, evidence assemblies,
and validation logic for the five Wave 1 capabilities:
1. BAE-OPS-OBSERVE-001 (Operational Observation and Telemetry Ingestion)
2. BAE-OPS-DETECT-001 (Anomaly and Variance Detection)
3. BAE-OPS-VERIFY-001 (System-of-Record Verification Engine Consumer)
4. BAE-OPS-PACKAGE-001 (Operational Context & Evidence Packaging)
5. BAE-OPS-ESCALATE-001 (Governed Operational Escalation)

Governing Invariants:
- B12 is an evidence packaging and certification-readiness step; it does NOT grant certification.
- No capability lifecycle state is set to CERTIFIED or AUTHORIZED_FOR_ENVIRONMENT.
- No canonical executable flag is set to True (all remain False).
- Current Certified Maturity remains unset (None). Target maturity M3 remains target only.
- Gate D remains NOT AUTHORIZED; production execution is strictly prohibited.
- Recommendation states are strictly: READY_FOR_CERTIFICATION_REVIEW, NOT_READY_FOR_CERTIFICATION, BLOCKED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .capability_registry import BAECapabilityRegistry
from .types import (
    ApprovalLevel,
    AuthorityClass,
    AutonomyMaturity,
    CapabilityLifecycleState,
    PilotWave,
    ToolAuthorityClass,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CertificationRecommendationState(str, Enum):
    """Governed certification recommendation states for Step B12."""
    READY_FOR_CERTIFICATION_REVIEW = "READY_FOR_CERTIFICATION_REVIEW"
    NOT_READY_FOR_CERTIFICATION = "NOT_READY_FOR_CERTIFICATION"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class Wave1CapabilityCertificationPackage:
    """Formal, auditable certification evidence package for a Wave 1 capability."""
    capability_id: str
    capability_version: str
    capability_name: str
    purpose: str
    scope: str
    authority_class: AuthorityClass
    current_certified_maturity: AutonomyMaturity | None
    target_pilot_entry_maturity: AutonomyMaturity
    maximum_governable_maturity: AutonomyMaturity | None
    approval_class: ApprovalLevel
    tool_authority: ToolAuthorityClass
    lifecycle_state: CapabilityLifecycleState
    executable_state: bool
    certification_state: str
    activation_state: str
    allowed_fixture_environments: tuple[str, ...]
    prohibited_environments: tuple[str, ...]
    actor_requirements: tuple[str, ...]
    permission_requirements: tuple[str, ...]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    data_classes: tuple[str, ...]
    approved_sources: tuple[str, ...]
    authoritative_source_of_truth: str | None
    verification_requirement: str
    verification_method: str
    accepted_evidence_classes: tuple[str, ...]
    retry_idempotency_requirements: str
    fallback_behavior: str
    safe_inaction_behavior: str
    escalation_behavior: str
    audit_requirements: str
    evidence_persistence_requirements: str
    correlation_lineage_requirements: str
    applicable_kill_switch_scopes: tuple[str, ...]
    human_override_behavior: str
    implementation_file_references: tuple[str, ...]
    implementation_test_references: tuple[str, ...]
    at_acceptance_references: tuple[str, ...]
    requirement_references: tuple[str, ...]
    audit_evidence_references: tuple[str, ...]
    known_limitations: tuple[str, ...]
    unresolved_dependencies: tuple[str, ...]
    launch_blockers: tuple[str, ...]
    certification_recommendation: CertificationRecommendationState
    rationale: str
    packaged_at: str = field(default_factory=utc_now)
    packager: str = "Antigravity"

    @property
    def authorized_environments(self) -> tuple[str, ...]:
        """Backward compatibility alias for fixture-allowed non-production environments."""
        return self.allowed_fixture_environments

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["authority_class"] = self.authority_class.value
        data["current_certified_maturity"] = self.current_certified_maturity.value if self.current_certified_maturity else None
        data["target_pilot_entry_maturity"] = self.target_pilot_entry_maturity.value
        data["maximum_governable_maturity"] = self.maximum_governable_maturity.value if self.maximum_governable_maturity else None
        data["approval_class"] = self.approval_class.value
        data["tool_authority"] = self.tool_authority.value
        data["lifecycle_state"] = self.lifecycle_state.value
        data["certification_recommendation"] = self.certification_recommendation.value
        return data


class Wave1CertificationEvidenceBuilder:
    """Constructs deterministic, verified Wave 1 certification evidence packages."""

    @classmethod
    def build_observe_package(cls, registry: BAECapabilityRegistry | None = None) -> Wave1CapabilityCertificationPackage:
        reg = registry or BAECapabilityRegistry.load_seed()
        seed = reg.get("BAE-OPS-OBSERVE-001", "1.0")
        if seed is None:
            raise ValueError("Canonical seed BAE-OPS-OBSERVE-001:1.0 not found in registry")

        return Wave1CapabilityCertificationPackage(
            capability_id=seed.capability_id,
            capability_version=seed.capability_version,
            capability_name=seed.capability_name,
            purpose="Governed read-only operational telemetry and metric observation.",
            scope="Non-production operational monitoring, health checks, and anomaly observation.",
            authority_class=seed.authority_class or AuthorityClass.L1,
            current_certified_maturity=seed.current_certified_maturity,  # None
            target_pilot_entry_maturity=seed.target_pilot_entry_maturity or AutonomyMaturity.M3,
            maximum_governable_maturity=seed.maximum_governable_maturity,
            approval_class=seed.approval_level or ApprovalLevel.A0,
            tool_authority=seed.tool_authority or ToolAuthorityClass.T0,
            lifecycle_state=seed.lifecycle_state,  # DEFINED
            executable_state=seed.executable,  # False
            certification_state="UNCERTIFIED / PENDING_GOVERNED_REVIEW",
            activation_state="INACTIVE / NON_EXECUTABLE",
            allowed_fixture_environments=tuple(sorted(seed.allowed_environments)),
            prohibited_environments=("production", "staging", "external_live"),
            actor_requirements=("bae-steward-001", "bae_steward", "system_internal"),
            permission_requirements=("bae:execute", "bae:telemetry"),
            input_schema={
                "source_identifier": "string (registered)",
                "query_params": "object (metric filters, timestamps)",
                "correlation": "CorrelationRecord (objective_id, action_id, correlation_id)",
            },
            output_schema={
                "observation_id": "UUID string",
                "source_identifier": "string",
                "observed_data": "sanitized dictionary",
                "observed_at": "ISO 8601 UTC string",
                "is_authoritative": "boolean",
                "data_hash": "SHA-256 hex string",
            },
            data_classes=("operational_telemetry", "system_health_metrics"),
            approved_sources=("postgres_ops_telemetry_db", "mock_telemetry_source", "test_source"),
            authoritative_source_of_truth="postgres_ops_telemetry_db",
            verification_requirement="Telemetry ingestion verified via direct database inspection or registered source query.",
            verification_method="POSTGRESQL_DIRECT_QUERY",
            accepted_evidence_classes=("AUTHORITATIVE_SOURCE_OF_TRUTH", "DETERMINISTIC_DIRECT_TECHNICAL"),
            retry_idempotency_requirements="Read-only queries are naturally idempotent; deduplicated on action_id.",
            fallback_behavior="Safe stop on source unreachability; returns empty result and records audit event.",
            safe_inaction_behavior="Halts execution without side effects when source or authorization is unavailable.",
            escalation_behavior="Escalates on persistent database unreachability or schema violation.",
            audit_requirements="Every observation emits an append-only AuditEventRecord with sanitized params.",
            evidence_persistence_requirements="Persists raw and hashed telemetry state into bae_audit.evidence_records.",
            correlation_lineage_requirements="Carries unbroken objective_id, action_id, correlation_id lineage.",
            applicable_kill_switch_scopes=("GLOBAL", "ENVIRONMENT", "CAPABILITY", "TOOL", "OBJECTIVE"),
            human_override_behavior="Immediate stop before data query if human override active.",
            implementation_file_references=(
                "src/budly_runtime/bae/wave1_capabilities.py",
                "src/budly_runtime/bae/policy_evaluator.py",
                "src/budly_runtime/bae/tool_gateway.py",
                "src/budly_runtime/bae/audit_persistence.py",
            ),
            implementation_test_references=(
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_01_authorized_read_only_observation_succeeds",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_02_observe_cannot_write_external_state",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_03_unregistered_source_denied",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_04_missing_permission_or_denied_environment_denied",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_05_active_kill_switch_stops_observe",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_06_observation_is_audited",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_07_authoritative_source_identity_preserved",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_08_correlation_lineage_preserved",
            ),
            at_acceptance_references=(
                "AT-001", "AT-006", "AT-011", "AT-016", "AT-019", "AT-033", "AT-034", "AT-043", "AT-044", "AT-046", "AT-050", "AT-056", "AT-063", "AT-066", "AT-067", "AT-068", "AT-069", "AT-070", "test_composed_wave1_acceptance_flow",
            ),
            requirement_references=(
                "BAE-P001-AUTH-001", "BAE-P001-AUTH-006", "BAE-P001-PERM-001", "BAE-P001-TOOL-001", "BAE-P001-TOOL-005", "BAE-P001-AUD-001", "BAE-P001-AUD-002", "BAE-P001-KILL-004", "BAE-P001-KILL-005", "BAE-P001-KILL-007", "BAE-P001-SELF-001", "BAE-P001-STATE-004", "BAE-P001-TOOL-009", "BAE-P001-REL-006", "BAE-P001-REL-007", "BAE-P001-REL-008", "BAE-P001-REL-009", "BAE-P001-REL-010",
            ),
            audit_evidence_references=(
                "bae_audit.audit_events (event_type=CAPABILITY_EXECUTION_EVENT)",
                "bae_audit.evidence_records (evidence_class=AUTHORITATIVE_SOURCE_OF_TRUTH)",
            ),
            known_limitations=(
                "Bounded strictly to non-production environments; cannot query production telemetry without Gate D authorization.",
            ),
            unresolved_dependencies=(),
            launch_blockers=(),
            certification_recommendation=CertificationRecommendationState.READY_FOR_CERTIFICATION_REVIEW,
            rationale="All B1-B11 requirements and AT acceptance tests passed deterministically. Control boundaries hold.",
        )

    @classmethod
    def build_detect_package(cls, registry: BAECapabilityRegistry | None = None) -> Wave1CapabilityCertificationPackage:
        reg = registry or BAECapabilityRegistry.load_seed()
        seed = reg.get("BAE-OPS-DETECT-001", "1.0")
        if seed is None:
            raise ValueError("Canonical seed BAE-OPS-DETECT-001:1.0 not found in registry")

        return Wave1CapabilityCertificationPackage(
            capability_id=seed.capability_id,
            capability_version=seed.capability_version,
            capability_name=seed.capability_name,
            purpose="Deterministic operational condition and anomaly recognition over observed state.",
            scope="Evaluation of registered detection rules against telemetry without autonomous LLM judgment.",
            authority_class=seed.authority_class or AuthorityClass.L1,
            current_certified_maturity=seed.current_certified_maturity,
            target_pilot_entry_maturity=seed.target_pilot_entry_maturity or AutonomyMaturity.M3,
            maximum_governable_maturity=seed.maximum_governable_maturity,
            approval_class=seed.approval_level or ApprovalLevel.A0,
            tool_authority=seed.tool_authority or ToolAuthorityClass.T1,
            lifecycle_state=seed.lifecycle_state,
            executable_state=seed.executable,
            certification_state="UNCERTIFIED / PENDING_GOVERNED_REVIEW",
            activation_state="INACTIVE / NON_EXECUTABLE",
            allowed_fixture_environments=tuple(sorted(seed.allowed_environments)),
            prohibited_environments=("production", "staging", "external_live"),
            actor_requirements=("bae-steward-001", "bae_steward", "system_internal"),
            permission_requirements=("bae:execute", "bae:telemetry"),
            input_schema={
                "rule_id": "string (registered rule identifier)",
                "condition_evaluated": "string (deterministic expression)",
                "observed_value": "Any (numeric / structured)",
                "expected_value": "Any",
                "input_evidence_refs": "tuple of UUID strings",
                "severity": "string (INFO, WARNING, CRITICAL)",
            },
            output_schema={
                "detection_id": "UUID string",
                "rule_id": "string",
                "is_matched": "boolean",
                "severity": "string",
                "condition_evaluated": "string",
                "observed_value": "Any",
                "detected_at": "ISO 8601 UTC string",
                "input_evidence_refs": "tuple of UUID strings",
            },
            data_classes=("operational_telemetry", "anomaly_evaluations"),
            approved_sources=("internal_rule_engine", "registered_detectors"),
            authoritative_source_of_truth="internal_rule_engine",
            verification_requirement="Deterministic mathematical/logical comparison against rule thresholds.",
            verification_method="DETERMINISTIC_PAYLOAD_COMPARISON",
            accepted_evidence_classes=("DETERMINISTIC_DIRECT_TECHNICAL", "AUTHORITATIVE_SOURCE_OF_TRUTH"),
            retry_idempotency_requirements="Pure compute function; deterministic output on identical inputs.",
            fallback_behavior="Safe stop on unparseable rule or missing evidence; produces unmatched state.",
            safe_inaction_behavior="Does not fabricate detection or trigger actions on malformed inputs.",
            escalation_behavior="Packages matched anomalies for downstream ESCALATE evaluation.",
            audit_requirements="Logs condition evaluation, inputs, outputs, and rule ID in audit persistence.",
            evidence_persistence_requirements="Saves detection proof records linked to input observation evidence IDs.",
            correlation_lineage_requirements="Maintains unbroken lineage back to initiating objective and observation.",
            applicable_kill_switch_scopes=("GLOBAL", "ENVIRONMENT", "CAPABILITY", "TOOL", "OBJECTIVE"),
            human_override_behavior="Halt detection evaluation immediately on active override.",
            implementation_file_references=(
                "src/budly_runtime/bae/wave1_capabilities.py",
                "src/budly_runtime/bae/policy_evaluator.py",
                "src/budly_runtime/bae/audit_persistence.py",
            ),
            implementation_test_references=(
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_09_matching_deterministic_condition_detected",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_10_non_matching_condition_does_not_trigger",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_11_detector_rule_and_version_recorded",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_12_detection_preserves_input_evidence_reference",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_13_unknown_input_does_not_become_positive_detection",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_14_detector_cannot_modify_external_state",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_15_detection_is_auditable",
            ),
            at_acceptance_references=(
                "AT-001", "AT-006", "AT-016", "AT-033", "AT-044", "AT-063", "AT-066", "AT-067", "AT-068", "AT-069", "AT-070", "test_composed_wave1_acceptance_flow",
            ),
            requirement_references=(
                "BAE-P001-AUTH-001", "BAE-P001-AUTH-006", "BAE-P001-TOOL-001", "BAE-P001-AUD-001", "BAE-P001-KILL-005", "BAE-P001-TOOL-009", "BAE-P001-REL-006", "BAE-P001-REL-007", "BAE-P001-REL-008", "BAE-P001-REL-009", "BAE-P001-REL-010",
            ),
            audit_evidence_references=(
                "bae_audit.audit_events (event_type=CAPABILITY_EXECUTION_EVENT)",
                "bae_audit.evidence_records (evidence_class=DETERMINISTIC_DIRECT_TECHNICAL)",
            ),
            known_limitations=(
                "Detector cannot autonomously create remediation plans or execute writes.",
            ),
            unresolved_dependencies=(),
            launch_blockers=(),
            certification_recommendation=CertificationRecommendationState.READY_FOR_CERTIFICATION_REVIEW,
            rationale="Deterministic detection logic proven across test and acceptance harnesses. B1-B11 compliant.",
        )

    @classmethod
    def build_verify_package(cls, registry: BAECapabilityRegistry | None = None) -> Wave1CapabilityCertificationPackage:
        reg = registry or BAECapabilityRegistry.load_seed()
        seed = reg.get("BAE-OPS-VERIFY-001", "1.0")
        if seed is None:
            raise ValueError("Canonical seed BAE-OPS-VERIFY-001:1.0 not found in registry")

        return Wave1CapabilityCertificationPackage(
            capability_id=seed.capability_id,
            capability_version=seed.capability_version,
            capability_name=seed.capability_name,
            purpose="Authoritative System-of-Record verification consuming the B5 Verification Engine.",
            scope="Postcondition verification enforcing authoritative evidence precedence and rejecting unverified claims.",
            authority_class=seed.authority_class or AuthorityClass.L1,
            current_certified_maturity=seed.current_certified_maturity,
            target_pilot_entry_maturity=seed.target_pilot_entry_maturity or AutonomyMaturity.M3,
            maximum_governable_maturity=seed.maximum_governable_maturity,
            approval_class=seed.approval_level or ApprovalLevel.A0,
            tool_authority=seed.tool_authority or ToolAuthorityClass.T0,
            lifecycle_state=seed.lifecycle_state,
            executable_state=seed.executable,
            certification_state="UNCERTIFIED / PENDING_GOVERNED_REVIEW",
            activation_state="INACTIVE / NON_EXECUTABLE",
            allowed_fixture_environments=tuple(sorted(seed.allowed_environments)),
            prohibited_environments=("production", "staging", "external_live"),
            actor_requirements=("bae-steward-001", "bae_steward", "verification_engine"),
            permission_requirements=("bae:execute", "bae:telemetry"),
            input_schema={
                "postcondition_name": "string (registered contract postcondition)",
                "expected_state": "dict",
                "evidence_items": "tuple of VerificationEvidenceItem",
                "access_decision": "VerificationAccessDecision (cryptographically signed)",
            },
            output_schema={
                "verification_id": "UUID string",
                "outcome": "VerificationOutcome (VERIFIED, PARTIALLY_VERIFIED, UNVERIFIED, FAILED, UNKNOWN)",
                "primary_reason": "VerificationReason",
                "verified_at": "ISO 8601 UTC string",
                "discrepancies": "list of discrepancies",
                "evaluated_evidence_ids": "tuple of UUID strings",
            },
            data_classes=("operational_telemetry", "verification_proofs"),
            approved_sources=("postgres_ops_telemetry_db", "authoritative_sor"),
            authoritative_source_of_truth="postgres_ops_telemetry_db",
            verification_requirement="Strict evaluation against registered postcondition contracts with provenance checks.",
            verification_method="POSTGRESQL_DIRECT_QUERY",
            accepted_evidence_classes=("AUTHORITATIVE_SOURCE_OF_TRUTH", "DETERMINISTIC_DIRECT_TECHNICAL"),
            retry_idempotency_requirements="Verification evaluations are idempotent read operations.",
            fallback_behavior="Fails safe to UNVERIFIED or UNKNOWN when evidence is missing or ambiguous.",
            safe_inaction_behavior="Never promotes partial, self-reported, or acknowledgement evidence to VERIFIED.",
            escalation_behavior="Escalates on verification failure or discrepancies.",
            audit_requirements="All verification requests and evaluated outcomes are recorded in durable audit persistence.",
            evidence_persistence_requirements="Stores verified evidence provenance tokens and evaluation results.",
            correlation_lineage_requirements="Carries objective, action, and correlation IDs throughout evaluation.",
            applicable_kill_switch_scopes=("GLOBAL", "ENVIRONMENT", "CAPABILITY", "TOOL", "OBJECTIVE"),
            human_override_behavior="Halts verification engine execution immediately upon active override.",
            implementation_file_references=(
                "src/budly_runtime/bae/wave1_capabilities.py",
                "src/budly_runtime/bae/verification_engine.py",
                "src/budly_runtime/bae/state_machine.py",
                "src/budly_runtime/bae/audit_persistence.py",
            ),
            implementation_test_references=(
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_16_authoritative_evidence_can_verify_registered_postcondition",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_17_deterministic_technical_evidence_verifies_when_allowed",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_18_provider_acknowledgement_alone_cannot_verify",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_19_agent_self_report_cannot_verify",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_20_unknown_outcome_remains_distinct",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_21_unverified_outcome_remains_distinct",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_22_partially_verified_outcome_remains_distinct",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_23_verification_evidence_persisted_to_b7",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_24_active_kill_switch_prevents_verification",
            ),
            at_acceptance_references=(
                "AT-021", "AT-022", "AT-023", "AT-024", "AT-025", "AT-026", "AT-056", "AT-063", "AT-064", "AT-066", "AT-067", "AT-068", "AT-069", "AT-070", "test_composed_wave1_acceptance_flow",
            ),
            requirement_references=(
                "BAE-P001-STATE-001", "BAE-P001-VER-002", "BAE-P001-VER-003", "BAE-P001-VER-004", "BAE-P001-VER-005", "BAE-P001-STATE-002", "BAE-P001-VER-006", "BAE-P001-STATE-003", "BAE-P001-STATE-004", "BAE-P001-VER-007", "BAE-P001-TOOL-009", "BAE-P001-VER-008", "BAE-P001-DATA-004", "BAE-P001-REL-006", "BAE-P001-REL-007", "BAE-P001-REL-008", "BAE-P001-REL-009", "BAE-P001-REL-010",
            ),
            audit_evidence_references=(
                "bae_audit.audit_events (event_type=CAPABILITY_EXECUTION_EVENT)",
                "bae_audit.evidence_records (evidence_class=AUTHORITATIVE_SOURCE_OF_TRUTH)",
            ),
            known_limitations=(
                "Requires valid, cryptographically signed VerificationAccessDecision; cannot verify unauthenticated requests.",
            ),
            unresolved_dependencies=(),
            launch_blockers=(),
            certification_recommendation=CertificationRecommendationState.READY_FOR_CERTIFICATION_REVIEW,
            rationale="B5 AuthoritativeVerificationEngine contract integrity proven across all 6 AT verification tests.",
        )

    @classmethod
    def build_package_package(cls, registry: BAECapabilityRegistry | None = None) -> Wave1CapabilityCertificationPackage:
        reg = registry or BAECapabilityRegistry.load_seed()
        seed = reg.get("BAE-OPS-PACKAGE-001", "1.0")
        if seed is None:
            raise ValueError("Canonical seed BAE-OPS-PACKAGE-001:1.0 not found in registry")

        return Wave1CapabilityCertificationPackage(
            capability_id=seed.capability_id,
            capability_version=seed.capability_version,
            capability_name=seed.capability_name,
            purpose="Operational context and evidence assembly without creating autonomous execution authority.",
            scope="Compilation of verified observations, detections, and execution state into immutable diagnostic containers.",
            authority_class=seed.authority_class or AuthorityClass.L1,
            current_certified_maturity=seed.current_certified_maturity,
            target_pilot_entry_maturity=seed.target_pilot_entry_maturity or AutonomyMaturity.M3,
            maximum_governable_maturity=seed.maximum_governable_maturity,
            approval_class=seed.approval_level or ApprovalLevel.A0,
            tool_authority=seed.tool_authority or ToolAuthorityClass.T1,
            lifecycle_state=seed.lifecycle_state,
            executable_state=seed.executable,
            certification_state="UNCERTIFIED / PENDING_GOVERNED_REVIEW",
            activation_state="INACTIVE / NON_EXECUTABLE",
            allowed_fixture_environments=tuple(sorted(seed.allowed_environments)),
            prohibited_environments=("production", "staging", "external_live"),
            actor_requirements=("bae-steward-001", "bae_steward", "system_internal"),
            permission_requirements=("bae:execute", "bae:telemetry"),
            input_schema={
                "execution_state": "ExecutionState",
                "verification_state": "VerificationState",
                "evidence_references": "tuple of UUID strings",
                "detected_conditions": "tuple of dicts",
                "permitted_next_actions": "tuple of action strings",
                "prohibited_next_actions": "tuple of action strings",
                "context_data": "dict",
            },
            output_schema={
                "package_id": "UUID string",
                "package_hash": "SHA-256 hex string",
                "created_at": "ISO 8601 UTC string",
                "is_authoritative": "boolean",
                "sanitized_context": "dict (PII/secrets redacted)",
            },
            data_classes=("operational_context", "diagnostic_packages"),
            approved_sources=("internal_context_packager",),
            authoritative_source_of_truth="internal_context_packager",
            verification_requirement="Cryptographic SHA-256 context packaging and sanitization validation.",
            verification_method="DETERMINISTIC_PAYLOAD_COMPARISON",
            accepted_evidence_classes=("DETERMINISTIC_DIRECT_TECHNICAL",),
            retry_idempotency_requirements="Deterministic pure packaging compute function.",
            fallback_behavior="Safe stop on sanitization error; fails closed.",
            safe_inaction_behavior="Packaging creates ZERO execution authority; cannot bypass B2 or satisfy human approvals.",
            escalation_behavior="Hands sanitized diagnostic packages off to ESCALATE controller.",
            audit_requirements="Emits audit events and persists package hash and metadata in B7 storage.",
            evidence_persistence_requirements="Persists context packages into bae_audit.evidence_records.",
            correlation_lineage_requirements="Preserves complete objective_id, action_id, correlation_id.",
            applicable_kill_switch_scopes=("GLOBAL", "ENVIRONMENT", "CAPABILITY", "TOOL", "OBJECTIVE"),
            human_override_behavior="Halts packaging immediately on human override.",
            implementation_file_references=(
                "src/budly_runtime/bae/wave1_capabilities.py",
                "src/budly_runtime/bae/audit_persistence.py",
                "src/budly_runtime/bae/policy_evaluator.py",
            ),
            implementation_test_references=(
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_25_package_contains_lineage",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_26_package_contains_capability_and_version",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_27_package_contains_evidence_references",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_28_package_contains_verification_state",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_29_package_distinguishes_permitted_and_prohibited_actions",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_30_package_sanitizes_pii_and_secrets",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_31_package_cannot_authorize_another_action",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_32_package_creation_is_audited",
            ),
            at_acceptance_references=(
                "AT-033", "AT-036", "AT-039", "AT-040", "AT-063", "AT-066", "AT-067", "AT-068", "AT-069", "AT-070", "test_composed_wave1_acceptance_flow",
            ),
            requirement_references=(
                "BAE-P001-AUD-001", "BAE-P001-DATA-001", "BAE-P001-AUD-004", "BAE-P001-ESC-002", "BAE-P001-ESC-003", "BAE-P001-TOOL-009", "BAE-P001-DATA-003", "BAE-P001-REL-006", "BAE-P001-REL-007", "BAE-P001-REL-008", "BAE-P001-REL-009", "BAE-P001-REL-010",
            ),
            audit_evidence_references=(
                "bae_audit.audit_events (event_type=CAPABILITY_EXECUTION_EVENT)",
                "bae_audit.evidence_records (evidence_class=DETERMINISTIC_DIRECT_TECHNICAL)",
            ),
            known_limitations=(
                "Cannot mutate system or capability state; strictly a read/package diagnostic component.",
            ),
            unresolved_dependencies=(),
            launch_blockers=(),
            certification_recommendation=CertificationRecommendationState.READY_FOR_CERTIFICATION_REVIEW,
            rationale="Context assembly, PII redaction, and non-authorizing semantics verified in B10 and B11.",
        )

    @classmethod
    def build_escalate_package(cls, registry: BAECapabilityRegistry | None = None) -> Wave1CapabilityCertificationPackage:
        reg = registry or BAECapabilityRegistry.load_seed()
        seed = reg.get("BAE-OPS-ESCALATE-001", "1.0")
        if seed is None:
            raise ValueError("Canonical seed BAE-OPS-ESCALATE-001:1.0 not found in registry")

        return Wave1CapabilityCertificationPackage(
            capability_id=seed.capability_id,
            capability_version=seed.capability_version,
            capability_name=seed.capability_name,
            purpose="Governed internal escalation packaging and routing consuming the B8 Escalation Controller.",
            scope="Internal operational review routing with strictly prohibited external/customer routing.",
            authority_class=seed.authority_class or AuthorityClass.L1,
            current_certified_maturity=seed.current_certified_maturity,
            target_pilot_entry_maturity=seed.target_pilot_entry_maturity or AutonomyMaturity.M3,
            maximum_governable_maturity=seed.maximum_governable_maturity,
            approval_class=seed.approval_level or ApprovalLevel.A0,
            tool_authority=seed.tool_authority or ToolAuthorityClass.T2,
            lifecycle_state=seed.lifecycle_state,
            executable_state=seed.executable,
            certification_state="UNCERTIFIED / PENDING_GOVERNED_REVIEW",
            activation_state="INACTIVE / NON_EXECUTABLE",
            allowed_fixture_environments=tuple(sorted(seed.allowed_environments)),
            prohibited_environments=("production", "staging", "external_live"),
            actor_requirements=("bae-steward-001", "bae_steward", "system_internal"),
            permission_requirements=("bae:execute", "bae:bounded_write"),
            input_schema={
                "authority_level": "AuthorityClass",
                "autonomy_maturity": "AutonomyMaturity",
                "approval_level": "ApprovalLevel",
                "execution_state": "ExecutionState",
                "escalation_reason": "EscalationReason",
                "escalation_priority": "EscalationPriority",
                "what_occurred_summary": "string",
                "evidence_references": "list of strings",
            },
            output_schema={
                "escalation_id": "UUID string",
                "delivery_state": "EscalationDeliveryState (SENT, SUPPRESSED, FAILED)",
                "target_destination": "string (registered internal route)",
                "created_at": "ISO 8601 UTC string",
            },
            data_classes=("operational_escalations", "human_review_packages"),
            approved_sources=("internal_escalation_controller",),
            authoritative_source_of_truth="internal_escalation_controller",
            verification_requirement="Delivery acknowledgment from registered internal system route.",
            verification_method="SECONDARY_AUDIT_LOG_CORROBORATION",
            accepted_evidence_classes=("CORROBORATED_SECONDARY_OPERATIONAL", "AUTHORITATIVE_SOURCE_OF_TRUTH"),
            retry_idempotency_requirements="Rate-limited and deduplicated via escalation signature window.",
            fallback_behavior="Fails safe to safe inaction if route is unavailable.",
            safe_inaction_behavior="Customer routes strictly prohibited; external communication attempt raises ValueError.",
            escalation_behavior="Self-contained terminal governance escalation handler.",
            audit_requirements="Logs escalation creation, routing, delivery, and human response reference in B7.",
            evidence_persistence_requirements="Persists escalation package and provenance in bae_audit.evidence_records.",
            correlation_lineage_requirements="Full unbroken lineage (objective_id, action_id, correlation_id).",
            applicable_kill_switch_scopes=("GLOBAL", "ENVIRONMENT", "CAPABILITY", "TOOL", "OBJECTIVE"),
            human_override_behavior="Halts escalation immediately if kill switch or human override is active.",
            implementation_file_references=(
                "src/budly_runtime/bae/wave1_capabilities.py",
                "src/budly_runtime/bae/escalation.py",
                "src/budly_runtime/bae/policy_evaluator.py",
                "src/budly_runtime/bae/audit_persistence.py",
            ),
            implementation_test_references=(
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_33_valid_qualifying_condition_creates_b8_escalation_package",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_34_non_qualifying_condition_does_not_escalate",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_35_route_must_be_registered_internal",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_36_external_customer_facing_route_prohibited",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_37_escalation_is_deduplicated",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_38_acknowledgement_does_not_create_approval",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_39_human_response_requires_fresh_b2_authorization",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_40_b9_kill_switch_prevents_escalation_execution",
                "tests/test_bae_step_b10_wave1_capabilities.py::TestBAEStepB10Wave1Capabilities::test_b10_41_escalation_events_audited",
            ),
            at_acceptance_references=(
                "AT-038", "AT-039", "AT-040", "AT-041", "AT-042", "AT-055", "AT-058", "AT-061", "AT-063", "AT-066", "AT-067", "AT-068", "AT-069", "AT-070", "test_composed_wave1_acceptance_flow",
            ),
            requirement_references=(
                "BAE-P001-ESC-001", "BAE-P001-ESC-002", "BAE-P001-ESC-003", "BAE-P001-ESC-004", "BAE-P001-ESC-005", "BAE-P001-SELF-006", "BAE-P001-ESC-006", "BAE-P001-ESC-007", "BAE-P001-REL-002", "BAE-P001-TOOL-009", "BAE-P001-DATA-003", "BAE-P001-REL-006", "BAE-P001-REL-007", "BAE-P001-REL-008", "BAE-P001-REL-009", "BAE-P001-REL-010",
            ),
            audit_evidence_references=(
                "bae_audit.audit_events (event_type=ESCALATION_EVENT)",
                "bae_audit.evidence_records (evidence_class=CORROBORATED_SECONDARY_OPERATIONAL)",
            ),
            known_limitations=(
                "Bounded to internal escalation destinations (sys_ops_triage, security_admin_queue, lead_steward_alerts); no outbound customer communication.",
            ),
            unresolved_dependencies=(),
            launch_blockers=(),
            certification_recommendation=CertificationRecommendationState.READY_FOR_CERTIFICATION_REVIEW,
            rationale="B8 Escalation Controller integration proven. Non-authorizing semantics and customer boundary preserved.",
        )

    @classmethod
    def build_all_wave1_packages(cls, registry: BAECapabilityRegistry | None = None) -> dict[str, Wave1CapabilityCertificationPackage]:
        """Assembles all five canonical Wave 1 certification packages."""
        reg = registry or BAECapabilityRegistry.load_seed()
        return {
            "BAE-OPS-OBSERVE-001": cls.build_observe_package(reg),
            "BAE-OPS-DETECT-001": cls.build_detect_package(reg),
            "BAE-OPS-VERIFY-001": cls.build_verify_package(reg),
            "BAE-OPS-PACKAGE-001": cls.build_package_package(reg),
            "BAE-OPS-ESCALATE-001": cls.build_escalate_package(reg),
        }
