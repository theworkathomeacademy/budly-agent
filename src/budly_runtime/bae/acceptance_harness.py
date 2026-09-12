"""BAE Pilot 001 Step B11 Acceptance Harness.

Defines the canonical AT-001 through AT-070 acceptance harness framework,
result tracking, evidence recording, and requirement traceability mapping:
- AT-001–AT-010: AUTHORITY (BAE-P001-AUTH, BAE-P001-MAT)
- AT-011–AT-015: CONTINUOUS AUTHORIZATION (BAE-P001-PERM, BAE-P001-AUTH)
- AT-016–AT-020: TOOL GATEWAY (BAE-P001-TOOL)
- AT-021–AT-026: EXECUTION STATE / VERIFICATION (BAE-P001-STATE, BAE-P001-VER)
- AT-027–AT-032: RETRY / IDEMPOTENCY (BAE-P001-RET)
- AT-033–AT-037: AUDIT / EVIDENCE (BAE-P001-AUD, BAE-P001-DATA)
- AT-038–AT-042: ESCALATION (BAE-P001-ESC)
- AT-043–AT-049: KILL SWITCH / HUMAN OVERRIDE (BAE-P001-KILL)
- AT-050–AT-055: SELF-EXPANSION PREVENTION (BAE-P001-SELF)
- AT-056–AT-059: SAFE STOP / SAFE INACTION (BAE-P001-STATE, BAE-P001-ESC)
- AT-060–AT-065: CUSTOMER / COMMERCIAL BOUNDARIES (BAE-P001-REL, BAE-P001-DATA)
- AT-066–AT-070: RELEASE / ENVIRONMENT / GATE CONTROL (BAE-P001-REL, BAE-P001-AUTH)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AcceptanceResultStatus(str, Enum):
    """Explicit deterministic result states for acceptance tests."""
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class AcceptanceCategory(str, Enum):
    """Canonical categories for AT-001 through AT-070."""
    AUTHORITY = "AUTHORITY"                                # AT-001 - AT-010
    CONTINUOUS_AUTHORIZATION = "CONTINUOUS_AUTHORIZATION"  # AT-011 - AT-015
    TOOL_GATEWAY = "TOOL_GATEWAY"                          # AT-016 - AT-020
    EXECUTION_STATE_VERIFICATION = "EXECUTION_STATE_VERIFICATION"  # AT-021 - AT-026
    RETRY_IDEMPOTENCY = "RETRY_IDEMPOTENCY"                # AT-027 - AT-032
    AUDIT_EVIDENCE = "AUDIT_EVIDENCE"                      # AT-033 - AT-037
    ESCALATION = "ESCALATION"                              # AT-038 - AT-042
    KILL_SWITCH_OVERRIDE = "KILL_SWITCH_OVERRIDE"          # AT-043 - AT-049
    SELF_EXPANSION_PREVENTION = "SELF_EXPANSION_PREVENTION"  # AT-050 - AT-055
    SAFE_STOP_INACTION = "SAFE_STOP_INACTION"              # AT-056 - AT-059
    CUSTOMER_COMMERCIAL_BOUNDARIES = "CUSTOMER_COMMERCIAL_BOUNDARIES"  # AT-060 - AT-065
    RELEASE_ENVIRONMENT_GATE = "RELEASE_ENVIRONMENT_GATE"  # AT-066 - AT-070


@dataclass(frozen=True)
class AcceptanceTestRecord:
    """Complete evidence record for an individual AT acceptance test."""
    test_id: str
    requirement_references: tuple[str, ...]
    category: AcceptanceCategory
    capabilities_involved: tuple[str, ...]
    environment: str
    preconditions: str
    fixture_input: dict[str, Any]
    expected_result: str
    actual_result: str
    status: AcceptanceResultStatus
    observed_authorization_decision: str | None = None
    observed_execution_state: str | None = None
    observed_verification_state: str | None = None
    evidence_reference: str | None = None
    defect_reference: str | None = None
    executed_at: str = field(default_factory=utc_now)
    executor: str = "Antigravity"
    # Additional governed trace attributes
    objective_id: str | None = None
    action_id: str | None = None
    correlation_id: str | None = None
    capability_version: str | None = None
    authority_class: str | None = None
    current_maturity: str | None = None
    max_maturity: str | None = None
    approval_level: str | None = None
    tool_authority: str | None = None
    provider_invocation_count: int = 0
    audit_event_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_record_ids: tuple[str, ...] = field(default_factory=tuple)
    kill_switch_state: str | None = None
    retry_idempotency_key: str | None = None
    escalation_reference: str | None = None
    sanitized_payload_evidence: dict[str, Any] = field(default_factory=dict)
    database_evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "requirement_references": list(self.requirement_references),
            "category": self.category.value,
            "capabilities_involved": list(self.capabilities_involved),
            "environment": self.environment,
            "preconditions": self.preconditions,
            "fixture_input": self.fixture_input,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "status": self.status.value,
            "observed_authorization_decision": self.observed_authorization_decision,
            "observed_execution_state": self.observed_execution_state,
            "observed_verification_state": self.observed_verification_state,
            "evidence_reference": self.evidence_reference,
            "defect_reference": self.defect_reference,
            "executed_at": self.executed_at,
            "executor": self.executor,
            "objective_id": self.objective_id,
            "action_id": self.action_id,
            "correlation_id": self.correlation_id,
            "capability_version": self.capability_version,
            "authority_class": self.authority_class,
            "current_maturity": self.current_maturity,
            "max_maturity": self.max_maturity,
            "approval_level": self.approval_level,
            "tool_authority": self.tool_authority,
            "provider_invocation_count": self.provider_invocation_count,
            "audit_event_ids": list(self.audit_event_ids),
            "evidence_record_ids": list(self.evidence_record_ids),
            "kill_switch_state": self.kill_switch_state,
            "retry_idempotency_key": self.retry_idempotency_key,
            "escalation_reference": self.escalation_reference,
            "sanitized_payload_evidence": self.sanitized_payload_evidence,
            "database_evidence": self.database_evidence,
        }


@dataclass
class AcceptanceHarnessSummary:
    """Summary of complete AT-001 through AT-070 acceptance execution."""
    total_tests: int = 70
    passed_count: int = 0
    failed_count: int = 0
    blocked_count: int = 0
    records: dict[str, AcceptanceTestRecord] = field(default_factory=dict)

    def record_test(self, record: AcceptanceTestRecord) -> None:
        self.records[record.test_id] = record
        if record.status == AcceptanceResultStatus.PASS:
            self.passed_count += 1
        elif record.status == AcceptanceResultStatus.FAIL:
            self.failed_count += 1
        elif record.status == AcceptanceResultStatus.BLOCKED:
            self.blocked_count += 1

    @property
    def is_acceptance_passed(self) -> bool:
        return self.passed_count == self.total_tests and self.failed_count == 0 and self.blocked_count == 0
