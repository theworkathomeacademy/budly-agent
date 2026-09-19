from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import RuntimeConfig
from .events import EventLogger
from .knowledge import KnowledgeGateway, KnowledgeRecord, retrieval_required
from .model import DeterministicMockAdapter, ModelGateway
from .personality import PersonalityPackageLoader
from .prompt import PromptAssembler
from .session import SessionManager
from .validation import ResponseValidator, safe_response
from .tool_gateway import (
    Actor, AuditSink, CapabilityDefinition, CapabilityRef, KnowledgeRetrieveInput,
    LocalKnowledgeAdapter, ResultStatus, ToolGateway, ToolRegistry, ToolRequest,
)


@dataclass(frozen=True)
class TurnResult:
    session_id: str
    response_text: str
    correlation_id: str
    validation_status: str


class ConversationOrchestrator:
    def __init__(self, config: RuntimeConfig, sessions: SessionManager, personality: dict, models: ModelGateway, knowledge: KnowledgeGateway, events: EventLogger) -> None:
        self.config, self.sessions, self.personality, self.models, self.knowledge, self.events = config, sessions, personality, models, knowledge, events
        self.prompts, self.validator = PromptAssembler(), ResponseValidator()
        fixtures = [
            {
                "knowledge_id": r.knowledge_id, "title": r.domain, "version": r.version,
                "domain": "customer_policy", "status": "Active" if r.active and r.approval_status == "approved" else "Draft",
                "classification": "Public", "source_reference": r.source, "content": r.content,
            }
            for r in knowledge.records
        ]
        self.tool_audit = AuditSink()
        definition = CapabilityDefinition(enabled=config.flags.budly_knowledge_retrieve_enabled)
        self.tools = ToolGateway(ToolRegistry(definition, LocalKnowledgeAdapter(fixtures)), self.tool_audit)

    def turn(self, message: str, session_id: str | None = None) -> TurnResult:
        started, correlation_id = time.monotonic(), str(uuid4())
        if not isinstance(message, str) or not message.strip() or len(message) > self.config.max_input_chars:
            return TurnResult(session_id or "", safe_response("VALIDATION_FAILURE"), correlation_id, "BLOCK")
        try:
            session = self.sessions.load(session_id) if session_id else self.sessions.create()
        except KeyError:
            return TurnResult(session_id or "", safe_response("SESSION_LOAD_FAILURE"), correlation_id, "FALLBACK")
        if not self.config.flags.budly_llm_enabled:
            return TurnResult(session.session_id, "The conversational prototype is disabled; the existing Budly experience remains available.", correlation_id, "FALLBACK")
        needs_knowledge = retrieval_required(message)
        knowledge_results: list[dict[str, Any]] = []
        tools_requested: list[str] = []
        tools_executed: list[str] = []
        if needs_knowledge:
            tools_requested.append("knowledge.retrieve")
            if self.config.flags.budly_knowledge_retrieve_enabled:
                tool_request = ToolRequest(
                    str(uuid4()), correlation_id, Actor("budly-runtime", "budly_service"),
                    CapabilityRef("knowledge.retrieve", "1.0"), "customer_education", "website_chat", "prototype",
                    KnowledgeRetrieveInput(message, "customer_policy", 5),
                )
                tool_result = self.tools.execute(tool_request)
                if tool_result.status == ResultStatus.SUCCESS:
                    knowledge_results = tool_result.result["items"] if tool_result.result else []
                    tools_executed.append("knowledge.retrieve")
        assembled = self.prompts.assemble(personality=self.personality, session=session, message=message, knowledge=knowledge_results)
        model_prompt = {"assembled": assembled, "message": message, "knowledge": knowledge_results, "knowledge_required": needs_knowledge}
        provider = model = "none"
        try:
            result = self.models.generate(model_prompt)
            payload, provider, model = result.payload, result.provider, result.model
        except TimeoutError:
            return self._fallback(session.session_id, correlation_id, "MODEL_TIMEOUT")
        except (ConnectionError, LookupError):
            return self._fallback(session.session_id, correlation_id, "MODEL_UNAVAILABLE")
        validation = self.validator.validate(payload, knowledge_required=needs_knowledge, knowledge_used=bool(knowledge_results))
        if validation.status == "REPAIR":
            payload = self.validator.repair(payload)
            validation = self.validator.validate(payload, knowledge_required=needs_knowledge, knowledge_used=bool(knowledge_results))
            if validation.status == "REPAIR":
                validation = type(validation)("FALLBACK", validation.reasons + ("repair_limit_reached",))
        if validation.status != "PASS":
            code = "MODEL_GOVERNANCE_FAILURE" if validation.status == "BLOCK" else "MODEL_SCHEMA_INVALID"
            response_text = safe_response(code)
        else:
            response_text = payload["response_text"]
            session.conversation_mode = payload["conversation_mode"]
            session.current_intents = list(payload["detected_intents"])
            # Only allowlisted operational state is accepted; inferred facts are not persisted.
        try:
            if self.config.flags.budly_session_memory_enabled:
                self.sessions.record_turn(session, message, response_text)
        except (KeyError, ValueError):
            return self._fallback(session.session_id, correlation_id, "SESSION_WRITE_FAILURE")
        if self.config.flags.budly_conversation_logging_enabled:
            self.events.emit_turn(session_id=session.session_id, channel=session.channel, conversation_mode=session.conversation_mode, detected_intents=session.current_intents, model_role="PRIMARY_CONVERSATION", provider=provider, model=model, personality_package_version="0.1", knowledge_used=[r["knowledge_id"] for r in knowledge_results], tools_requested=tools_requested, tools_executed=tools_executed, validation_status=validation.status, latency_ms=int((time.monotonic()-started)*1000), input_tokens=None, output_tokens=None, estimated_cost=None, correlation_id=correlation_id)
        return TurnResult(session.session_id, response_text, correlation_id, validation.status)

    def _fallback(self, session_id: str, correlation_id: str, code: str) -> TurnResult:
        return TurnResult(session_id, safe_response(code), correlation_id, "FALLBACK")


def build_prototype(config: RuntimeConfig | None = None, *, adapter: DeterministicMockAdapter | None = None, records: list[KnowledgeRecord] | None = None) -> ConversationOrchestrator:
    config = config or RuntimeConfig()
    root = Path(__file__).resolve().parents[2]
    personality = PersonalityPackageLoader(root / "config" / "budly_runtime" / "personality-package-v0.1.json").load()
    sessions = SessionManager(config.recent_turn_limit, config.summary_trigger_turns)
    primary = adapter or DeterministicMockAdapter("mock-a")
    registry = {config.primary_role: primary, config.fallback_role: DeterministicMockAdapter("mock-fallback"), config.summarization_role: DeterministicMockAdapter("mock-summarizer")}
    return ConversationOrchestrator(config, sessions, personality, ModelGateway(registry, config.primary_role, config.fallback_role), KnowledgeGateway(records or []), EventLogger())
