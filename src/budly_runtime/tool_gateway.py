"""TG-P01 canonical BROS Tool Gateway vertical slice (local, non-production)."""

from __future__ import annotations

import re
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol
from uuid import UUID, uuid4

from .preference_registry import PREFERENCE_REGISTRY
from .relationship_registry import MINOR_PROHIBITED_FIELDS, RELATIONSHIP_FACT_REGISTRY

ALLOWED_ACTIVITY_TYPES = frozenset({
    "conversation_started", "conversation_completed", "education_provided", "recommendation_presented",
    "customer_response_recorded", "human_escalation_requested", "support_interaction", "approved_journey_interaction",
})
PROTECTED_ACTIVITY_TYPES = frozenset({
    "purchase_completed", "payment_received", "subscription_started", "membership_activated", "consent_granted",
    "consent_withdrawn", "lifecycle_stage_changed", "affiliate_approved", "price_changed", "product_changed",
    "policy_changed", "customer_merged",
})
PROHIBITED_ACTIVITY_PROPERTIES = frozenset({
    "activity_id", "customer_email", "email", "phone", "address", "raw_transcript", "payment_data",
    "consent", "consent_status", "lifecycle_stage", "purchase_status", "membership_status", "subscription_status",
})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RequestValidationError(ValueError):
    pass


class ResultStatus(str, Enum):
    SUCCESS = "SUCCESS"
    DENIED = "DENIED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class ErrorClass(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    UNKNOWN_ACTOR = "UNKNOWN_ACTOR"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    CAPABILITY_DISABLED = "CAPABILITY_DISABLED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    ENVIRONMENT_DENIED = "ENVIRONMENT_DENIED"
    CHANNEL_DENIED = "CHANNEL_DENIED"
    PURPOSE_DENIED = "PURPOSE_DENIED"
    DATA_SCOPE_DENIED = "DATA_SCOPE_DENIED"
    INPUT_VALIDATION_FAILED = "INPUT_VALIDATION_FAILED"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    ADAPTER_FAILURE = "ADAPTER_FAILURE"
    OUTPUT_VALIDATION_FAILED = "OUTPUT_VALIDATION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    ACTIVITY_TYPE_NOT_AUTHORIZED = "ACTIVITY_TYPE_NOT_AUTHORIZED"
    FACT_CLASSIFICATION_INVALID = "FACT_CLASSIFICATION_INVALID"
    IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    WRITE_FAILED = "WRITE_FAILED"
    POSTCONDITION_FAILED = "POSTCONDITION_FAILED"
    AUDIT_FAILURE = "AUDIT_FAILURE"
    PREFERENCE_KEY_NOT_AUTHORIZED = "PREFERENCE_KEY_NOT_AUTHORIZED"
    PREFERENCE_VALUE_INVALID = "PREFERENCE_VALUE_INVALID"
    MEMORY_PERMISSION_REQUIRED = "MEMORY_PERMISSION_REQUIRED"
    MEMORY_PERMISSION_WITHDRAWN = "MEMORY_PERMISSION_WITHDRAWN"
    SUBJECT_SCOPE_DENIED = "SUBJECT_SCOPE_DENIED"
    RELATIONSHIP_FACT_KEY_NOT_AUTHORIZED = "RELATIONSHIP_FACT_KEY_NOT_AUTHORIZED"
    RELATIONSHIP_FACT_VALUE_INVALID = "RELATIONSHIP_FACT_VALUE_INVALID"
    RELATIONSHIP_FACT_SENSITIVITY_DENIED = "RELATIONSHIP_FACT_SENSITIVITY_DENIED"
    AMBIGUOUS_RELATIONSHIP_FACT = "AMBIGUOUS_RELATIONSHIP_FACT"
    MINOR_DATA_PROHIBITED = "MINOR_DATA_PROHIBITED"
    SOURCE_CONTEXT_INVALID = "SOURCE_CONTEXT_INVALID"
    IDENTITY_VERIFICATION_REQUIRED = "IDENTITY_VERIFICATION_REQUIRED"
    MEMORY_USE_PERMISSION_REQUIRED = "MEMORY_USE_PERMISSION_REQUIRED"
    BAE_AUTHORIZATION_REQUIRED = "BAE_AUTHORIZATION_REQUIRED"
    BAE_AUTHORIZATION_DENIED = "BAE_AUTHORIZATION_DENIED"
    BAE_STEP_TOKEN_INVALID = "BAE_STEP_TOKEN_INVALID"


class ToolHealth(str, Enum):
    HEALTHY = "HEALTHY"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class Actor:
    actor_id: str
    actor_type: str


@dataclass(frozen=True)
class CapabilityRef:
    capability_id: str
    capability_version: str


@dataclass(frozen=True)
class KnowledgeRetrieveInput:
    query: str
    domain: str
    max_results: int = 5

    def __post_init__(self) -> None:
        if not isinstance(self.query, str) or not self.query.strip() or len(self.query) > 1000:
            raise RequestValidationError("query is required and must be <= 1000 characters")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", self.domain or ""):
            raise RequestValidationError("domain is invalid")
        if type(self.max_results) is not int or not 1 <= self.max_results <= 10:
            raise RequestValidationError("max_results must be 1..10")


@dataclass(frozen=True)
class OperationalMetricsRetrieveInput:
    domain: str
    metric_names: tuple[str, ...]
    time_window: str = "current_snapshot"
    max_results: int = 10

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", self.domain or ""):
            raise RequestValidationError("domain is invalid")
        if not isinstance(self.metric_names, tuple) or not self.metric_names or len(self.metric_names) > 20:
            raise RequestValidationError("metric_names must contain 1..20 names")
        if any(not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_.]{2,127}", name) for name in self.metric_names):
            raise RequestValidationError("metric name is invalid")
        if self.time_window not in {"current_snapshot", "last_24h", "last_7d"}:
            raise RequestValidationError("time_window is invalid")
        if type(self.max_results) is not int or not 1 <= self.max_results <= 20:
            raise RequestValidationError("max_results must be 1..20")


@dataclass(frozen=True)
class SubjectRef:
    subject_type: str
    subject_id: str

    def __post_init__(self) -> None:
        if self.subject_type not in {"synthetic_person", "synthetic_conversation", "synthetic_recommendation"}:
            raise RequestValidationError("subject type is invalid")
        if not re.fullmatch(r"[PCR]-TEST-[0-9]{3}", self.subject_id or ""):
            raise RequestValidationError("subject id is invalid")


@dataclass(frozen=True)
class SourceRef:
    source_type: str
    source_id: str

    def __post_init__(self) -> None:
        if self.source_type not in {"budly_service", "administrator", "system_service", "test_harness"}:
            raise RequestValidationError("source type is invalid")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{2,63}", self.source_id or ""):
            raise RequestValidationError("source id is invalid")


@dataclass(frozen=True)
class ActivityRecordInput:
    activity_type: str
    subject: SubjectRef
    source: SourceRef
    occurred_at: str
    idempotency_key: str
    properties: dict[str, Any]
    fact_classification: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", self.activity_type or ""):
            raise RequestValidationError("activity type is invalid")
        try:
            observed = datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise RequestValidationError("occurred_at must be an ISO timestamp") from exc
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise RequestValidationError("occurred_at must include a timezone")
        if not isinstance(self.idempotency_key, str) or len(self.idempotency_key) > 128:
            raise RequestValidationError("idempotency key is invalid")
        if not isinstance(self.properties, dict) or len(self.properties) > 10:
            raise RequestValidationError("properties must be a bounded object")
        for key, value in self.properties.items():
            if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", key):
                raise RequestValidationError("property key is invalid")
            if isinstance(value, (dict, list, tuple, set)) or not isinstance(value, (str, int, float, bool, type(None))):
                raise RequestValidationError("property value is invalid")
            if isinstance(value, str) and len(value) > 256:
                raise RequestValidationError("property value is too long")


