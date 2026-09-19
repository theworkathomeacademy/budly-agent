from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .session import MODES

REQUIRED = {"response_text", "conversation_mode", "detected_intents", "customer_context_updates", "clarification", "recommended_next_action", "requested_tools", "personality_state", "confidence", "risk_flags"}
CONFIDENCE = {"low", "moderate", "high"}
SAFE_MESSAGES = {
    "MODEL_TIMEOUT": "I’m having trouble responding right now. Please try again in a moment.",
    "MODEL_UNAVAILABLE": "I’m temporarily unavailable. Please try again shortly.",
    "MODEL_SCHEMA_INVALID": "I couldn’t form a reliable answer, so I won’t guess. Please try that again.",
    "MODEL_GOVERNANCE_FAILURE": "I can’t help with that request, but I can help with a safer alternative.",
    "KNOWLEDGE_UNAVAILABLE": "I don’t have an approved current source for that, so I won’t guess.",
    "TOOL_UNAVAILABLE": "That information source is temporarily unavailable.",
    "TOOL_UNAUTHORIZED": "I’m not authorized to do that.",
    "TOOL_FAILED": "I couldn’t complete that lookup safely.",
    "SESSION_LOAD_FAILURE": "I couldn’t safely resume this conversation. Please start a new one.",
    "SESSION_WRITE_FAILURE": "I couldn’t safely save this turn. Please try again.",
    "VALIDATION_FAILURE": "I couldn’t form a reliable answer, so I won’t guess.",
}


@dataclass(frozen=True)
class ValidationResult:
    status: str
    reasons: tuple[str, ...] = ()


def safe_response(code: str) -> str:
    return SAFE_MESSAGES.get(code, SAFE_MESSAGES["VALIDATION_FAILURE"])


class ResponseValidator:
    def validate(self, payload: Any, *, knowledge_required: bool, knowledge_used: bool) -> ValidationResult:
        if not isinstance(payload, dict):
            return ValidationResult("REPAIR", ("schema_not_object",))
        missing = REQUIRED - set(payload)
        if missing:
            return ValidationResult("REPAIR", ("missing_fields",))
        if not isinstance(payload["response_text"], str) or not payload["response_text"].strip():
            return ValidationResult("FALLBACK", ("empty_response",))
        if payload["conversation_mode"] not in MODES or payload["confidence"] not in CONFIDENCE:
            return ValidationResult("REPAIR", ("unsupported_enum",))
        if not isinstance(payload["detected_intents"], list) or not isinstance(payload["requested_tools"], list) or not isinstance(payload["risk_flags"], list) or not isinstance(payload["customer_context_updates"], dict):
            return ValidationResult("REPAIR", ("invalid_types",))
        text = payload["response_text"].lower()
        if re.search(r"(system prompt|system instructions|hidden instructions|chain.of.thought)", text):
            return ValidationResult("BLOCK", ("prompt_disclosure",))
        if re.search(r"(i (have )?(completed|executed|purchased|updated|sent)|tool succeeded)", text) and not knowledge_used:
            return ValidationResult("BLOCK", ("fabricated_execution",))
        if knowledge_required and not knowledge_used and not re.search(r"(don.t have|cannot verify|won.t guess|approved current source)", text):
            return ValidationResult("BLOCK", ("unsupported_business_claim",))
        if text.count("buy now") > 1 or text.count("!") > 8:
            return ValidationResult("FALLBACK", ("excessive_sales_pressure",))
        return ValidationResult("PASS")

    def repair(self, payload: Any) -> dict | None:
        if not isinstance(payload, dict):
            return None
        repaired = dict(payload)
        repaired.setdefault("detected_intents", [])
        repaired.setdefault("customer_context_updates", {})
        repaired.setdefault("clarification", {"needed": False, "topic": None})
        repaired.setdefault("recommended_next_action", None)
        repaired.setdefault("requested_tools", [])
        repaired.setdefault("personality_state", {"personality_intensity": 2, "humor_intensity": 2, "curiosity_intensity": 2, "commercial_pressure": 1, "education_depth": 1})
        repaired.setdefault("confidence", "low")
        repaired.setdefault("risk_flags", [])
        return repaired
