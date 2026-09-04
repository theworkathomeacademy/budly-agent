"""TG-P07 deterministic multi-session orchestration proof.

This harness owns no capability. Durable reads/writes are delegated to the
accepted TG-P05A, TG-P05B and TG-P06 Tool Gateway registrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .tool_gateway import (
    Actor, CapabilityRef, CustomerMemoryRetrieveInput, CustomerPreferenceRecordInput,
    CustomerRelationshipFactRecordInput, MemoryAuthorization, MemoryCurrentContext,
    MemoryLimits, PreferenceSource, PreferenceValue, RelationshipFactValue,
    RelationshipSource, ResultStatus, SessionMemoryUse, SubjectRef, ToolGateway,
    ToolRequest, VerifiedMemorySubject,
)


@dataclass
class HarnessSession:
    session_id: str
    subject_id: str
    identity_state: str
    memory_use_mode: str
    ephemeral_context: dict[str, str] = field(default_factory=dict)
    current_statements: dict[str, str] = field(default_factory=dict)
    turns: list[dict[str, str]] = field(default_factory=list)
    bounded_summary_topics: list[str] = field(default_factory=list)
    hypotheses: dict[str, dict[str, Any]] = field(default_factory=dict)
    capability_results: list[dict[str, Any]] = field(default_factory=list)
    correlation_ids: list[str] = field(default_factory=list)

    @property
    def bounded_summary(self) -> str:
        return "; ".join(self.bounded_summary_topics[-8:])[:500]


@dataclass(frozen=True)
class RecallComposition:
    functional_context: tuple[dict[str, Any], ...]
    relationship_context: tuple[dict[str, Any], ...]
    response_instructions: dict[str, Any]
    memory_available: bool
    evidence_reference: str | None


class ConversationHarness:
    """Orchestrates accepted capabilities without acquiring their authority."""

    def __init__(self, preference_gateway: ToolGateway, relationship_gateway: ToolGateway,
                 recall_gateway: ToolGateway) -> None:
        self.preference_gateway = preference_gateway
        self.relationship_gateway = relationship_gateway
        self.recall_gateway = recall_gateway
        self._source_counter = 0

    def start_session(self, subject_id: str, *, memory_use_mode: str = "ACTIVE",
                      identity_state: str = "VERIFIED") -> HarnessSession:
        if memory_use_mode not in {"ACTIVE", "START_FRESH", "NOT_GRANTED", "WITHDRAWN"}:
            raise ValueError("invalid memory-use mode")
        return HarnessSession(str(uuid4()), subject_id, identity_state, memory_use_mode)

    def receive_turn(self, session: HarnessSession, message: str, *, topic: str,
                     intent: str, ephemeral_updates: dict[str, str] | None = None,
                     current_statements: dict[str, str] | None = None) -> None:
        if not isinstance(message, str) or not message.strip() or len(message) > 1000:
            raise ValueError("turn message must be bounded")
        session.turns.append({"role": "customer", "message": message})
        session.turns[:] = session.turns[-10:]
        if ephemeral_updates:
            session.ephemeral_context.update(ephemeral_updates)
        if current_statements:
            session.current_statements.update(current_statements)
        if topic not in session.bounded_summary_topics:
            session.bounded_summary_topics.append(topic)
            session.bounded_summary_topics[:] = session.bounded_summary_topics[-8:]

    def observe_behavior(self, session: HarnessSession, key: str, value: str) -> dict[str, Any]:
        hypothesis = session.hypotheses.setdefault(key, {"value": value, "observations": 0, "authoritative": False})
        if hypothesis["value"] != value:
            hypothesis.update({"value": value, "observations": 0})
        hypothesis["observations"] += 1
        return dict(hypothesis)

    def recall(self, session: HarnessSession, *, purpose: str, topic: str, intent: str,
               entities: tuple[str, ...] = (), operational_priority: str = "NORMAL",
               explicit_memory_request: bool = False, provenance_challenge: bool = False,
               functional_limit: int = 5, relational_limit: int = 1) -> RecallComposition:
        request = self._request(
            session, "customer.memory.retrieve", purpose,
            CustomerMemoryRetrieveInput(
                VerifiedMemorySubject("synthetic_person", session.subject_id, session.identity_state),
                SessionMemoryUse(session.memory_use_mode, "ACTIVE", False),
                MemoryCurrentContext(
                    topic, intent, entities, dict(session.current_statements), operational_priority,
                    "RELATIONSHIP_CONTINUATION" if purpose == "relationship_conversation" else "PRODUCT_DISCOVERY",
                    explicit_memory_request, provenance_challenge,
                ),
                MemoryLimits(functional_limit, relational_limit),
            ),
        )
        result = self.recall_gateway.execute(request)
        self._record_result(session, result)
        if result.status != ResultStatus.SUCCESS or result.result is None:
            return RecallComposition((), (), {
                "continue_without_saved_memory": True,
                "must_not_claim_recollection": True,
                "ephemeral_context": dict(session.ephemeral_context),
            }, False, result.evidence_reference)
        functional = tuple(result.result["functional_context"])
        relational = tuple(result.result["relationship_context"])
        instructions = self._compose(functional, relational, session.ephemeral_context)
        instructions.update(result.result["instructions"])
        return RecallComposition(functional, relational, instructions, True, result.evidence_reference)

    def record_preference(self, session: HarnessSession, key: str, value: str, *,
                          explicit_customer_statement: bool, remember_requested: bool = True) -> dict[str, Any]:
        if not explicit_customer_statement or not remember_requested:
            return {"status": "EPHEMERAL_ONLY", "saved": False, "claim_saved": False}
        session.current_statements[key] = value
        existing = self.recall(
            session, purpose="explicit_memory_review", topic="memory_review",
            intent="show_saved_memory", explicit_memory_request=True,
        )
        if any(item["key"] == key and item["value"] == value for item in existing.functional_context):
            return {"status": "ALREADY_CURRENT", "saved": True, "claim_saved": False}
        source, statement = self._next_source()
        request = self._request(
            session, "customer.preference.record", "internal_test",
            CustomerPreferenceRecordInput(
                SubjectRef("synthetic_person", session.subject_id),
                PreferenceValue(key, value, "CUSTOMER_STATED"),
                PreferenceSource("conversation", source, statement),
                MemoryAuthorization("ACTIVE", "internal_test"), False,
                "2026-08-24T18:00:00+00:00", f"tg-p07:{session.session_id}:{key}:{statement}",
            ),
        )
        result = self.preference_gateway.execute(request)
        self._record_result(session, result)
        return {
            "status": result.status.value, "saved": result.status == ResultStatus.SUCCESS,
            "claim_saved": result.status == ResultStatus.SUCCESS,
            "result": result.result, "error": result.error,
        }

    def record_relationship_fact(self, session: HarnessSession, fact_key: str,
                                 fact_value: dict[str, Any], *, explicit_customer_statement: bool,
                                 remember_requested: bool = True) -> dict[str, Any]:
        if not explicit_customer_statement or not remember_requested:
            return {"status": "EPHEMERAL_ONLY", "saved": False, "claim_saved": False}
        session.current_statements[fact_key] = str(fact_value)
        session.ephemeral_context[fact_key] = str(fact_value)
        source, statement = self._next_source()
        request = self._request(
            session, "customer.relationship_fact.record", "internal_test",
            CustomerRelationshipFactRecordInput(
                SubjectRef("synthetic_person", session.subject_id),
                RelationshipFactValue(fact_key, dict(fact_value), "CUSTOMER_STATED_RELATIONSHIP_FACT", "EXPLICIT"),
                RelationshipSource("conversation", source, statement, "conversation about family milestones"),
                MemoryAuthorization("ACTIVE", "internal_test"), "2026-08-24T18:00:00+00:00",
                f"tg-p07:{session.session_id}:{fact_key}:{statement}",
            ),
        )
        result = self.relationship_gateway.execute(request)
        self._record_result(session, result)
        return {
            "status": result.status.value, "saved": result.status == ResultStatus.SUCCESS,
            "claim_saved": result.status == ResultStatus.SUCCESS,
            "result": result.result, "error": result.error,
        }

    @staticmethod
    def _compose(functional: tuple[dict[str, Any], ...], relational: tuple[dict[str, Any], ...],
                 ephemeral: dict[str, str]) -> dict[str, Any]:
        instructions: dict[str, Any] = {
            "style": dict(ephemeral), "contextual_references": [], "transparent_review": [],
            "relationship_context": list(relational),
        }
        for item in functional:
            if item["recall_mode"] == "SILENT_USE":
                instructions["style"][item["key"]] = item["value"]
            elif item["recall_mode"] == "CONTEXTUAL_REFERENCE":
                instructions["contextual_references"].append({"key": item["key"], "value": item["value"]})
            elif item["recall_mode"] == "TRANSPARENT_REVIEW":
                instructions["transparent_review"].append({"key": item["key"], "value": item["value"]})
        return instructions

    def _request(self, session: HarnessSession, capability_id: str, purpose: str, input_value: Any) -> ToolRequest:
        correlation_id = str(uuid4())
        session.correlation_ids.append(correlation_id)
        return ToolRequest(
            str(uuid4()), correlation_id, Actor("tg-p07-harness", "test_harness"),
            CapabilityRef(capability_id, "1.0"), purpose, "internal_test", "prototype", input_value,
        )

    def _next_source(self) -> tuple[str, str]:
        self._source_counter += 1
        value = ((self._source_counter - 1) % 999) + 1
        return f"C-TEST-{value:03d}", f"S-TEST-{value:03d}"

    @staticmethod
    def _record_result(session: HarnessSession, result: Any) -> None:
        session.capability_results.append({
            "capability_id": result.capability_id, "status": result.status.value,
            "evidence_reference": result.evidence_reference, "error": result.error,
        })