@dataclass(frozen=True)
class PreferenceValue:
    key: str
    value: str
    information_type: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", self.key or ""):
            raise RequestValidationError("preference key is invalid")
        if not isinstance(self.value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", self.value):
            raise RequestValidationError("preference value is invalid")
        if not re.fullmatch(r"[A-Z][A-Z_]{2,31}", self.information_type or ""):
            raise RequestValidationError("information type is invalid")


@dataclass(frozen=True)
class PreferenceSource:
    source_type: str
    source_reference: str
    statement_reference: str

    def __post_init__(self) -> None:
        if self.source_type not in {"conversation", "behavior", "recommendation", "model"}:
            raise RequestValidationError("preference source type is invalid")
        if not re.fullmatch(r"C-TEST-[0-9]{3}", self.source_reference or ""):
            raise RequestValidationError("source reference is invalid")
        if not re.fullmatch(r"S-TEST-[0-9]{3}", self.statement_reference or ""):
            raise RequestValidationError("statement reference is invalid")


@dataclass(frozen=True)
class MemoryAuthorization:
    state: str
    purpose: str

    def __post_init__(self) -> None:
        if self.state not in {"ACTIVE", "NOT_GRANTED", "WITHDRAWN"}:
            raise RequestValidationError("memory authorization state is invalid")
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", self.purpose or ""):
            raise RequestValidationError("memory authorization purpose is invalid")


@dataclass(frozen=True)
class CustomerPreferenceRecordInput:
    subject: SubjectRef
    preference: PreferenceValue
    source: PreferenceSource
    memory_authorization: MemoryAuthorization
    marketing_consent: bool
    stated_at: str
    idempotency_key: str

    def __post_init__(self) -> None:
        try:
            observed = datetime.fromisoformat(self.stated_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise RequestValidationError("stated_at must be an ISO timestamp") from exc
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise RequestValidationError("stated_at must include a timezone")
        if type(self.marketing_consent) is not bool:
            raise RequestValidationError("marketing consent context must be boolean")
        if not isinstance(self.idempotency_key, str) or not self.idempotency_key.strip() or len(self.idempotency_key) > 160:
            raise RequestValidationError("idempotency key is invalid")


@dataclass(frozen=True)
class RelationshipFactValue:
    fact_key: str
    fact_value: dict[str, Any]
    information_type: str
    certainty: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", self.fact_key or ""):
            raise RequestValidationError("relationship fact key is invalid")
        if not isinstance(self.fact_value, dict) or len(self.fact_value) > 12:
            raise RequestValidationError("relationship fact value must be a bounded object")
        for key, value in self.fact_value.items():
            if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", key):
                raise RequestValidationError("relationship fact field is invalid")
            if isinstance(value, (dict, list, tuple, set)) or not isinstance(value, (str, int, bool)):
                raise RequestValidationError("relationship fact field value is invalid")
            if isinstance(value, str) and len(value) > 120:
                raise RequestValidationError("relationship fact field value is too long")
        if not re.fullmatch(r"[A-Z][A-Z_]{2,47}", self.information_type or ""):
            raise RequestValidationError("relationship information type is invalid")
        if self.certainty not in {"EXPLICIT", "CONFIRMED", "AMBIGUOUS"}:
            raise RequestValidationError("relationship fact certainty is invalid")


@dataclass(frozen=True)
class RelationshipSource:
    source_type: str
    source_reference: str
    statement_reference: str
    source_context_summary: str

    def __post_init__(self) -> None:
        if self.source_type not in {"conversation", "behavior", "purchase", "external", "model"}:
            raise RequestValidationError("relationship source type is invalid")
        if not re.fullmatch(r"C-TEST-[0-9]{3}", self.source_reference or ""):
            raise RequestValidationError("source reference is invalid")
        if not re.fullmatch(r"S-TEST-[0-9]{3}", self.statement_reference or ""):
            raise RequestValidationError("statement reference is invalid")
        if not isinstance(self.source_context_summary, str) or not 10 <= len(self.source_context_summary) <= 240:
            raise RequestValidationError("source context summary must be bounded")
        if self.source_context_summary not in RELATIONSHIP_FACT_REGISTRY.allowed_source_context_summaries:
            raise RequestValidationError("source context summary is not an approved minimized context")


@dataclass(frozen=True)
class CustomerRelationshipFactRecordInput:
    subject: SubjectRef
    relationship_fact: RelationshipFactValue
    source: RelationshipSource
    memory_authorization: MemoryAuthorization
    stated_at: str
    idempotency_key: str

    def __post_init__(self) -> None:
        try:
            observed = datetime.fromisoformat(self.stated_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise RequestValidationError("stated_at must be an ISO timestamp") from exc
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise RequestValidationError("stated_at must include a timezone")
        if not isinstance(self.idempotency_key, str) or not self.idempotency_key.strip() or len(self.idempotency_key) > 180:
            raise RequestValidationError("idempotency key is invalid")


@dataclass(frozen=True)
class VerifiedMemorySubject:
    subject_type: str
    subject_id: str
    identity_state: str

    def __post_init__(self) -> None:
        SubjectRef(self.subject_type, self.subject_id)
        if self.identity_state not in {"VERIFIED", "UNVERIFIED", "UNKNOWN", "NAME_MATCH_ONLY"}:
            raise RequestValidationError("identity state is invalid")


@dataclass(frozen=True)
class SessionMemoryUse:
    state: str
    storage_permission_state: str
    marketing_consent: bool

    def __post_init__(self) -> None:
        if self.state not in {"ACTIVE", "NOT_GRANTED", "WITHDRAWN", "START_FRESH"}:
            raise RequestValidationError("session memory-use state is invalid")
        if self.storage_permission_state not in {"ACTIVE", "NOT_GRANTED", "WITHDRAWN"}:
            raise RequestValidationError("storage permission state is invalid")
        if type(self.marketing_consent) is not bool:
            raise RequestValidationError("marketing consent context must be boolean")


@dataclass(frozen=True)
class MemoryCurrentContext:
    topic: str
    intent: str
    entities: tuple[str, ...]
    customer_current_statements: dict[str, str]
    operational_priority: str
    conversation_mode: str
    explicit_memory_request: bool = False
    provenance_challenge: bool = False

    def __post_init__(self) -> None:
        for name, value in (("topic", self.topic), ("intent", self.intent)):
            if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", value):
                raise RequestValidationError(f"{name} is invalid")
        if not isinstance(self.entities, tuple) or len(self.entities) > 10:
            raise RequestValidationError("entities must be bounded")
        if any(not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_ -]{1,64}", item) for item in self.entities):
            raise RequestValidationError("entity is invalid")
        if not isinstance(self.customer_current_statements, dict) or len(self.customer_current_statements) > 10:
            raise RequestValidationError("current statements must be bounded")
        for key, value in self.customer_current_statements.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", key or "") or not isinstance(value, str) or len(value) > 80:
                raise RequestValidationError("current statement is invalid")
        if self.operational_priority not in {"NORMAL", "COMPLAINT", "PAYMENT_PROBLEM", "SECURITY_CONCERN", "URGENT_SUPPORT", "ANGRY", "REFUND_DISPUTE", "ACCOUNT_ACCESS"}:
            raise RequestValidationError("operational priority is invalid")
        if not re.fullmatch(r"[A-Z][A-Z_]{2,39}", self.conversation_mode or ""):
            raise RequestValidationError("conversation mode is invalid")
        if type(self.explicit_memory_request) is not bool or type(self.provenance_challenge) is not bool:
            raise RequestValidationError("memory review flags must be boolean")


@dataclass(frozen=True)
class MemoryLimits:
    functional: int = 5
    relational: int = 1

    def __post_init__(self) -> None:
        if type(self.functional) is not int or not 0 <= self.functional <= 5:
            raise RequestValidationError("functional memory limit must be 0..5")
        if type(self.relational) is not int or not 0 <= self.relational <= 1:
            raise RequestValidationError("relationship memory limit must be 0..1")


@dataclass(frozen=True)
class CustomerMemoryRetrieveInput:
    subject: VerifiedMemorySubject
    session_memory_use: SessionMemoryUse
    current_context: MemoryCurrentContext
    limits: MemoryLimits


@dataclass(frozen=True)
class ToolRequest:
    request_id: str
    correlation_id: str
    actor: Actor
    capability: CapabilityRef
    purpose: str
    channel: str
    environment: str
    input: KnowledgeRetrieveInput | OperationalMetricsRetrieveInput | ActivityRecordInput | CustomerPreferenceRecordInput | CustomerRelationshipFactRecordInput | CustomerMemoryRetrieveInput
    bae_authorization: Any = None

    def __post_init__(self) -> None:
        for name, value in (("request_id", self.request_id), ("correlation_id", self.correlation_id)):
            try:
                UUID(value)
            except (ValueError, TypeError, AttributeError) as exc:
                raise RequestValidationError(f"{name} must be a UUID") from exc

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ToolRequest":
        if not isinstance(value, dict):
            raise RequestValidationError("request must be an object")
        expected = {"request_id", "correlation_id", "actor", "capability", "purpose", "channel", "environment", "input"}
        if not expected.issubset(set(value)) or set(value) - expected - {"bae_authorization"}:
            raise RequestValidationError("unexpected or missing request fields")
        if set(value["actor"]) != {"actor_id", "actor_type"} or set(value["capability"]) != {"capability_id", "capability_version"}:
            raise RequestValidationError("actor or capability fields invalid")
        capability_id = value["capability"].get("capability_id")
        if capability_id == "customer.memory.retrieve":
            required = {"subject", "session_memory_use", "current_context", "limits"}
            if set(value["input"]) != required:
                raise RequestValidationError("unexpected or missing memory-recall input fields")
            if set(value["input"]["subject"]) != {"subject_type", "subject_id", "identity_state"}:
                raise RequestValidationError("memory subject fields invalid")
            if set(value["input"]["session_memory_use"]) != {"state", "storage_permission_state", "marketing_consent"}:
                raise RequestValidationError("session memory-use fields invalid")
            context_fields = {"topic", "intent", "entities", "customer_current_statements", "operational_priority", "conversation_mode", "explicit_memory_request", "provenance_challenge"}
            if set(value["input"]["current_context"]) != context_fields:
                raise RequestValidationError("current context fields invalid")
            if set(value["input"]["limits"]) != {"functional", "relational"}:
                raise RequestValidationError("memory limit fields invalid")
            current = dict(value["input"]["current_context"])
            current["entities"] = tuple(current["entities"])
            current["customer_current_statements"] = dict(current["customer_current_statements"])
            input_model = CustomerMemoryRetrieveInput(
                VerifiedMemorySubject(**value["input"]["subject"]),
                SessionMemoryUse(**value["input"]["session_memory_use"]),
                MemoryCurrentContext(**current), MemoryLimits(**value["input"]["limits"]),
            )
        elif capability_id == "customer.relationship_fact.record":
            required = {"subject", "relationship_fact", "source", "memory_authorization", "stated_at", "idempotency_key"}
            if set(value["input"]) != required:
                raise RequestValidationError("unexpected or missing relationship-fact input fields")
            if set(value["input"]["subject"]) != {"subject_type", "subject_id"}:
                raise RequestValidationError("subject fields invalid")
            if set(value["input"]["relationship_fact"]) != {"fact_key", "fact_value", "information_type", "certainty"}:
                raise RequestValidationError("relationship-fact fields invalid")
            if set(value["input"]["source"]) != {"source_type", "source_reference", "statement_reference", "source_context_summary"}:
                raise RequestValidationError("relationship source fields invalid")
            if set(value["input"]["memory_authorization"]) != {"state", "purpose"}:
                raise RequestValidationError("memory authorization fields invalid")
            input_model = CustomerRelationshipFactRecordInput(
                SubjectRef(**value["input"]["subject"]), RelationshipFactValue(**value["input"]["relationship_fact"]),
                RelationshipSource(**value["input"]["source"]), MemoryAuthorization(**value["input"]["memory_authorization"]),
                value["input"]["stated_at"], value["input"]["idempotency_key"],
            )
        elif capability_id == "customer.preference.record":
            required = {"subject", "preference", "source", "memory_authorization", "marketing_consent", "stated_at", "idempotency_key"}
            if set(value["input"]) != required:
                raise RequestValidationError("unexpected or missing preference input fields")
            if set(value["input"]["subject"]) != {"subject_type", "subject_id"}:
                raise RequestValidationError("subject fields invalid")
            if set(value["input"]["preference"]) != {"key", "value", "information_type"}:
                raise RequestValidationError("preference fields invalid")
            if set(value["input"]["source"]) != {"source_type", "source_reference", "statement_reference"}:
                raise RequestValidationError("preference source fields invalid")
            if set(value["input"]["memory_authorization"]) != {"state", "purpose"}:
                raise RequestValidationError("memory authorization fields invalid")
            input_model = CustomerPreferenceRecordInput(
                SubjectRef(**value["input"]["subject"]), PreferenceValue(**value["input"]["preference"]),
                PreferenceSource(**value["input"]["source"]), MemoryAuthorization(**value["input"]["memory_authorization"]),
                value["input"]["marketing_consent"], value["input"]["stated_at"], value["input"]["idempotency_key"],
            )
        elif capability_id == "activity.record":
            if set(value["input"]) != {"activity_type", "subject", "source", "occurred_at", "idempotency_key", "properties", "fact_classification"}:
                raise RequestValidationError("unexpected or missing activity input fields")
            if not isinstance(value["input"]["subject"], dict) or set(value["input"]["subject"]) != {"subject_type", "subject_id"}:
                raise RequestValidationError("subject fields invalid")
            if not isinstance(value["input"]["source"], dict) or set(value["input"]["source"]) != {"source_type", "source_id"}:
                raise RequestValidationError("source fields invalid")
            input_model = ActivityRecordInput(
                activity_type=value["input"]["activity_type"], subject=SubjectRef(**value["input"]["subject"]),
                source=SourceRef(**value["input"]["source"]), occurred_at=value["input"]["occurred_at"],
                idempotency_key=value["input"]["idempotency_key"], properties=dict(value["input"]["properties"]),
                fact_classification=value["input"]["fact_classification"],
            )
        elif capability_id == "operational.metrics.retrieve":
            if set(value["input"]) != {"domain", "metric_names", "time_window", "max_results"}:
                raise RequestValidationError("unexpected or missing metrics input fields")
            input_model: KnowledgeRetrieveInput | OperationalMetricsRetrieveInput = OperationalMetricsRetrieveInput(
                domain=value["input"]["domain"], metric_names=tuple(value["input"]["metric_names"]),
                time_window=value["input"]["time_window"], max_results=value["input"]["max_results"],
            )
        else:
            if set(value["input"]) != {"query", "domain", "max_results"}:
                raise RequestValidationError("unexpected or missing input fields")
            input_model = KnowledgeRetrieveInput(**value["input"])
        return cls(
            str(value["request_id"]), str(value["correlation_id"]), Actor(**value["actor"]),
            CapabilityRef(**value["capability"]), str(value["purpose"]), str(value["channel"]),
            str(value["environment"]), input_model,
            bae_authorization=value.get("bae_authorization"),
        )


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str = "knowledge.retrieve"
    capability_version: str = "1.0"
    bros_level: int = 1
    tool_class: str = "T0"
    enabled: bool = True
    allowed_environments: frozenset[str] = frozenset({"automated_test", "development", "prototype"})
    allowed_purposes: frozenset[str] = frozenset({"customer_education", "product_guidance", "policy_explanation", "internal_test"})
    allowed_channels: frozenset[str] = frozenset({"website_chat", "internal_test"})
    specifically_authorized_bounded_write: bool = False
    allowed_activity_types: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ActorPermission:
    actor_type: str
    domains: frozenset[str]
    classifications: frozenset[str]
    purposes: frozenset[str] = frozenset()
    channels: frozenset[str] = frozenset()
    activity_types: frozenset[str] = frozenset()
    subject_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AuthorityDecision:
    execution_allowed: bool
    human_review_required: bool
    reason: str


def reconcile_authority(bros_level: int, tool_class: str, *, specifically_authorized_bounded_write: bool = False) -> AuthorityDecision:
    if tool_class == "TX":
        return AuthorityDecision(False, False, "prohibited")
    if bros_level >= 3:
        return AuthorityDecision(False, False, "reserved_human_authority")
    if bros_level == 2 or tool_class == "T3":
        return AuthorityDecision(False, True, "human_approval_required")
    if tool_class == "T2" and not specifically_authorized_bounded_write:
        return AuthorityDecision(False, False, "bounded_write_not_specifically_authorized")
    if bros_level == 1 and tool_class in {"T0", "T1", "T2"}:
        return AuthorityDecision(True, False, "explicit_authority_permitted")
    return AuthorityDecision(False, False, "authority_uncertain")


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    classification: ErrorClass | None
    reason: str
    access_classifications: frozenset[str] = frozenset()


@dataclass(frozen=True)
class KnowledgeItem:
    knowledge_id: str
    title: str
    version: str
    domain: str
    status: str
    classification: str
    source_reference: str
    content: str


@dataclass(frozen=True)
class OperationalMetricItem:
    metric_name: str
    domain: str
    value: Any
    unit: str
    classification: str
    status: str
    source_reference: str
    observed_at: str


import hmac
import secrets

# Gateway internal HMAC secret for execution context provenance
_GATEWAY_EXECUTION_SECRET = secrets.token_bytes(32)
_VALID_EXECUTION_CAPABILITIES: set[str] = set()


@dataclass(frozen=True)
class GatewayExecutionContext:
    execution_id: str
    event_id: str
    request_id: str
    capability_id: str
    hmac_signature: str
    is_trusted_internal: bool = False

    @classmethod
    def create(cls, event_id: str, request_id: str, capability_id: str, is_trusted_internal: bool = False) -> "GatewayExecutionContext":
        execution_id = secrets.token_hex(16)
        msg = f"{execution_id}:{event_id}:{request_id}:{capability_id}:{is_trusted_internal}".encode("utf-8")
        signature = hmac.new(_GATEWAY_EXECUTION_SECRET, msg, hashlib.sha256).hexdigest()
        token = cls(
            execution_id=execution_id,
            event_id=event_id,
            request_id=request_id,
            capability_id=capability_id,
            hmac_signature=signature,
            is_trusted_internal=is_trusted_internal,
        )
        _VALID_EXECUTION_CAPABILITIES.add(token.execution_id)
        return token

    @classmethod
    def trusted_internal(cls, purpose: str = "internal_migration_or_test") -> "GatewayExecutionContext":
        return cls.create(f"INTERNAL-{uuid4()}", str(uuid4()), purpose, is_trusted_internal=True)

    def verify_and_retire(self, expected_request_id: str | None = None, expected_capability_id: str | None = None) -> bool:
        if self.execution_id not in _VALID_EXECUTION_CAPABILITIES:
            return False
        msg = f"{self.execution_id}:{self.event_id}:{self.request_id}:{self.capability_id}:{self.is_trusted_internal}".encode("utf-8")
        expected_sig = hmac.new(_GATEWAY_EXECUTION_SECRET, msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(self.hmac_signature, expected_sig):
            return False
        if expected_request_id and not self.is_trusted_internal and self.request_id != expected_request_id:
            return False
        if expected_capability_id and not self.is_trusted_internal and self.capability_id != expected_capability_id:
            return False
        # Retire execution capability on use to prevent replay/cross-execution reuse
        _VALID_EXECUTION_CAPABILITIES.discard(self.execution_id)
        return True


def verify_adapter_provenance(execution_context: Any, request_id: str | None = None, capability_id: str | None = None) -> None:
    """Verifies that an execution capability is an authentic, unexpired GatewayExecutionContext instance."""
    if not isinstance(execution_context, GatewayExecutionContext):
        raise PermissionError("Direct adapter execution prohibited: must be invoked via canonical Tool Gateway with authentic GatewayExecutionContext")
    if not execution_context.verify_and_retire(expected_request_id=request_id, expected_capability_id=capability_id):
        raise PermissionError("Gateway execution context verification failed: forged, replayed, expired, or mismatched execution context")


@dataclass(frozen=True)
class AdapterContext:
    query: str
    domain: str
    max_results: int
    access_classifications: frozenset[str]
    request_id: str
    correlation_id: str
    gateway_execution_context: GatewayExecutionContext | None = None


@dataclass(frozen=True)
class MetricsAdapterContext:
    domain: str
    metric_names: tuple[str, ...]
    time_window: str
    max_results: int
    access_classifications: frozenset[str]
    request_id: str
    correlation_id: str
    gateway_execution_context: GatewayExecutionContext | None = None


class KnowledgeAdapter(Protocol):
    tool_id: str
    tool_version: str

    def health(self) -> ToolHealth: ...
    def retrieve(self, context: AdapterContext) -> list[dict[str, Any]]: ...


@dataclass
class LocalKnowledgeAdapter:
    fixtures: list[dict[str, Any]]
    state: ToolHealth = ToolHealth.HEALTHY
    fail: bool = False
    tool_id: str = "local_knowledge_fixture"
    tool_version: str = "1.0"
    last_context: AdapterContext | None = None

    def health(self) -> ToolHealth:
        return self.state

    def retrieve(self, context: AdapterContext) -> list[dict[str, Any]]:
        # Enforce fail-closed boundary: verify provenance via GatewayExecutionContext
        if not context or not getattr(context, "gateway_execution_context", None):
            raise PermissionError("Direct adapter execution prohibited: must be invoked via canonical Tool Gateway")
        verify_adapter_provenance(context.gateway_execution_context, request_id=context.request_id, capability_id=getattr(context.gateway_execution_context, "capability_id", None))

        self.last_context = context
        if self.fail:
            raise RuntimeError("deterministic adapter failure")
        terms = set(re.findall(r"[a-z0-9]+", context.query.lower()))
        matches = []
        for item in self.fixtures:
            searchable = f"{item.get('title', '')} {item.get('content', '')}".lower()
            if item.get("status") != "Active" or item.get("domain") != context.domain:
                continue
            if item.get("classification") not in context.access_classifications:
                continue
            if terms and not terms.intersection(re.findall(r"[a-z0-9]+", searchable)):
                continue
            matches.append(dict(item))
        return matches[: context.max_results]


@dataclass
class LocalOperationalMetricsAdapter:
    fixtures: list[dict[str, Any]]
    state: ToolHealth = ToolHealth.HEALTHY
    fail: bool = False
    tool_id: str = "local_operational_metrics"
    tool_version: str = "1.0"
    last_context: MetricsAdapterContext | None = None

    def health(self) -> ToolHealth:
        return self.state

    def health_check(self) -> ToolHealth:
        return self.health()

    def retrieve(self, context: MetricsAdapterContext) -> list[dict[str, Any]]:
        self.last_context = context
        if self.fail:
            raise RuntimeError("deterministic metrics adapter failure")
        requested = set(context.metric_names)
        matches = [
            dict(item) for item in self.fixtures
            if item.get("status") == "Active"
            and item.get("domain") == context.domain
            and item.get("metric_name") in requested
            and item.get("classification") in context.access_classifications
            and item.get("time_window", "current_snapshot") == context.time_window
        ]
        return matches[: context.max_results]

    def validate_result(self, raw_items: Any, context: MetricsAdapterContext) -> list[dict[str, Any]]:
        return ToolGateway._validate_metrics_output(raw_items, context)

    def normalize_result(self, raw_items: Any, context: MetricsAdapterContext) -> list[dict[str, Any]]:
        return self.validate_result(raw_items, context)


@dataclass(frozen=True)
class ActivityRecord:
    activity_id: str
    activity_type: str
    subject_type: str
    subject_id: str
    source_type: str
    source_id: str
    channel: str
    purpose: str
    occurred_at: str
    recorded_at: str
    correlation_id: str
    idempotency_key: str
    properties: dict[str, Any]
    fact_classification: str
    semantic_fingerprint: str


@dataclass(frozen=True)
class ActivityAdapterContext:
    activity_type: str
    subject: SubjectRef
    source: SourceRef
    channel: str
    purpose: str
    occurred_at: str
    idempotency_key: str
    properties: dict[str, Any]
    fact_classification: str
    request_id: str
    correlation_id: str
    allowed_activity_types: frozenset[str]
    gateway_execution_context: GatewayExecutionContext | None = None


@dataclass(frozen=True)
class DurableActivityOutcome:
    record: ActivityRecord
    recorded: bool
    duplicate: bool
    idempotency_decision: str
    audit_event_id: str


class DurableActivityError(RuntimeError):
    def __init__(self, classification: ErrorClass, message: str, *, status: ResultStatus = ResultStatus.FAILED,
                 retryable: bool = False, activity_id: str | None = None, audit_event_id: str | None = None) -> None:
        super().__init__(message)
        self.classification = classification
        self.message = message
        self.status = status
        self.retryable = retryable
        self.activity_id = activity_id
        self.audit_event_id = audit_event_id


@dataclass(frozen=True)
class PreferenceRecord:
    preference_id: str
    subject_type: str
    subject_id: str
    category: str
    preference_key: str
    preference_value: str
    information_type: str
    source_type: str
    source_reference: str
    statement_reference: str
    purpose: str
    memory_permission_state_at_write: str
    stated_at: str
    recorded_at: str
    correlation_id: str
    idempotency_key: str
    payload_fingerprint: str
    status: str
    supersedes_preference_id: str | None


@dataclass(frozen=True)
class PreferenceAdapterContext:
    subject: SubjectRef
    preference: PreferenceValue
    source: PreferenceSource
    memory_authorization: MemoryAuthorization
    stated_at: str
    idempotency_key: str
    request_id: str
    correlation_id: str
    channel: str
    gateway_execution_context: GatewayExecutionContext | None = None


@dataclass(frozen=True)
class DurablePreferenceOutcome:
    record: PreferenceRecord
    recorded: bool
    duplicate: bool
    idempotency_decision: str
    audit_event_id: str
    previous_preference_id: str | None


@dataclass(frozen=True)
class RelationshipFactRecord:
    relationship_fact_id: str
    subject_type: str
    subject_id: str
    fact_category: str
    fact_key: str
    fact_value: dict[str, Any]
    information_type: str
    certainty: str
    sensitivity_class: str
    source_type: str
    source_reference: str
    statement_reference: str
    source_context_summary: str
    purpose: str
    memory_permission_state_at_write: str
    stated_at: str
    recorded_at: str
    request_id: str
    correlation_id: str
    idempotency_key: str
    payload_fingerprint: str
    status: str
    supersedes_fact_id: str | None
    event_date_or_period: str | None
    related_person_context: dict[str, Any] | None


@dataclass(frozen=True)
class RelationshipFactAdapterContext:
    subject: SubjectRef
    relationship_fact: RelationshipFactValue
    source: RelationshipSource
    memory_authorization: MemoryAuthorization
    stated_at: str
    idempotency_key: str
    request_id: str
    correlation_id: str
    channel: str
    gateway_execution_context: GatewayExecutionContext | None = None


@dataclass(frozen=True)
class DurableRelationshipFactOutcome:
    record: RelationshipFactRecord
    recorded: bool
    duplicate: bool
    idempotency_decision: str
    audit_event_id: str
    previous_fact_id: str | None


@dataclass(frozen=True)
class MemoryRecallAdapterContext:
    subject: VerifiedMemorySubject
    session_memory_use: SessionMemoryUse
    purpose: str
    current_context: MemoryCurrentContext
    limits: MemoryLimits
    request_id: str
    correlation_id: str
    channel: str
    gateway_execution_context: GatewayExecutionContext | None = None


@dataclass(frozen=True)
class MemoryRecallOutcome:
    functional_context: tuple[dict[str, Any], ...]
    relationship_context: tuple[dict[str, Any], ...]
    instructions: dict[str, Any]
    selected_memory_ids: tuple[str, ...]
    recall_modes: tuple[str, ...]
    audit_event_id: str


class InMemoryActivityStore:
    """Append-only prototype store. Rollback is private and transaction-only."""

    def __init__(self) -> None:
        self._records: list[ActivityRecord] = []
        self._by_key: dict[str, ActivityRecord] = {}

    def append(self, record: ActivityRecord) -> None:
        if record.idempotency_key in self._by_key:
            raise ValueError("idempotency key already exists")
        self._records.append(record)
        self._by_key[record.idempotency_key] = record

    def get_by_idempotency_key(self, key: str) -> ActivityRecord | None:
        return self._by_key.get(key)

    def get(self, activity_id: str) -> ActivityRecord | None:
        return next((record for record in self._records if record.activity_id == activity_id), None)

    def count(self) -> int:
        return len(self._records)

    def _rollback_append(self, activity_id: str) -> None:
        if not self._records or self._records[-1].activity_id != activity_id:
            raise RuntimeError("rollback target is not the staged append")
        record = self._records.pop()
        self._by_key.pop(record.idempotency_key, None)


@dataclass
class LocalActivityAdapter:
    store: InMemoryActivityStore
    state: ToolHealth = ToolHealth.HEALTHY
    fail_write: bool = False
    fail_postcondition: bool = False
    tool_id: str = "local_activity_store"
    tool_version: str = "1.0"
    last_context: ActivityAdapterContext | None = None

    def health(self) -> ToolHealth:
        return self.state

    def prepare(self, context: ActivityAdapterContext) -> ActivityRecord:
        self.last_context = context
        fingerprint_payload = {
            "activity_type": context.activity_type,
            "subject": asdict(context.subject), "source": asdict(context.source),
            "channel": context.channel, "purpose": context.purpose,
            "occurred_at": context.occurred_at, "properties": context.properties,
            "fact_classification": context.fact_classification,
        }
        fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return ActivityRecord(
            f"ACT-{uuid4()}", context.activity_type, context.subject.subject_type, context.subject.subject_id,
            context.source.source_type, context.source.source_id, context.channel, context.purpose,
            context.occurred_at, utc_now(), context.correlation_id, context.idempotency_key,
            dict(context.properties), context.fact_classification, fingerprint,
        )

    def commit(self, record: ActivityRecord) -> None:
        if self.fail_write:
            raise RuntimeError("deterministic write failure")
        self.store.append(record)

    def validate_postcondition(self, record: ActivityRecord, count_before: int) -> bool:
        if self.fail_postcondition:
            return False
        return (
            self.store.count() == count_before + 1
            and self.store.get(record.activity_id) == record
            and self.store.get_by_idempotency_key(record.idempotency_key) == record
        )

    def rollback(self, record: ActivityRecord) -> None:
        self.store._rollback_append(record.activity_id)


class ToolRegistry:
    def __init__(self, capability: CapabilityDefinition, adapter: KnowledgeAdapter) -> None:
        self._definitions: dict[str, CapabilityDefinition] = {capability.capability_id: capability}
        self._adapters: dict[str, KnowledgeAdapter] = {capability.capability_id: adapter}

    @property
    def capability(self) -> CapabilityDefinition:
        """TG-P01 compatibility view for a single-capability registry."""
        return next(iter(self._definitions.values()))

    def register(self, capability: CapabilityDefinition, adapter: KnowledgeAdapter) -> None:
        if capability.capability_id in self._definitions:
            raise ValueError("capability already registered")
        self._definitions[capability.capability_id] = capability
        self._adapters[capability.capability_id] = adapter

    def definition(self, capability_id: str, version: str) -> CapabilityDefinition | None:
        definition = self._definitions.get(capability_id)
        if definition and definition.capability_version == version:
            return definition
        return None

    def resolve(self, capability_id: str, version: str) -> KnowledgeAdapter | None:
        return self._adapters.get(capability_id) if self.definition(capability_id, version) else None


@dataclass(frozen=True)
class AuditEvent:
    audit_event_id: str
    request_id: str
    correlation_id: str
    actor_id: str
    actor_type: str
    capability_id: str
    capability_version: str
    bros_authority_level: int
    tool_authority_class: str
    permission_version: str
    environment: str
    channel: str
    purpose: str
    permission_decision: str
    tool_id: str | None
    tool_version: str | None
    execution_status: str
    error_classification: str | None
    started_at: str
    completed_at: str
    metric_domain: str | None = None
    activity_type: str | None = None
    idempotency_reference: str | None = None
    idempotency_decision: str | None = None
    activity_id: str | None = None
    subject_id: str | None = None
    preference_key: str | None = None
    memory_permission_state: str | None = None
    previous_preference_id: str | None = None
    new_preference_id: str | None = None
    fact_key: str | None = None
    sensitivity_class: str | None = None
    previous_fact_id: str | None = None
    new_fact_id: str | None = None
    identity_verification_state: str | None = None
    session_memory_use_state: str | None = None
    memory_classes_considered: tuple[str, ...] = ()
    memory_ids_selected: tuple[str, ...] = ()
    functional_count: int | None = None
    relationship_count: int | None = None
    recall_modes: tuple[str, ...] = ()


@dataclass
class AuditSink:
    events: list[AuditEvent] = field(default_factory=list)
    fail: bool = False

    def record(self, event: AuditEvent) -> None:
        if self.fail:
            raise RuntimeError("deterministic audit failure")
        self.events.append(event)


@dataclass(frozen=True)
class NormalizedResult:
    request_id: str
    correlation_id: str
    capability_id: str
    status: ResultStatus
    result: dict[str, Any] | None
    result_classification: str | None
    implementation: dict[str, str] | None
    authority: dict[str, Any]
    retryable: bool
    human_review_required: bool
    error: dict[str, str] | None
    evidence_reference: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        return value


class ToolGateway:
    PERMISSION_VERSIONS = {
        "knowledge.retrieve": "TG-P01-permissions-1.0",
        "operational.metrics.retrieve": "TG-P02-permissions-1.0",
        "activity.record": "TG-P03-permissions-1.0",
        "customer.preference.record": "TG-P05A-permissions-1.0",
        "customer.relationship_fact.record": "TG-P05B-permissions-1.0",
        "customer.memory.retrieve": "TG-P06-permissions-1.0",
    }

    def __init__(self, registry: ToolRegistry, audit: AuditSink, permissions: dict[str, Any] | None = None, policy_evaluator: Any = None) -> None:
        self.registry, self.audit = registry, audit
        self.policy_evaluator = policy_evaluator
        default_knowledge_permissions = {
            "budly_service": ActorPermission("budly_service", frozenset({"customer_policy", "educational"}), frozenset({"Public", "PUBLIC"})),
            "administrator": ActorPermission("administrator", frozenset({"customer_policy", "educational", "governance"}), frozenset({"Public", "PUBLIC", "Restricted", "RESTRICTED"})),
            "test_harness": ActorPermission("test_harness", frozenset({"customer_policy", "educational", "governance"}), frozenset({"Public", "PUBLIC", "Restricted", "RESTRICTED"})),
            "bae_steward": ActorPermission("bae_steward", frozenset({"customer_policy", "educational"}), frozenset({"Public", "PUBLIC", "Internal", "INTERNAL"})),
        }
        if permissions:
            if "knowledge.retrieve" in permissions and isinstance(permissions["knowledge.retrieve"], dict):
                knowledge_permissions = permissions["knowledge.retrieve"]
            else:
                knowledge_permissions = {**default_knowledge_permissions, **permissions}
        else:
            knowledge_permissions = default_knowledge_permissions

        self.permission_sets: dict[str, dict[str, ActorPermission]] = {
            "knowledge.retrieve": knowledge_permissions,
            "operational.metrics.retrieve": {
                "budly_service": ActorPermission("budly_service", frozenset({"tool_gateway", "system_health"}), frozenset({"PUBLIC", "INTERNAL"}), frozenset({"operational_status", "system_health_review", "internal_test"}), frozenset({"website_chat", "internal_test"})),
                "administrator": ActorPermission("administrator", frozenset({"revenue_operations", "tool_gateway", "workflow_operations", "system_health"}), frozenset({"PUBLIC", "INTERNAL", "RESTRICTED"}), frozenset({"operational_status", "system_health_review", "internal_test", "admin_review"}), frozenset({"admin_console", "internal_test"})),
                "test_harness": ActorPermission("test_harness", frozenset({"revenue_operations", "tool_gateway", "workflow_operations", "system_health"}), frozenset({"PUBLIC", "INTERNAL", "RESTRICTED"}), frozenset({"operational_status", "system_health_review", "internal_test", "admin_review"}), frozenset({"admin_console", "internal_test"})),
            },
            "activity.record": {
                "budly_service": ActorPermission("budly_service", frozenset(), frozenset(), frozenset({"relationship_history", "interaction_recording", "support_history", "recommendation_evidence", "internal_test"}), frozenset({"website_chat", "internal_test"}), ALLOWED_ACTIVITY_TYPES),
                "administrator": ActorPermission("administrator", frozenset(), frozenset(), frozenset({"relationship_history", "interaction_recording", "support_history", "recommendation_evidence", "internal_test"}), frozenset({"admin_console", "internal_test"}), ALLOWED_ACTIVITY_TYPES),
                "system_service": ActorPermission("system_service", frozenset(), frozenset(), frozenset({"relationship_history", "interaction_recording", "support_history", "recommendation_evidence", "internal_test"}), frozenset({"system_internal", "internal_test"}), ALLOWED_ACTIVITY_TYPES),
                "test_harness": ActorPermission("test_harness", frozenset(), frozenset(), frozenset({"relationship_history", "interaction_recording", "support_history", "recommendation_evidence", "internal_test"}), frozenset({"website_chat", "admin_console", "system_internal", "internal_test"}), ALLOWED_ACTIVITY_TYPES),
            },
            "customer.preference.record": {
                "budly_service": ActorPermission("budly_service", frozenset(), frozenset({"INTERNAL"}), frozenset({"conversation_continuity", "education_personalization", "approved_recommendation_context", "support_continuity", "internal_test"}), frozenset({"website_chat", "internal_test"}), subject_ids=frozenset({"P-TEST-001"})),
                "administrator": ActorPermission("administrator", frozenset(), frozenset({"INTERNAL"}), frozenset({"conversation_continuity", "education_personalization", "approved_recommendation_context", "support_continuity", "internal_test"}), frozenset({"admin_console", "internal_test"}), subject_ids=frozenset({"P-TEST-001", "P-TEST-002"})),
                "test_harness": ActorPermission("test_harness", frozenset(), frozenset({"INTERNAL"}), frozenset({"conversation_continuity", "education_personalization", "approved_recommendation_context", "support_continuity", "internal_test"}), frozenset({"website_chat", "admin_console", "internal_test"}), subject_ids=frozenset({"P-TEST-001", "P-TEST-002"})),
            },
            "customer.relationship_fact.record": {
                "budly_service": ActorPermission("budly_service", frozenset(), frozenset({"R1"}), frozenset({"conversation_continuity", "relationship_continuity", "customer_service", "appropriate_personalization", "support_continuity", "internal_test"}), frozenset({"website_chat", "internal_test"}), subject_ids=frozenset({"P-TEST-001"})),
                "administrator": ActorPermission("administrator", frozenset(), frozenset({"R1"}), frozenset({"conversation_continuity", "relationship_continuity", "customer_service", "appropriate_personalization", "support_continuity", "internal_test"}), frozenset({"admin_console", "internal_test"}), subject_ids=frozenset({"P-TEST-001", "P-TEST-002"})),
                "test_harness": ActorPermission("test_harness", frozenset(), frozenset({"R1"}), frozenset({"conversation_continuity", "relationship_continuity", "customer_service", "appropriate_personalization", "support_continuity", "internal_test"}), frozenset({"website_chat", "admin_console", "internal_test"}), subject_ids=frozenset({"P-TEST-001", "P-TEST-002"})),
            },
            "customer.memory.retrieve": {
                "budly_service": ActorPermission("budly_service", frozenset(), frozenset({"PREFERENCE", "R1"}), frozenset({"product_assistance", "education_assistance", "support_assistance", "relationship_conversation", "explicit_memory_review", "internal_test"}), frozenset({"website_chat", "internal_test"}), subject_ids=frozenset({"P-TEST-001"})),
                "administrator": ActorPermission("administrator", frozenset(), frozenset({"PREFERENCE", "R1"}), frozenset({"explicit_memory_review", "internal_test"}), frozenset({"admin_console", "internal_test"}), subject_ids=frozenset({"P-TEST-001", "P-TEST-002"})),
                "test_harness": ActorPermission("test_harness", frozenset(), frozenset({"PREFERENCE", "R1"}), frozenset({"product_assistance", "education_assistance", "support_assistance", "relationship_conversation", "explicit_memory_review", "internal_test"}), frozenset({"website_chat", "admin_console", "internal_test"}), subject_ids=frozenset({"P-TEST-001", "P-TEST-002"})),
            },
        }
        if permissions:
            for cap_id, p_dict in permissions.items():
                if isinstance(p_dict, dict):
                    self.permission_sets[cap_id] = p_dict

    def authorize(self, request: ToolRequest) -> PermissionDecision:
        definition = self.registry.definition(request.capability.capability_id, request.capability.capability_version)
        if definition is None:
            return PermissionDecision(False, ErrorClass.UNKNOWN_CAPABILITY, "capability not registered")
        if not definition.enabled:
            return PermissionDecision(False, ErrorClass.CAPABILITY_DISABLED, "capability disabled")
        if request.environment not in definition.allowed_environments:
            return PermissionDecision(False, ErrorClass.ENVIRONMENT_DENIED, "environment prohibited")

        # BAE continuous authorization check at entry boundary
        if getattr(request.actor, "actor_type", "") == "bae_steward" or request.bae_authorization is not None or request.capability.capability_id.startswith("BAE-"):
            bae_auth = request.bae_authorization
            if bae_auth is None:
                return PermissionDecision(False, ErrorClass.BAE_AUTHORIZATION_REQUIRED, "BAE tool invocation requires an explicit B2 authorization decision")

            # If step > 1, check token presence and fields before full verifier
            step_token = getattr(bae_auth, "step_token", None)
            if step_token is not None and getattr(step_token, "step_number", 1) > 1:
                if not getattr(step_token, "checksum", "") or not getattr(step_token, "material_state_fingerprint", ""):
                    return PermissionDecision(False, ErrorClass.BAE_STEP_TOKEN_INVALID, "BAE step authorization token is invalid or missing material fingerprint")

            # If a trusted policy_evaluator verifier is present, verify authenticity, binding, and cryptographic fingerprint
            if self.policy_evaluator is not None and hasattr(self.policy_evaluator, "verify_decision"):
                is_valid, verify_err = self.policy_evaluator.verify_decision(
                    decision=bae_auth,
                    actor_id=request.actor.actor_id,
                    actor_type=request.actor.actor_type,
                    capability_id=request.capability.capability_id,
                    capability_version=request.capability.capability_version,
                    environment=request.environment,
                    channel=request.channel,
                    purpose=request.purpose,
                )
                if not is_valid:
                    if step_token is not None and getattr(step_token, "step_number", 1) > 1 and ("checksum" in str(verify_err).lower() or "fingerprint" in str(verify_err).lower()):
                        return PermissionDecision(False, ErrorClass.BAE_STEP_TOKEN_INVALID, f"BAE step token invalid: {verify_err}")
                    return PermissionDecision(False, ErrorClass.BAE_AUTHORIZATION_DENIED, f"BAE authorization verification failed: {verify_err}")
            else:
                # Direct check: Must be genuine AuthorizationDecision with status == PERMITTED
                auth_status = getattr(bae_auth, "status", None)
                status_val = getattr(auth_status, "value", str(auth_status)) if auth_status is not None else ""
                is_permitted = getattr(bae_auth, "permitted", False) and (status_val == "PERMITTED" or auth_status == "PERMITTED")
                if not is_permitted:
                    denial_reason = getattr(bae_auth, "denial_reason", None)
                    reason_detail = getattr(bae_auth, "reason_detail", "BAE authorization denied")
                    return PermissionDecision(False, ErrorClass.BAE_AUTHORIZATION_DENIED, f"BAE authorization denied: {reason_detail} ({denial_reason})")
        permission = self.permission_sets.get(definition.capability_id, {}).get(request.actor.actor_type)
        if permission is None:
            return PermissionDecision(False, ErrorClass.UNKNOWN_ACTOR, "actor type not registered")
        if request.purpose not in definition.allowed_purposes:
            return PermissionDecision(False, ErrorClass.PURPOSE_DENIED, "purpose not allowed")
        if permission.purposes and request.purpose not in permission.purposes:
            return PermissionDecision(False, ErrorClass.PURPOSE_DENIED, "purpose outside actor grant")
        if request.channel not in definition.allowed_channels:
            return PermissionDecision(False, ErrorClass.CHANNEL_DENIED, "channel not allowed")
        if permission.channels and request.channel not in permission.channels:
            return PermissionDecision(False, ErrorClass.CHANNEL_DENIED, "channel outside actor grant")
        if hasattr(request.input, "domain") and request.input.domain not in permission.domains:
            return PermissionDecision(False, ErrorClass.DATA_SCOPE_DENIED, "domain outside actor scope")
        if isinstance(request.input, ActivityRecordInput):
            if request.input.activity_type not in definition.allowed_activity_types or request.input.activity_type not in permission.activity_types:
                return PermissionDecision(False, ErrorClass.ACTIVITY_TYPE_NOT_AUTHORIZED, "activity type is not explicitly authorized")
            if request.input.source.source_type != request.actor.actor_type:
                return PermissionDecision(False, ErrorClass.PERMISSION_DENIED, "source identity does not match actor authority")
            if not request.input.idempotency_key.strip():
                return PermissionDecision(False, ErrorClass.IDEMPOTENCY_KEY_REQUIRED, "idempotency key is required")
            if request.input.fact_classification not in {"VERIFIED_OPERATIONAL_FACT", "CUSTOMER_STATED"}:
                return PermissionDecision(False, ErrorClass.FACT_CLASSIFICATION_INVALID, "fact classification is invalid")
            if request.input.fact_classification == "VERIFIED_OPERATIONAL_FACT" and any(key in request.input.properties for key in {"inferred", "inference", "assumption"}):
                return PermissionDecision(False, ErrorClass.FACT_CLASSIFICATION_INVALID, "inference cannot be recorded as verified fact")
            if set(request.input.properties).intersection(PROHIBITED_ACTIVITY_PROPERTIES):
                return PermissionDecision(False, ErrorClass.PERMISSION_DENIED, "properties attempt protected-state or existing-record mutation")
        if isinstance(request.input, CustomerPreferenceRecordInput):
            preference = request.input.preference
            memory = request.input.memory_authorization
            if request.input.subject.subject_id not in permission.subject_ids:
                return PermissionDecision(False, ErrorClass.SUBJECT_SCOPE_DENIED, "subject outside actor grant")
            if memory.purpose != request.purpose:
                return PermissionDecision(False, ErrorClass.PURPOSE_DENIED, "memory authorization purpose does not match request")
            if memory.state == "NOT_GRANTED":
                return PermissionDecision(False, ErrorClass.MEMORY_PERMISSION_REQUIRED, "active memory permission is required")
            if memory.state == "WITHDRAWN":
                return PermissionDecision(False, ErrorClass.MEMORY_PERMISSION_WITHDRAWN, "memory permission was withdrawn")
            if preference.information_type != "CUSTOMER_STATED" or request.input.source.source_type != "conversation":
                return PermissionDecision(False, ErrorClass.FACT_CLASSIFICATION_INVALID, "only customer-stated conversation evidence may persist")
            preference_definition = PREFERENCE_REGISTRY.definitions.get(preference.key)
            if preference_definition is None or not preference_definition.durable_memory_eligible:
                return PermissionDecision(False, ErrorClass.PREFERENCE_KEY_NOT_AUTHORIZED, "preference key is not authorized")
            if preference.value not in preference_definition.allowed_values:
                return PermissionDecision(False, ErrorClass.PREFERENCE_VALUE_INVALID, "preference value is not authorized")
            if request.purpose not in preference_definition.permitted_purposes:
                return PermissionDecision(False, ErrorClass.PURPOSE_DENIED, "preference key is not permitted for purpose")
        if isinstance(request.input, CustomerRelationshipFactRecordInput):
            fact = request.input.relationship_fact
            memory = request.input.memory_authorization
            if request.input.subject.subject_id not in permission.subject_ids:
                return PermissionDecision(False, ErrorClass.SUBJECT_SCOPE_DENIED, "subject outside actor grant")
            if memory.purpose != request.purpose:
                return PermissionDecision(False, ErrorClass.PURPOSE_DENIED, "memory authorization purpose does not match request")
            if memory.state == "NOT_GRANTED":
                return PermissionDecision(False, ErrorClass.MEMORY_PERMISSION_REQUIRED, "active memory permission is required")
            if memory.state == "WITHDRAWN":
                return PermissionDecision(False, ErrorClass.MEMORY_PERMISSION_WITHDRAWN, "memory permission was withdrawn")
            if fact.information_type != "CUSTOMER_STATED_RELATIONSHIP_FACT" or request.input.source.source_type != "conversation":
                return PermissionDecision(False, ErrorClass.FACT_CLASSIFICATION_INVALID, "only customer-stated conversation evidence may persist")
            if fact.certainty == "AMBIGUOUS":
                return PermissionDecision(False, ErrorClass.AMBIGUOUS_RELATIONSHIP_FACT, "ambiguous relationship fact requires confirmation")
            fact_definition = RELATIONSHIP_FACT_REGISTRY.definitions.get(fact.fact_key)
            if fact_definition is None:
                return PermissionDecision(False, ErrorClass.RELATIONSHIP_FACT_KEY_NOT_AUTHORIZED, "relationship fact key is not authorized")
            if fact_definition.sensitivity in {"R2", "RX"}:
                return PermissionDecision(False, ErrorClass.RELATIONSHIP_FACT_SENSITIVITY_DENIED, "relationship fact sensitivity is not persistable")
            if fact_definition.sensitivity not in permission.classifications:
                return PermissionDecision(False, ErrorClass.RELATIONSHIP_FACT_SENSITIVITY_DENIED, "actor lacks sensitivity permission")
            fields = set(fact.fact_value)
            if bool(fact.fact_value.get("is_minor")) and fields.intersection(MINOR_PROHIBITED_FIELDS):
                return PermissionDecision(False, ErrorClass.MINOR_DATA_PROHIBITED, "minor-specific prohibited data cannot persist")
            if bool(fact.fact_value.get("is_minor")) and not fact_definition.minor_allowed:
                return PermissionDecision(False, ErrorClass.MINOR_DATA_PROHIBITED, "fact type is not authorized for minor context")
            if not RELATIONSHIP_FACT_REGISTRY.validate_value(fact_definition, fact.fact_value):
                return PermissionDecision(False, ErrorClass.RELATIONSHIP_FACT_VALUE_INVALID, "relationship fact value is invalid")
            if request.purpose not in fact_definition.permitted_purposes:
                return PermissionDecision(False, ErrorClass.PURPOSE_DENIED, "relationship fact is not permitted for purpose")
        if isinstance(request.input, CustomerMemoryRetrieveInput):
            memory = request.input
            if memory.subject.subject_id not in permission.subject_ids:
                return PermissionDecision(False, ErrorClass.SUBJECT_SCOPE_DENIED, "subject outside actor grant")
            if memory.subject.identity_state != "VERIFIED":
                return PermissionDecision(False, ErrorClass.IDENTITY_VERIFICATION_REQUIRED, "verified customer identity is required")
            if memory.session_memory_use.state == "NOT_GRANTED":
                return PermissionDecision(False, ErrorClass.MEMORY_USE_PERMISSION_REQUIRED, "current-session memory-use permission is required")
            if memory.session_memory_use.state == "WITHDRAWN":
                return PermissionDecision(False, ErrorClass.MEMORY_PERMISSION_WITHDRAWN, "current-session memory-use permission was withdrawn")

        authority = reconcile_authority(definition.bros_level, definition.tool_class, specifically_authorized_bounded_write=definition.specifically_authorized_bounded_write)
        if not authority.execution_allowed:
            return PermissionDecision(False, ErrorClass.PERMISSION_DENIED, authority.reason, permission.classifications)
        return PermissionDecision(True, None, "explicit permission granted", permission.classifications)

    def execute(self, request: ToolRequest) -> NormalizedResult:
        started, event_id = utc_now(), str(uuid4())
        decision = self.authorize(request)
        if not decision.allowed:
            return self._finish(request, event_id, started, decision, ResultStatus.DENIED, None, None, False, False)
        adapter = self.registry.resolve(request.capability.capability_id, request.capability.capability_version)
        if adapter is None:
            denied = PermissionDecision(False, ErrorClass.UNKNOWN_CAPABILITY, "registry route unavailable")
            return self._finish(request, event_id, started, denied, ResultStatus.DENIED, None, None, False, False)
        health = adapter.health()
        if health != ToolHealth.HEALTHY:
            error = ErrorClass.CAPABILITY_DISABLED if health == ToolHealth.DISABLED else ErrorClass.TOOL_UNAVAILABLE
            unavailable = PermissionDecision(health != ToolHealth.DISABLED, error, f"tool health {health.value}", decision.access_classifications)
            status = ResultStatus.DENIED if health == ToolHealth.DISABLED else ResultStatus.UNAVAILABLE
            return self._finish(request, event_id, started, unavailable, status, adapter, None, health != ToolHealth.DISABLED, False)
        if request.capability.capability_id == "activity.record" and isinstance(request.input, ActivityRecordInput):
            if isinstance(adapter, LocalActivityAdapter):
                return self._execute_activity(request, adapter, decision, event_id, started)
            if callable(getattr(adapter, "execute_durable", None)):
                return self._execute_durable_activity(request, adapter, decision, event_id, started)
        if request.capability.capability_id == "customer.preference.record" and isinstance(request.input, CustomerPreferenceRecordInput):
            if callable(getattr(adapter, "execute_durable", None)):
                return self._execute_durable_preference(request, adapter, event_id, started)
        if request.capability.capability_id == "customer.relationship_fact.record" and isinstance(request.input, CustomerRelationshipFactRecordInput):
            if callable(getattr(adapter, "execute_durable", None)):
                return self._execute_durable_relationship_fact(request, adapter, event_id, started)
        if request.capability.capability_id == "customer.memory.retrieve" and isinstance(request.input, CustomerMemoryRetrieveInput):
            if callable(getattr(adapter, "retrieve_memory", None)):
                return self._execute_memory_recall(request, adapter, event_id, started)
        exec_context = GatewayExecutionContext.create(
            event_id=event_id,
            request_id=request.request_id,
            capability_id=request.capability.capability_id,
        )
        if request.capability.capability_id == "operational.metrics.retrieve" and isinstance(request.input, OperationalMetricsRetrieveInput):
            context: AdapterContext | MetricsAdapterContext = MetricsAdapterContext(
                request.input.domain, request.input.metric_names, request.input.time_window,
                request.input.max_results, decision.access_classifications, request.request_id,
                request.correlation_id, gateway_execution_context=exec_context,
            )
        elif (request.capability.capability_id == "knowledge.retrieve" or hasattr(adapter, "retrieve")) and isinstance(request.input, KnowledgeRetrieveInput):
            context = AdapterContext(
                request.input.query.strip(), request.input.domain, request.input.max_results,
                decision.access_classifications, request.request_id, request.correlation_id,
                gateway_execution_context=exec_context,
            )
        else:
            denied = PermissionDecision(False, ErrorClass.INPUT_VALIDATION_FAILED, "input model does not match capability", decision.access_classifications)
            return self._finish(request, event_id, started, denied, ResultStatus.DENIED, None, None, False, False)
        try:
            raw_items = adapter.retrieve(context)
        except Exception:
            failed = PermissionDecision(True, ErrorClass.ADAPTER_FAILURE, "adapter execution failed", decision.access_classifications)
            return self._finish(request, event_id, started, failed, ResultStatus.FAILED, adapter, None, True, False)
        try:
            items = self._validate_output(raw_items, context)
        except ValueError:
            failed = PermissionDecision(True, ErrorClass.OUTPUT_VALIDATION_FAILED, "adapter output failed validation", decision.access_classifications)
            return self._finish(request, event_id, started, failed, ResultStatus.FAILED, adapter, None, False, False)
        return self._finish(request, event_id, started, decision, ResultStatus.SUCCESS, adapter, items, False, False)

    def _execute_activity(self, request: ToolRequest, adapter: LocalActivityAdapter, decision: PermissionDecision, event_id: str, started: str) -> NormalizedResult:
        activity_input = request.input
        assert isinstance(activity_input, ActivityRecordInput)
        permission = self.permission_sets["activity.record"][request.actor.actor_type]
        context = ActivityAdapterContext(
            activity_input.activity_type, activity_input.subject, activity_input.source, request.channel, request.purpose,
            activity_input.occurred_at, activity_input.idempotency_key, dict(activity_input.properties),
            activity_input.fact_classification, request.request_id, request.correlation_id, permission.activity_types,
        )
        prepared = adapter.prepare(context)
        existing = adapter.store.get_by_idempotency_key(activity_input.idempotency_key)
        if existing is not None:
            if existing.semantic_fingerprint != prepared.semantic_fingerprint:
                conflict = PermissionDecision(False, ErrorClass.IDEMPOTENCY_CONFLICT, "idempotency key payload conflict")
                return self._finish(request, event_id, started, conflict, ResultStatus.DENIED, adapter, None, False, False, idempotency_decision="CONFLICT", activity_id=existing.activity_id)
            return self._finish_activity_success(request, adapter, existing, event_id, started, recorded=False, duplicate=True, idempotency_decision="DUPLICATE")
        count_before = adapter.store.count()
        try:
            adapter.commit(prepared)
        except Exception:
            failed = PermissionDecision(True, ErrorClass.WRITE_FAILED, "activity append failed", decision.access_classifications)
            return self._finish(request, event_id, started, failed, ResultStatus.FAILED, adapter, None, True, False, idempotency_decision="NEW", activity_id=None)
        if not adapter.validate_postcondition(prepared, count_before):
            adapter.rollback(prepared)
            failed = PermissionDecision(True, ErrorClass.POSTCONDITION_FAILED, "activity postcondition failed", decision.access_classifications)
            return self._finish(request, event_id, started, failed, ResultStatus.FAILED, adapter, None, False, False, idempotency_decision="NEW", activity_id=None)
        try:
            return self._finish_activity_success(request, adapter, prepared, event_id, started, recorded=True, duplicate=False, idempotency_decision="CREATED")
        except RuntimeError:
            adapter.rollback(prepared)
            definition = self.registry.definition(request.capability.capability_id, request.capability.capability_version)
            assert definition is not None
            return NormalizedResult(
                request.request_id, request.correlation_id, request.capability.capability_id, ResultStatus.FAILED, None, None,
                {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version},
                {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, False, False,
                {"classification": ErrorClass.AUDIT_FAILURE.value, "message": "required audit evidence could not be persisted"}, event_id,
            )

    def _execute_durable_activity(self, request: ToolRequest, adapter: Any, decision: PermissionDecision,
                                  event_id: str, started: str) -> NormalizedResult:
        activity_input = request.input
        assert isinstance(activity_input, ActivityRecordInput)
        definition = self.registry.definition(request.capability.capability_id, request.capability.capability_version)
        assert definition is not None
        permission = self.permission_sets["activity.record"][request.actor.actor_type]
        exec_context = GatewayExecutionContext.create(
            event_id=event_id,
            request_id=request.request_id,
            capability_id=request.capability.capability_id,
        )
        context = ActivityAdapterContext(
            activity_input.activity_type, activity_input.subject, activity_input.source, request.channel, request.purpose,
            activity_input.occurred_at, activity_input.idempotency_key, dict(activity_input.properties),
            activity_input.fact_classification, request.request_id, request.correlation_id, permission.activity_types,
            gateway_execution_context=exec_context,
        )
        try:
            outcome: DurableActivityOutcome = adapter.execute_durable(
                context=context, request=request, definition=definition,
                permission_version=self.PERMISSION_VERSIONS["activity.record"],
                started_at=started, audit_event_id=event_id,
            )
        except DurableActivityError as exc:
            evidence = exc.audit_event_id or event_id
            return NormalizedResult(
                request.request_id, request.correlation_id, request.capability.capability_id, exc.status, None, None,
                {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version},
                {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, exc.retryable, False,
                {"classification": exc.classification.value, "message": exc.message}, evidence,
            )
        record = outcome.record
        return NormalizedResult(
            request.request_id, request.correlation_id, request.capability.capability_id, ResultStatus.SUCCESS,
            {"activity_id": record.activity_id, "activity_type": record.activity_type,
             "recorded": outcome.recorded, "duplicate": outcome.duplicate},
            "INTERNAL", {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version},
            {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, False, False, None,
            outcome.audit_event_id,
        )

    def _execute_durable_preference(self, request: ToolRequest, adapter: Any, event_id: str,
                                    started: str) -> NormalizedResult:
        preference_input = request.input
        assert isinstance(preference_input, CustomerPreferenceRecordInput)
        definition = self.registry.definition(request.capability.capability_id, request.capability.capability_version)
        assert definition is not None
        exec_context = GatewayExecutionContext.create(
            event_id=event_id,
            request_id=request.request_id,
            capability_id=request.capability.capability_id,
        )
        context = PreferenceAdapterContext(
            preference_input.subject, preference_input.preference, preference_input.source,
            preference_input.memory_authorization, preference_input.stated_at, preference_input.idempotency_key,
            request.request_id, request.correlation_id, request.channel,
            gateway_execution_context=exec_context,
        )
        try:
            outcome: DurablePreferenceOutcome = adapter.execute_durable(
                context=context, request=request, definition=definition,
                permission_version=self.PERMISSION_VERSIONS["customer.preference.record"],
                started_at=started, audit_event_id=event_id,
            )
        except DurableActivityError as exc:
            return NormalizedResult(
                request.request_id, request.correlation_id, request.capability.capability_id, exc.status, None, None,
                {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version},
                {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, exc.retryable, False,
                {"classification": exc.classification.value, "message": exc.message}, exc.audit_event_id or event_id,
            )
        record = outcome.record
        return NormalizedResult(
            request.request_id, request.correlation_id, request.capability.capability_id, ResultStatus.SUCCESS,
            {"preference_id": record.preference_id, "preference_key": record.preference_key,
             "preference_value": record.preference_value, "status": record.status,
             "recorded": outcome.recorded, "duplicate": outcome.duplicate,
             "supersedes_preference_id": record.supersedes_preference_id},
            "INTERNAL", {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version},
            {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, False, False, None,
            outcome.audit_event_id,
        )

    def _execute_durable_relationship_fact(self, request: ToolRequest, adapter: Any, event_id: str,
                                           started: str) -> NormalizedResult:
        relationship_input = request.input
        assert isinstance(relationship_input, CustomerRelationshipFactRecordInput)
        definition = self.registry.definition(request.capability.capability_id, request.capability.capability_version)
        assert definition is not None
        exec_context = GatewayExecutionContext.create(
            event_id=event_id,
            request_id=request.request_id,
            capability_id=request.capability.capability_id,
        )
        context = RelationshipFactAdapterContext(
            relationship_input.subject, relationship_input.relationship_fact, relationship_input.source,
            relationship_input.memory_authorization, relationship_input.stated_at, relationship_input.idempotency_key,
            request.request_id, request.correlation_id, request.channel,
            gateway_execution_context=exec_context,
        )
        try:
            outcome: DurableRelationshipFactOutcome = adapter.execute_durable(
                context=context, request=request, definition=definition,
                permission_version=self.PERMISSION_VERSIONS["customer.relationship_fact.record"],
                started_at=started, audit_event_id=event_id,
            )
        except DurableActivityError as exc:
            return NormalizedResult(
                request.request_id, request.correlation_id, request.capability.capability_id, exc.status, None, None,
                {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version},
                {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, exc.retryable, False,
                {"classification": exc.classification.value, "message": exc.message}, exc.audit_event_id or event_id,
            )
        record = outcome.record
        return NormalizedResult(
            request.request_id, request.correlation_id, request.capability.capability_id, ResultStatus.SUCCESS,
            {"relationship_fact_id": record.relationship_fact_id, "fact_key": record.fact_key,
             "status": record.status, "recorded": outcome.recorded, "duplicate": outcome.duplicate,
             "supersedes_fact_id": record.supersedes_fact_id},
            record.sensitivity_class, {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version},
            {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, False, False, None,
            outcome.audit_event_id,
        )

    def _execute_memory_recall(self, request: ToolRequest, adapter: Any, event_id: str,
                               started: str) -> NormalizedResult:
        memory_input = request.input
        assert isinstance(memory_input, CustomerMemoryRetrieveInput)
        definition = self.registry.definition(request.capability.capability_id, request.capability.capability_version)
        assert definition is not None
        exec_context = GatewayExecutionContext.create(
            event_id=event_id,
            request_id=request.request_id,
            capability_id=request.capability.capability_id,
        )
        context = MemoryRecallAdapterContext(
            memory_input.subject, memory_input.session_memory_use, request.purpose,
            memory_input.current_context, memory_input.limits, request.request_id,
            request.correlation_id, request.channel,
            gateway_execution_context=exec_context,
        )
        try:
            outcome: MemoryRecallOutcome = adapter.retrieve_memory(
                context=context, request=request, definition=definition,
                permission_version=self.PERMISSION_VERSIONS["customer.memory.retrieve"],
                started_at=started, audit_event_id=event_id,
            )
        except DurableActivityError as exc:
            return NormalizedResult(
                request.request_id, request.correlation_id, request.capability.capability_id, exc.status, None, None,
                {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version},
                {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, exc.retryable, False,
                {"classification": exc.classification.value, "message": exc.message}, exc.audit_event_id or event_id,
            )
        return NormalizedResult(
            request.request_id, request.correlation_id, request.capability.capability_id, ResultStatus.SUCCESS,
            {"functional_context": list(outcome.functional_context),
             "relationship_context": list(outcome.relationship_context),
             "instructions": dict(outcome.instructions)},
            "CUSTOMER_VISIBLE", {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version},
            {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, False, False, None,
            outcome.audit_event_id,
        )

    def _finish_activity_success(self, request: ToolRequest, adapter: LocalActivityAdapter, record: ActivityRecord, event_id: str, started: str, *, recorded: bool, duplicate: bool, idempotency_decision: str) -> NormalizedResult:
        definition = self.registry.definition(request.capability.capability_id, request.capability.capability_version)
        assert definition is not None
        permission_version = self.PERMISSION_VERSIONS[request.capability.capability_id]
        self.audit.record(AuditEvent(
            event_id, request.request_id, request.correlation_id, request.actor.actor_id, request.actor.actor_type,
            request.capability.capability_id, request.capability.capability_version, definition.bros_level, definition.tool_class,
            permission_version, request.environment, request.channel, request.purpose, "ALLOW", adapter.tool_id,
            adapter.tool_version, ResultStatus.SUCCESS.value, None, started, utc_now(), None, record.activity_type,
            self._idempotency_reference(record.idempotency_key), idempotency_decision, record.activity_id,
        ))
        return NormalizedResult(
            request.request_id, request.correlation_id, request.capability.capability_id, ResultStatus.SUCCESS,
            {"activity_id": record.activity_id, "activity_type": record.activity_type, "recorded": recorded, "duplicate": duplicate},
            "INTERNAL", {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version},
            {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, False, False, None, event_id,
        )

    @staticmethod
    def _idempotency_reference(key: str) -> str:
        return "sha256:" + hashlib.sha256(key.encode("utf-8")).hexdigest()

    def execute_raw(self, value: dict[str, Any]) -> NormalizedResult:
        """Strict boundary for serialized requests, including auditable input denial."""
        try:
            return self.execute(ToolRequest.from_dict(value))
        except RequestValidationError:
            def valid_uuid(candidate: Any) -> str:
                try:
                    return str(UUID(str(candidate)))
                except (ValueError, TypeError, AttributeError):
                    return str(uuid4())
            actor = value.get("actor", {}) if isinstance(value, dict) else {}
            capability = value.get("capability", {}) if isinstance(value, dict) else {}
            capability_id = str(capability.get("capability_id", "invalid"))
            raw_input = value.get("input", {}) if isinstance(value, dict) and isinstance(value.get("input"), dict) else {}
            placeholder_input: KnowledgeRetrieveInput | OperationalMetricsRetrieveInput | ActivityRecordInput | CustomerPreferenceRecordInput | CustomerRelationshipFactRecordInput | CustomerMemoryRetrieveInput
            if capability_id == "customer.memory.retrieve":
                placeholder_input = CustomerMemoryRetrieveInput(
                    VerifiedMemorySubject("synthetic_person", "P-TEST-001", "UNVERIFIED"),
                    SessionMemoryUse("NOT_GRANTED", "NOT_GRANTED", False),
                    MemoryCurrentContext("invalid_topic", "invalid_intent", (), {}, "NORMAL", "DISCOVERY"),
                    MemoryLimits(0, 0),
                )
            elif capability_id == "customer.relationship_fact.record":
                placeholder_input = CustomerRelationshipFactRecordInput(
                    SubjectRef("synthetic_person", "P-TEST-001"),
                    RelationshipFactValue("customer_birthday", {"month": 1, "day": 1}, "CUSTOMER_STATED_RELATIONSHIP_FACT", "EXPLICIT"),
                    RelationshipSource("conversation", "C-TEST-001", "S-TEST-001", "invalid request context"),
                    MemoryAuthorization("ACTIVE", "internal_test"), utc_now(), "invalid",
                )
            elif capability_id == "customer.preference.record":
                placeholder_input = CustomerPreferenceRecordInput(
                    SubjectRef("synthetic_person", "P-TEST-001"), PreferenceValue("book_format", "paperback", "CUSTOMER_STATED"),
                    PreferenceSource("conversation", "C-TEST-001", "S-TEST-001"),
                    MemoryAuthorization("ACTIVE", "internal_test"), False, utc_now(), "invalid",
                )
            elif capability_id == "activity.record":
                placeholder_input = ActivityRecordInput(
                    "conversation_started", SubjectRef("synthetic_person", "P-TEST-001"),
                    SourceRef("test_harness", "invalid-request"), utc_now(), "invalid", {}, "VERIFIED_OPERATIONAL_FACT",
                )
            elif capability_id == "operational.metrics.retrieve":
                raw_domain = str(raw_input.get("domain", "invalid_domain"))
                safe_domain = raw_domain if re.fullmatch(r"[a-z][a-z0-9_]{1,63}", raw_domain) else "invalid_domain"
                placeholder_input = OperationalMetricsRetrieveInput(safe_domain, ("invalid.metric",), "current_snapshot", 1)
            else:
                placeholder_input = KnowledgeRetrieveInput("invalid", "invalid_domain", 1)
            placeholder = ToolRequest(
                valid_uuid(value.get("request_id") if isinstance(value, dict) else None),
                valid_uuid(value.get("correlation_id") if isinstance(value, dict) else None),
                Actor(str(actor.get("actor_id", "invalid-request")), str(actor.get("actor_type", "unknown"))),
                CapabilityRef(capability_id, str(capability.get("capability_version", "invalid"))),
                str(value.get("purpose", "invalid")) if isinstance(value, dict) else "invalid",
                str(value.get("channel", "invalid")) if isinstance(value, dict) else "invalid",
                str(value.get("environment", "invalid")) if isinstance(value, dict) else "invalid",
                placeholder_input,
            )
            started, event_id = utc_now(), str(uuid4())
            denied = PermissionDecision(False, ErrorClass.INPUT_VALIDATION_FAILED, "request schema or input invalid")
            return self._finish(placeholder, event_id, started, denied, ResultStatus.DENIED, None, None, False, False)

    @staticmethod
    def _validate_output(raw_items: Any, context: AdapterContext | MetricsAdapterContext) -> list[dict[str, Any]]:
        if isinstance(context, MetricsAdapterContext):
            return ToolGateway._validate_metrics_output(raw_items, context)
        if not isinstance(raw_items, list):
            raise ValueError("items must be a list")
        required = {"knowledge_id", "title", "version", "domain", "status", "classification", "source_reference", "content"}
        validated = []
        for raw in raw_items:
            if not isinstance(raw, dict) or not required.issubset(raw):
                raise ValueError("missing output fields")
            if any(not isinstance(raw[key], str) or not raw[key].strip() for key in required):
                raise ValueError("invalid output provenance")
            if raw["status"] != "Active" or raw["domain"] != context.domain or raw["classification"] not in context.access_classifications:
                raise ValueError("output exceeded authorized scope")
            validated.append(asdict(KnowledgeItem(**{key: raw[key] for key in required})))
        return validated[: context.max_results]

    @staticmethod
    def _validate_metrics_output(raw_items: Any, context: MetricsAdapterContext) -> list[dict[str, Any]]:
        if not isinstance(raw_items, list):
            raise ValueError("items must be a list")
        required = {"metric_name", "domain", "value", "unit", "classification", "status", "source_reference", "observed_at"}
        validated = []
        for raw in raw_items:
            if not isinstance(raw, dict) or not required.issubset(raw):
                raise ValueError("missing metric output fields")
            for key in required - {"value"}:
                if not isinstance(raw[key], str) or not raw[key].strip():
                    raise ValueError("invalid metric provenance")
            if raw["value"] is None:
                raise ValueError("metric value missing")
            if raw["status"] != "Active" or raw["domain"] != context.domain or raw["classification"] not in context.access_classifications:
                raise ValueError("metric output exceeded authorized scope")
            if raw["metric_name"] not in context.metric_names:
                raise ValueError("unrequested metric returned")
            validated.append(asdict(OperationalMetricItem(**{key: raw[key] for key in required})))
        return validated[: context.max_results]

    def _finish(self, request: ToolRequest, event_id: str, started: str, decision: PermissionDecision, status: ResultStatus, adapter: KnowledgeAdapter | None, items: list[dict[str, Any]] | None, retryable: bool, human_review: bool, *, idempotency_decision: str | None = None, activity_id: str | None = None) -> NormalizedResult:
        definition = self.registry.definition(request.capability.capability_id, request.capability.capability_version) or CapabilityDefinition(capability_id=request.capability.capability_id, capability_version=request.capability.capability_version)
        error = None if decision.classification is None else {"classification": decision.classification.value, "message": decision.reason}
        implementation = None if adapter is None else {"tool_id": adapter.tool_id, "tool_version": adapter.tool_version}
        result = None if items is None else {"items": items}
        classifications = {str(item["classification"]).upper() for item in items or []}
        result_classification = "RESTRICTED" if "RESTRICTED" in classifications else ("INTERNAL" if "INTERNAL" in classifications else ("PUBLIC" if items is not None else None))
        metric_domain = request.input.domain if isinstance(request.input, OperationalMetricsRetrieveInput) else None
        activity_type = request.input.activity_type if isinstance(request.input, ActivityRecordInput) else None
        idempotency_reference = self._idempotency_reference(request.input.idempotency_key) if isinstance(request.input, ActivityRecordInput) and request.input.idempotency_key else None
        if isinstance(request.input, CustomerPreferenceRecordInput):
            idempotency_reference = self._idempotency_reference(request.input.idempotency_key)
        if isinstance(request.input, CustomerRelationshipFactRecordInput):
            idempotency_reference = self._idempotency_reference(request.input.idempotency_key)
        subject_id = request.input.subject.subject_id if isinstance(request.input, (CustomerPreferenceRecordInput, CustomerRelationshipFactRecordInput, CustomerMemoryRetrieveInput)) else None
        preference_key = request.input.preference.key if isinstance(request.input, CustomerPreferenceRecordInput) else None
        memory_state = request.input.memory_authorization.state if isinstance(request.input, (CustomerPreferenceRecordInput, CustomerRelationshipFactRecordInput)) else None
        fact_key = request.input.relationship_fact.fact_key if isinstance(request.input, CustomerRelationshipFactRecordInput) else None
        sensitivity = None
        if isinstance(request.input, CustomerRelationshipFactRecordInput):
            fact_definition = RELATIONSHIP_FACT_REGISTRY.definitions.get(fact_key)
            sensitivity = fact_definition.sensitivity if fact_definition else None
        identity_state = request.input.subject.identity_state if isinstance(request.input, CustomerMemoryRetrieveInput) else None
        session_use_state = request.input.session_memory_use.state if isinstance(request.input, CustomerMemoryRetrieveInput) else None
        permission_version = self.PERMISSION_VERSIONS.get(request.capability.capability_id, "unregistered")
        self.audit.record(AuditEvent(event_id, request.request_id, request.correlation_id, request.actor.actor_id, request.actor.actor_type, request.capability.capability_id, request.capability.capability_version, definition.bros_level, definition.tool_class, permission_version, request.environment, request.channel, request.purpose, "ALLOW" if decision.allowed else "DENY", adapter.tool_id if adapter else None, adapter.tool_version if adapter else None, status.value, decision.classification.value if decision.classification else None, started, utc_now(), metric_domain, activity_type, idempotency_reference, idempotency_decision, activity_id, subject_id, preference_key, memory_state, None, None, fact_key, sensitivity, None, None, identity_state, session_use_state))
        return NormalizedResult(request.request_id, request.correlation_id, request.capability.capability_id, status, result, result_classification, implementation, {"bros_level": definition.bros_level, "tool_class": definition.tool_class}, retryable, human_review, error, event_id)
