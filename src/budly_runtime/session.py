from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

MODES = {"DISCOVERY", "EDUCATION", "PRODUCT_DISCOVERY", "RECOMMENDATION", "COMPARISON", "PURCHASE_GUIDANCE", "SUPPORT", "RELATIONSHIP_CONTINUATION", "COMMUNITY", "NO_MATCH"}
EMOTIONS = {"NEUTRAL", "POSITIVE", "FRUSTRATED", "CONCERNED"}
EXPERTISE = {"UNKNOWN", "BEGINNER", "INTERMEDIATE", "EXPERIENCED"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Turn:
    role: str
    content: str


@dataclass
class ConversationSession:
    session_id: str
    created_at: str
    updated_at: str
    channel: str = "ccc_website"
    customer_identity_status: str = "anonymous"
    conversation_mode: str = "DISCOVERY"
    personality_intensity: int = 2
    humor_intensity: int = 2
    curiosity_intensity: int = 2
    commercial_pressure: int = 1
    education_depth: int = 1
    customer_emotional_state: str = "NEUTRAL"
    customer_expertise: str = "UNKNOWN"
    primary_goal: str | None = None
    current_intents: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    products_discussed: list[str] = field(default_factory=list)
    resources_discussed: list[str] = field(default_factory=list)
    recommendations_presented: list[str] = field(default_factory=list)
    questions_already_answered: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    objections_or_concerns: list[str] = field(default_factory=list)
    next_best_action: str | None = None
    conversation_summary: str | None = None
    recent_turns: list[Turn] = field(default_factory=list)
    conversational_turn_count: int = 0

    def runtime_variables(self) -> dict[str, Any]:
        keys = ("personality_intensity", "humor_intensity", "curiosity_intensity", "commercial_pressure", "education_depth", "customer_emotional_state", "customer_expertise", "conversation_mode")
        data = asdict(self)
        return {key: data[key] for key in keys}


def validate_runtime_variables(values: dict[str, Any]) -> None:
    for key in ("personality_intensity", "humor_intensity", "curiosity_intensity", "commercial_pressure", "education_depth"):
        if type(values.get(key)) is not int or not 0 <= values[key] <= 4:
            raise ValueError(f"{key} must be an integer from 0 to 4")
    if values.get("conversation_mode") not in MODES:
        raise ValueError("unsupported conversation mode")
    if values.get("customer_emotional_state") not in EMOTIONS:
        raise ValueError("unsupported emotional state")
    if values.get("customer_expertise") not in EXPERTISE:
        raise ValueError("unsupported expertise")


class SessionManager:
    """Process-local prototype store; it is not CRM or persistent memory."""

    def __init__(self, recent_turn_limit: int = 10, summary_trigger_turns: int = 8) -> None:
        self._sessions: dict[str, ConversationSession] = {}
        self.recent_turn_limit = recent_turn_limit
        self.summary_trigger_turns = summary_trigger_turns

    def create(self, channel: str = "ccc_website") -> ConversationSession:
        now = _now()
        session = ConversationSession(str(uuid4()), now, now, channel=channel)
        validate_runtime_variables(session.runtime_variables())
        self._sessions[session.session_id] = deepcopy(session)
        return deepcopy(session)

    def load(self, session_id: str) -> ConversationSession:
        if session_id not in self._sessions:
            raise KeyError("session not found")
        return deepcopy(self._sessions[session_id])

    def update(self, session: ConversationSession) -> ConversationSession:
        if session.session_id not in self._sessions:
            raise KeyError("session not found")
        validate_runtime_variables(session.runtime_variables())
        session.updated_at = _now()
        self._sessions[session.session_id] = deepcopy(session)
        return deepcopy(session)

    def record_turn(self, session: ConversationSession, customer: str, assistant: str) -> ConversationSession:
        session.recent_turns.extend([Turn("customer", customer), Turn("assistant", assistant)])
        session.conversational_turn_count += 1
        if session.conversational_turn_count % self.summary_trigger_turns == 0:
            older = session.recent_turns[:-self.recent_turn_limit]
            if older:
                safe = [f"{t.role}: {t.content[:160]}" for t in older]
                session.conversation_summary = " | ".join(safe)[-2000:]
        session.recent_turns = session.recent_turns[-self.recent_turn_limit:]
        return self.update(session)
