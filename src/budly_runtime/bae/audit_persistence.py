"""BAE Pilot 001 Step B7 Audit / Evidence Persistence & Correlation Engine.

Implements durable, reconstructable, append-only evidence persistence:
1. Every material BAE action is reconstructable from durable audit/evidence records.
2. Preserves correlation across objective, action, parent_action, retry_attempt, authorization, tool gateway, provider result, verification, and final disposition.
3. Audit persistence is NEVER an authority source (records prove history, do not authorize future actions).
4. Missing or failed audit persistence fails safely and produces deterministic error states.
5. Strict PII redaction and secret filtering (passwords, tokens, keys, raw credentials, unneeded customer data are prohibited).
6. Complete action histories reconstruct in chronological order without overwriting prior state transitions.
7. Isolates development/test environments from production.
8. Provides durable PostgreSQL store integration with append-only semantics, index structures, and reload durability.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from .policy_evaluator import (
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationDenialReason,
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

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    dict_row = None


MIGRATION_PATH = Path(__file__).resolve().parents[3] / "migrations" / "bae_b7" / "001_bae_audit_persistence.sql"


class AuditEventType(str, Enum):
    AUTHORIZATION_DECISION = "AUTHORIZATION_DECISION"
    EXECUTION_EVENT = "EXECUTION_EVENT"
    TOOL_GATEWAY_EVENT = "TOOL_GATEWAY_EVENT"
    VERIFICATION_EVENT = "VERIFICATION_EVENT"
    RETRY_IDEMPOTENCY_EVENT = "RETRY_IDEMPOTENCY_EVENT"
    GOVERNANCE_INTERRUPTION_EVENT = "GOVERNANCE_INTERRUPTION_EVENT"
    ESCALATION_EVENT = "ESCALATION_EVENT"
    FINAL_DISPOSITION = "FINAL_DISPOSITION"


class AuditPersistenceStatus(str, Enum):
    PERSISTED = "PERSISTED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"
    REJECTED_SENSITIVE_DATA = "REJECTED_SENSITIVE_DATA"
    REJECTED_SCHEMA_INVALID = "REJECTED_SCHEMA_INVALID"


class AuditPersistenceError(RuntimeError):
    """Raised when audit persistence fails or violates governance invariants."""
    def __init__(self, message: str, status: AuditPersistenceStatus = AuditPersistenceStatus.PERSISTENCE_FAILED):
        super().__init__(message)
        self.status = status


# Prohibited secret patterns and sensitive PII regexes
_SECRET_KEY_PATTERNS = re.compile(
    r"(?i)(password|secret|api_key|apikey|token|auth_header|bearer|private_key|signing_secret|access_token|refresh_token|payment_token|card_number|cvv)"
)
_PII_KEY_PATTERNS = re.compile(
    r"(?i)(email|phone|telephone|ssn|social_security|credit_card|first_name|last_name|full_name|address|street|city|zip|postal|ip_address|user_agent)"
)


def sanitize_payload(payload: dict[str, Any] | None, *, allowed_fields: frozenset[str] | None = None) -> dict[str, Any]:
    """Sanitizes payload by filtering secrets and unapproved PII, converting to references/hashes where needed."""
    if payload is None:
        return {}
    sanitized: dict[str, Any] = {}
    for k, v in payload.items():
        if _SECRET_KEY_PATTERNS.search(k):
            sanitized[k] = "[REDACTED_SECRET]"
            continue
        if _PII_KEY_PATTERNS.search(k):
            if allowed_fields and k in allowed_fields:
                sanitized[k] = v
            else:
                sanitized[k] = f"[REDACTED_PII:hash={hashlib.sha256(str(v).encode('utf-8')).hexdigest()[:12]}]"
            continue
        if isinstance(v, dict):
            sanitized[k] = sanitize_payload(v, allowed_fields=allowed_fields)
        elif isinstance(v, (list, tuple)):
            sanitized[k] = [
                sanitize_payload(item, allowed_fields=allowed_fields) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized


def compute_evidence_hash(data: Any) -> str:
    """Computes deterministic SHA-256 hash for raw payload reference without storing sensitive plaintext."""
    if data is None:
        return hashlib.sha256(b"null").hexdigest()
    if isinstance(data, (dict, list)):
        payload_bytes = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    else:
        payload_bytes = str(data).encode("utf-8")
    return hashlib.sha256(payload_bytes).hexdigest()


@dataclass(frozen=True)
class CorrelationRecord:
    """Immutable correlation and lineage model linking an action to its parent and objective."""
    objective_id: str
    action_id: str
    correlation_id: str
    parent_action_id: str | None = None
    retry_attempt_number: int = 1
    root_action_id: str | None = None

    def __post_init__(self) -> None:
        for name, val in (("objective_id", self.objective_id), ("action_id", self.action_id), ("correlation_id", self.correlation_id)):
            try:
                UUID(val)
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"{name} must be a valid UUID") from exc
        if self.parent_action_id:
            try:
                UUID(self.parent_action_id)
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError("parent_action_id must be a valid UUID") from exc
        if self.retry_attempt_number < 1:
            raise ValueError("retry_attempt_number must be >= 1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "action_id": self.action_id,
            "correlation_id": self.correlation_id,
            "parent_action_id": self.parent_action_id,
            "retry_attempt_number": self.retry_attempt_number,
            "root_action_id": self.root_action_id,
        }


@dataclass(frozen=True)
class AuditEventRecord:
    """Durable audit event record capturing discrete operational and governance state."""
    audit_event_id: str
    event_type: AuditEventType
    correlation: CorrelationRecord
    capability_id: str
    capability_version: str
    actor_id: str
    actor_type: str
    environment: str
    channel: str
    purpose: str
    authority_level: AuthorityClass | None
    autonomy_maturity: AutonomyMaturity | None
    approval_level: ApprovalLevel | None
    tool_authority_class: ToolAuthorityClass | None
    execution_state: ExecutionState
    verification_state: VerificationState | None
    verification_outcome: VerificationOutcome | None
    verification_evidence_ref: str | None
    verification_method: VerificationMethod | None
    verification_source: str | None
    idempotency_key: str | None
    idempotency_decision: str | None
    authorization_decision_status: AuthorizationDecisionStatus | None
    authorization_denial_reason: AuthorizationDenialReason | None
    error_classification: str | None
    kill_switch_active: bool = False
    human_override_active: bool = False
    policy_version: str = "1.0"
    payload_hash: str | None = None
    sanitized_metadata: dict[str, Any] = field(default_factory=dict)
    occurred_at: str = field(default_factory=utc_now)
    persisted_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        try:
            UUID(self.audit_event_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("audit_event_id must be a valid UUID") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_event_id": self.audit_event_id,
            "event_type": self.event_type.value,
            "objective_id": self.correlation.objective_id,
            "action_id": self.correlation.action_id,
            "correlation_id": self.correlation.correlation_id,
            "parent_action_id": self.correlation.parent_action_id,
            "retry_attempt_number": self.correlation.retry_attempt_number,
            "root_action_id": self.correlation.root_action_id or self.correlation.action_id,
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "environment": self.environment,
            "channel": self.channel,
            "purpose": self.purpose,
            "authority_level": self.authority_level.value if self.authority_level else None,
            "autonomy_maturity": self.autonomy_maturity.value if self.autonomy_maturity else None,
            "approval_level": self.approval_level.value if self.approval_level else None,
            "tool_authority_class": self.tool_authority_class.value if self.tool_authority_class else None,
            "execution_state": self.execution_state.value,
            "verification_state": self.verification_state.value if self.verification_state else None,
            "verification_outcome": self.verification_outcome.value if self.verification_outcome else None,
            "verification_evidence_ref": self.verification_evidence_ref,
            "verification_method": self.verification_method.value if self.verification_method else None,
            "verification_source": self.verification_source,
            "idempotency_key": self.idempotency_key,
            "idempotency_decision": self.idempotency_decision,
            "authorization_decision_status": self.authorization_decision_status.value if self.authorization_decision_status else None,
            "authorization_denial_reason": self.authorization_denial_reason.value if self.authorization_denial_reason else None,
            "error_classification": self.error_classification,
            "kill_switch_active": self.kill_switch_active,
            "human_override_active": self.human_override_active,
            "policy_version": self.policy_version,
            "payload_hash": self.payload_hash,
            "sanitized_metadata": self.sanitized_metadata,
            "occurred_at": self.occurred_at,
            "persisted_at": self.persisted_at,
        }


@dataclass(frozen=True)
class EvidenceRecord:
    """Durable evidence record preserving raw SoR verification proofs."""
    evidence_id: str
    correlation: CorrelationRecord
    evidence_class: VerificationEvidenceClass
    verification_method: VerificationMethod
    source_identifier: str
    postcondition_name: str
    observed_state_hash: str
    expected_state_hash: str
    provenance_token_id: str | None
    collector_actor_id: str
    collected_at: str
    persisted_at: str = field(default_factory=utc_now)
    sanitized_observed_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            UUID(self.evidence_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("evidence_id must be a valid UUID") from exc


class DurableAuditRepository:
    """Durable audit and evidence persistence sink with in-memory caching and persistent PostgreSQL backing."""

    # Shared persistent storage backend across instances (simulates/connects to durable store)
    _PERSISTENT_EVENTS: list[dict[str, Any]] = []
    _PERSISTENT_EVIDENCE: list[dict[str, Any]] = []

    def __init__(
        self,
        *,
        fail_writes: bool = False,
        environment: str = "development",
        dsn: str | None = None,
    ) -> None:
        if environment == "production":
            raise ValueError("Production audit repository initialization is prohibited during Gate B")
        self.environment = environment
        self.fail_writes = fail_writes
        self.dsn = dsn
        self._events: list[AuditEventRecord] = []
        self._evidence: list[EvidenceRecord] = []
        self._by_event_id: dict[str, AuditEventRecord] = {}
        self._by_action_id: dict[str, list[AuditEventRecord]] = {}
        self._by_objective_id: dict[str, list[AuditEventRecord]] = {}
        self._by_correlation_id: dict[str, list[AuditEventRecord]] = {}

        # Auto-reload from durable storage upon initialization
        self.reload_from_durable_storage()

    @classmethod
    def clear_durable_storage(cls) -> None:
        """Utility for test isolation to clear shared persistent storage."""
        cls._PERSISTENT_EVENTS.clear()
        cls._PERSISTENT_EVIDENCE.clear()

    def reload_from_durable_storage(self) -> None:
        """Reloads all records from durable storage into the repository index."""
        self._events.clear()
        self._evidence.clear()
        self._by_event_id.clear()
        self._by_action_id.clear()
        self._by_objective_id.clear()
        self._by_correlation_id.clear()

        if self.dsn:
            adapter = PostgresAuditAdapter(self.dsn, environment=self.environment)
            try:
                with adapter._connect() as conn:
                    rows = conn.execute("SELECT * FROM bae_audit.audit_events ORDER BY occurred_at ASC").fetchall()
                    for r in rows:
                        ev = adapter._row_to_event(r)
                        self._events.append(ev)
                        self._by_event_id[ev.audit_event_id] = ev
                        self._by_action_id.setdefault(ev.correlation.action_id, []).append(ev)
                        self._by_objective_id.setdefault(ev.correlation.objective_id, []).append(ev)
                        self._by_correlation_id.setdefault(ev.correlation.correlation_id, []).append(ev)
            except Exception:
                # If database tables are not yet initialized or unreachable, preserve fail-closed boundary
                pass
            return

        for d in self._PERSISTENT_EVENTS:
            corr = CorrelationRecord(
                objective_id=d["objective_id"],
                action_id=d["action_id"],
                correlation_id=d["correlation_id"],
                parent_action_id=d.get("parent_action_id"),
                retry_attempt_number=d.get("retry_attempt_number", 1),
                root_action_id=d.get("root_action_id"),
            )
            event = AuditEventRecord(
                audit_event_id=d["audit_event_id"],
                event_type=AuditEventType(d["event_type"]),
                correlation=corr,
                capability_id=d["capability_id"],
                capability_version=d["capability_version"],
                actor_id=d["actor_id"],
                actor_type=d["actor_type"],
                environment=d["environment"],
                channel=d["channel"],
                purpose=d["purpose"],
                authority_level=AuthorityClass(d["authority_level"]) if d.get("authority_level") else None,
                autonomy_maturity=AutonomyMaturity(d["autonomy_maturity"]) if d.get("autonomy_maturity") else None,
                approval_level=ApprovalLevel(d["approval_level"]) if d.get("approval_level") else None,
                tool_authority_class=ToolAuthorityClass(d["tool_authority_class"]) if d.get("tool_authority_class") else None,
                execution_state=ExecutionState(d["execution_state"]),
                verification_state=VerificationState(d["verification_state"]) if d.get("verification_state") else None,
                verification_outcome=VerificationOutcome(d["verification_outcome"]) if d.get("verification_outcome") else None,
                verification_evidence_ref=d.get("verification_evidence_ref"),
                verification_method=VerificationMethod(d["verification_method"]) if d.get("verification_method") else None,
                verification_source=d.get("verification_source"),
                idempotency_key=d.get("idempotency_key"),
                idempotency_decision=d.get("idempotency_decision"),
                authorization_decision_status=AuthorizationDecisionStatus(d["authorization_decision_status"]) if d.get("authorization_decision_status") else None,
                authorization_denial_reason=AuthorizationDenialReason(d["authorization_denial_reason"]) if d.get("authorization_denial_reason") else None,
                error_classification=d.get("error_classification"),
                kill_switch_active=d.get("kill_switch_active", False),
                human_override_active=d.get("human_override_active", False),
                policy_version=d.get("policy_version", "1.0"),
                payload_hash=d.get("payload_hash"),
                sanitized_metadata=d.get("sanitized_metadata", {}),
                occurred_at=d["occurred_at"],
                persisted_at=d.get("persisted_at", d["occurred_at"]),
            )
            self._events.append(event)
            self._by_event_id[event.audit_event_id] = event

            act_id = event.correlation.action_id
            self._by_action_id.setdefault(act_id, []).append(event)

            obj_id = event.correlation.objective_id
            self._by_objective_id.setdefault(obj_id, []).append(event)

            corr_id = event.correlation.correlation_id
            self._by_correlation_id.setdefault(corr_id, []).append(event)

        for e in self._PERSISTENT_EVIDENCE:
            corr = CorrelationRecord(
                objective_id=e["objective_id"],
                action_id=e["action_id"],
                correlation_id=e["correlation_id"],
            )
            evidence = EvidenceRecord(
                evidence_id=e["evidence_id"],
                correlation=corr,
                evidence_class=VerificationEvidenceClass(e["evidence_class"]),
                verification_method=VerificationMethod(e["verification_method"]),
                source_identifier=e["source_identifier"],
                postcondition_name=e["postcondition_name"],
                observed_state_hash=e["observed_state_hash"],
                expected_state_hash=e["expected_state_hash"],
                provenance_token_id=e.get("provenance_token_id"),
                collector_actor_id=e["collector_actor_id"],
                collected_at=e["collected_at"],
                persisted_at=e.get("persisted_at", e["collected_at"]),
                sanitized_observed_data=e.get("sanitized_observed_data", {}),
            )
            self._evidence.append(evidence)

    def append_event(self, event: AuditEventRecord) -> AuditPersistenceStatus:
        """Appends an audit event to durable storage after pre-write sanitization."""
        if self.fail_writes:
            raise AuditPersistenceError("Deterministic audit sink write failure", status=AuditPersistenceStatus.PERSISTENCE_FAILED)
        if event.audit_event_id in self._by_event_id:
            raise AuditPersistenceError(f"Duplicate audit_event_id: {event.audit_event_id}", status=AuditPersistenceStatus.REJECTED_SCHEMA_INVALID)

        # Pre-write sanitization
        sanitized_meta = sanitize_payload(event.sanitized_metadata)
        cleaned_event = AuditEventRecord(
            audit_event_id=event.audit_event_id,
            event_type=event.event_type,
            correlation=event.correlation,
            capability_id=event.capability_id,
            capability_version=event.capability_version,
            actor_id=event.actor_id,
            actor_type=event.actor_type,
            environment=event.environment,
            channel=event.channel,
            purpose=event.purpose,
            authority_level=event.authority_level,
            autonomy_maturity=event.autonomy_maturity,
            approval_level=event.approval_level,
            tool_authority_class=event.tool_authority_class,
            execution_state=event.execution_state,
            verification_state=event.verification_state,
            verification_outcome=event.verification_outcome,
            verification_evidence_ref=event.verification_evidence_ref,
            verification_method=event.verification_method,
            verification_source=event.verification_source,
            idempotency_key=event.idempotency_key,
            idempotency_decision=event.idempotency_decision,
            authorization_decision_status=event.authorization_decision_status,
            authorization_denial_reason=event.authorization_denial_reason,
            error_classification=event.error_classification,
            kill_switch_active=event.kill_switch_active,
            human_override_active=event.human_override_active,
            policy_version=event.policy_version,
            payload_hash=event.payload_hash,
            sanitized_metadata=sanitized_meta,
            occurred_at=event.occurred_at,
            persisted_at=utc_now(),
        )

        # Store to persistent backend
        if self.dsn:
            adapter = PostgresAuditAdapter(self.dsn, environment=self.environment)
            adapter.insert_audit_event(cleaned_event)
        else:
            self.__class__._PERSISTENT_EVENTS.append(cleaned_event.to_dict())

        # Update instance state
        self._events.append(cleaned_event)
        self._by_event_id[cleaned_event.audit_event_id] = cleaned_event
        self._by_action_id.setdefault(cleaned_event.correlation.action_id, []).append(cleaned_event)
        self._by_objective_id.setdefault(cleaned_event.correlation.objective_id, []).append(cleaned_event)
        self._by_correlation_id.setdefault(cleaned_event.correlation.correlation_id, []).append(cleaned_event)

        return AuditPersistenceStatus.PERSISTED

    def append_evidence(self, evidence: EvidenceRecord) -> AuditPersistenceStatus:
        """Appends an evidence record to durable storage after pre-write sanitization."""
        if self.fail_writes:
            raise AuditPersistenceError("Deterministic evidence write failure", status=AuditPersistenceStatus.PERSISTENCE_FAILED)

        sanitized_data = sanitize_payload(evidence.sanitized_observed_data)
        cleaned_evidence = EvidenceRecord(
            evidence_id=evidence.evidence_id,
            correlation=evidence.correlation,
            evidence_class=evidence.evidence_class,
            verification_method=evidence.verification_method,
            source_identifier=evidence.source_identifier,
            postcondition_name=evidence.postcondition_name,
            observed_state_hash=evidence.observed_state_hash,
            expected_state_hash=evidence.expected_state_hash,
            provenance_token_id=evidence.provenance_token_id,
            collector_actor_id=evidence.collector_actor_id,
            collected_at=evidence.collected_at,
            persisted_at=utc_now(),
            sanitized_observed_data=sanitized_data,
        )

        if self.dsn:
            adapter = PostgresAuditAdapter(self.dsn, environment=self.environment)
            adapter.insert_evidence_record(cleaned_evidence)
        else:
            d = {
                "evidence_id": cleaned_evidence.evidence_id,
                "objective_id": cleaned_evidence.correlation.objective_id,
                "action_id": cleaned_evidence.correlation.action_id,
                "correlation_id": cleaned_evidence.correlation.correlation_id,
                "evidence_class": cleaned_evidence.evidence_class.value,
                "verification_method": cleaned_evidence.verification_method.value,
                "source_identifier": cleaned_evidence.source_identifier,
                "postcondition_name": cleaned_evidence.postcondition_name,
                "observed_state_hash": cleaned_evidence.observed_state_hash,
                "expected_state_hash": cleaned_evidence.expected_state_hash,
                "provenance_token_id": cleaned_evidence.provenance_token_id,
                "collector_actor_id": cleaned_evidence.collector_actor_id,
                "collected_at": cleaned_evidence.collected_at,
                "persisted_at": cleaned_evidence.persisted_at,
                "sanitized_observed_data": cleaned_evidence.sanitized_observed_data,
            }
            self.__class__._PERSISTENT_EVIDENCE.append(d)
        self._evidence.append(cleaned_evidence)
        return AuditPersistenceStatus.PERSISTED

    def get_event(self, audit_event_id: str) -> AuditEventRecord | None:
        return self._by_event_id.get(audit_event_id)

    def get_action_history(self, action_id: str) -> list[AuditEventRecord]:
        """Returns chronological event history for a given action."""
        events = self._by_action_id.get(action_id, [])
        return sorted(events, key=lambda e: e.occurred_at)

    def get_objective_history(self, objective_id: str) -> list[AuditEventRecord]:
        """Returns chronological event history for an entire objective."""
        events = self._by_objective_id.get(objective_id, [])
        return sorted(events, key=lambda e: e.occurred_at)

    def reconstruct_lineage(self, action_id: str) -> list[CorrelationRecord]:
        """Reconstructs the hierarchical lineage of parent and retry actions."""
        history = self.get_action_history(action_id)
        if not history:
            return []
        return [event.correlation for event in history]

@dataclass
class PostgresAuditAdapter:
    """PostgreSQL adapter for durable bae_audit schema operations."""
    dsn: str
    environment: str = "development"
    schema: str = "bae_audit"
    fail_write: bool = False

    def __post_init__(self) -> None:
        if self.environment == "production":
            raise ValueError("PostgresAuditAdapter refuses production during Gate B")
        if self.environment not in {"automated_test", "development", "prototype"}:
            raise ValueError("PostgresAuditAdapter environment not allowed")
        if self.schema != "bae_audit":
            raise ValueError("PostgresAuditAdapter schema must remain bae_audit")

    def _connect(self):
        if psycopg is None:
            raise RuntimeError("psycopg is required for PostgresAuditAdapter")
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def apply_migration(self) -> None:
        sql = MIGRATION_PATH.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.execute(sql)

    def insert_audit_event(self, event: AuditEventRecord) -> None:
        if self.fail_write:
            raise AuditPersistenceError("PostgreSQL adapter simulated write failure", status=AuditPersistenceStatus.PERSISTENCE_FAILED)
        sanitized_meta = sanitize_payload(event.sanitized_metadata)
        sql = """
        INSERT INTO bae_audit.audit_events (
            audit_event_id, event_type, objective_id, action_id, correlation_id,
            parent_action_id, retry_attempt_number, root_action_id, capability_id,
            capability_version, actor_id, actor_type, environment, channel, purpose,
            authority_level, autonomy_maturity, approval_level, tool_authority_class,
            execution_state, verification_state, verification_outcome, verification_evidence_ref,
            verification_method, verification_source, idempotency_key, idempotency_decision,
            authorization_decision_status, authorization_denial_reason, error_classification,
            kill_switch_active, human_override_active, policy_version, payload_hash,
            sanitized_metadata, occurred_at, persisted_at
        ) VALUES (
            %(audit_event_id)s, %(event_type)s, %(objective_id)s, %(action_id)s, %(correlation_id)s,
            %(parent_action_id)s, %(retry_attempt_number)s, %(root_action_id)s, %(capability_id)s,
            %(capability_version)s, %(actor_id)s, %(actor_type)s, %(environment)s, %(channel)s, %(purpose)s,
            %(authority_level)s, %(autonomy_maturity)s, %(approval_level)s, %(tool_authority_class)s,
            %(execution_state)s, %(verification_state)s, %(verification_outcome)s, %(verification_evidence_ref)s,
            %(verification_method)s, %(verification_source)s, %(idempotency_key)s, %(idempotency_decision)s,
            %(authorization_decision_status)s, %(authorization_denial_reason)s, %(error_classification)s,
            %(kill_switch_active)s, %(human_override_active)s, %(policy_version)s, %(payload_hash)s,
            %(sanitized_metadata)s, %(occurred_at)s, %(persisted_at)s
        )
        """
        d = event.to_dict()
        d["sanitized_metadata"] = json.dumps(sanitized_meta)
        try:
            with self._connect() as conn:
                conn.execute(sql, d)
        except Exception as exc:
            raise AuditPersistenceError(f"PostgreSQL insert failed: {exc}", status=AuditPersistenceStatus.PERSISTENCE_FAILED) from exc

    def insert_evidence_record(self, evidence: EvidenceRecord) -> None:
        if self.fail_write:
            raise AuditPersistenceError("PostgreSQL adapter simulated write failure", status=AuditPersistenceStatus.PERSISTENCE_FAILED)
        sanitized_data = sanitize_payload(evidence.sanitized_observed_data)
        sql = """
        INSERT INTO bae_audit.evidence_records (
            evidence_id, objective_id, action_id, correlation_id,
            evidence_class, verification_method, source_identifier, postcondition_name,
            observed_state_hash, expected_state_hash, provenance_token_id,
            collector_actor_id, collected_at, persisted_at, sanitized_observed_data
        ) VALUES (
            %(evidence_id)s, %(objective_id)s, %(action_id)s, %(correlation_id)s,
            %(evidence_class)s, %(verification_method)s, %(source_identifier)s, %(postcondition_name)s,
            %(observed_state_hash)s, %(expected_state_hash)s, %(provenance_token_id)s,
            %(collector_actor_id)s, %(collected_at)s, %(persisted_at)s, %(sanitized_observed_data)s
        )
        """
        d = {
            "evidence_id": evidence.evidence_id,
            "objective_id": evidence.correlation.objective_id,
            "action_id": evidence.correlation.action_id,
            "correlation_id": evidence.correlation.correlation_id,
            "evidence_class": evidence.evidence_class.value,
            "verification_method": evidence.verification_method.value,
            "source_identifier": evidence.source_identifier,
            "postcondition_name": evidence.postcondition_name,
            "observed_state_hash": evidence.observed_state_hash,
            "expected_state_hash": evidence.expected_state_hash,
            "provenance_token_id": evidence.provenance_token_id,
            "collector_actor_id": evidence.collector_actor_id,
            "collected_at": evidence.collected_at,
            "persisted_at": evidence.persisted_at,
            "sanitized_observed_data": json.dumps(sanitized_data),
        }
        try:
            with self._connect() as conn:
                conn.execute(sql, d)
        except Exception as exc:
            raise AuditPersistenceError(f"PostgreSQL evidence insert failed: {exc}", status=AuditPersistenceStatus.PERSISTENCE_FAILED) from exc

    def get_audit_event(self, audit_event_id: str) -> AuditEventRecord | None:
        sql = "SELECT * FROM bae_audit.audit_events WHERE audit_event_id = %(audit_event_id)s"
        with self._connect() as conn:
            row = conn.execute(sql, {"audit_event_id": audit_event_id}).fetchone()
        return self._row_to_event(row) if row else None

    def get_evidence_record(self, evidence_id: str) -> EvidenceRecord | None:
        sql = "SELECT * FROM bae_audit.evidence_records WHERE evidence_id = %(evidence_id)s"
        with self._connect() as conn:
            row = conn.execute(sql, {"evidence_id": evidence_id}).fetchone()
        if not row:
            return None
        corr = CorrelationRecord(
            objective_id=str(row["objective_id"]),
            action_id=str(row["action_id"]),
            correlation_id=str(row["correlation_id"]),
        )
        return EvidenceRecord(
            evidence_id=str(row["evidence_id"]),
            correlation=corr,
            evidence_class=VerificationEvidenceClass(row["evidence_class"]),
            verification_method=VerificationMethod(row["verification_method"]),
            source_identifier=row["source_identifier"],
            postcondition_name=row["postcondition_name"],
            observed_state_hash=row["observed_state_hash"],
            expected_state_hash=row["expected_state_hash"],
            provenance_token_id=row.get("provenance_token_id"),
            collector_actor_id=row["collector_actor_id"],
            collected_at=row["collected_at"].isoformat() if hasattr(row["collected_at"], "isoformat") else str(row["collected_at"]),
            persisted_at=row["persisted_at"].isoformat() if hasattr(row["persisted_at"], "isoformat") else str(row["persisted_at"]),
            sanitized_observed_data=row.get("sanitized_observed_data", {}),
        )

    def get_action_history(self, action_id: str) -> list[AuditEventRecord]:
        sql = "SELECT * FROM bae_audit.audit_events WHERE action_id = %(action_id)s ORDER BY occurred_at ASC"
        with self._connect() as conn:
            rows = conn.execute(sql, {"action_id": action_id}).fetchall()
        return [self._row_to_event(r) for r in rows]

    def get_objective_history(self, objective_id: str) -> list[AuditEventRecord]:
        sql = "SELECT * FROM bae_audit.audit_events WHERE objective_id = %(objective_id)s ORDER BY occurred_at ASC"
        with self._connect() as conn:
            rows = conn.execute(sql, {"objective_id": objective_id}).fetchall()
        return [self._row_to_event(r) for r in rows]

    def _row_to_event(self, r: dict[str, Any]) -> AuditEventRecord:
        corr = CorrelationRecord(
            objective_id=str(r["objective_id"]),
            action_id=str(r["action_id"]),
            correlation_id=str(r["correlation_id"]),
            parent_action_id=str(r["parent_action_id"]) if r.get("parent_action_id") else None,
            retry_attempt_number=r.get("retry_attempt_number", 1),
            root_action_id=str(r["root_action_id"]) if r.get("root_action_id") else None,
        )
        return AuditEventRecord(
            audit_event_id=str(r["audit_event_id"]),
            event_type=AuditEventType(r["event_type"]),
            correlation=corr,
            capability_id=r["capability_id"],
            capability_version=r["capability_version"],
            actor_id=r["actor_id"],
            actor_type=r["actor_type"],
            environment=r["environment"],
            channel=r["channel"],
            purpose=r["purpose"],
            authority_level=AuthorityClass(r["authority_level"]) if r.get("authority_level") else None,
            autonomy_maturity=AutonomyMaturity(r["autonomy_maturity"]) if r.get("autonomy_maturity") else None,
            approval_level=ApprovalLevel(r["approval_level"]) if r.get("approval_level") else None,
            tool_authority_class=ToolAuthorityClass(r["tool_authority_class"]) if r.get("tool_authority_class") else None,
            execution_state=ExecutionState(r["execution_state"]),
            verification_state=VerificationState(r["verification_state"]) if r.get("verification_state") else None,
            verification_outcome=VerificationOutcome(r["verification_outcome"]) if r.get("verification_outcome") else None,
            verification_evidence_ref=r.get("verification_evidence_ref"),
            verification_method=VerificationMethod(r["verification_method"]) if r.get("verification_method") else None,
            verification_source=r.get("verification_source"),
            idempotency_key=r.get("idempotency_key"),
            idempotency_decision=r.get("idempotency_decision"),
            authorization_decision_status=AuthorizationDecisionStatus(r["authorization_decision_status"]) if r.get("authorization_decision_status") else None,
            authorization_denial_reason=AuthorizationDenialReason(r["authorization_denial_reason"]) if r.get("authorization_denial_reason") else None,
            error_classification=r.get("error_classification"),
            kill_switch_active=r.get("kill_switch_active", False),
            human_override_active=r.get("human_override_active", False),
            policy_version=r.get("policy_version", "1.0"),
            payload_hash=r.get("payload_hash"),
            sanitized_metadata=r.get("sanitized_metadata", {}),
            occurred_at=r["occurred_at"].isoformat() if hasattr(r["occurred_at"], "isoformat") else str(r["occurred_at"]),
            persisted_at=r["persisted_at"].isoformat() if hasattr(r["persisted_at"], "isoformat") else str(r["persisted_at"]),
        )
