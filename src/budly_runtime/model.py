from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import uuid4
import json
import urllib.error
import urllib.request


@dataclass(frozen=True)
class ModelRequest:
    request_id: str
    role: str
    task: str
    complexity: str
    risk: str
    privacy_class: str
    required_capabilities: tuple[str, ...]
    prompt_package: dict[str, Any]
    timeout_ms: int = 15000


@dataclass(frozen=True)
class ProviderResult:
    payload: Any
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class ProviderAdapter(ABC):
    @abstractmethod
    def generate(self, request: ModelRequest) -> ProviderResult: ...


class DeterministicMockAdapter(ProviderAdapter):
    def __init__(self, name: str = "mock-a", behavior: str = "normal") -> None:
        self.name, self.behavior = name, behavior

    def generate(self, request: ModelRequest) -> ProviderResult:
        if self.behavior == "timeout":
            raise TimeoutError("mock timeout")
        if self.behavior == "unavailable":
            raise ConnectionError("mock unavailable")
        if self.behavior == "malformed":
            return ProviderResult("not-json", "deterministic-mock", self.name)
        knowledge = request.prompt_package.get("knowledge", [])
        message = request.prompt_package.get("message", "")
        if knowledge:
            text = f"According to the approved source, {knowledge[0]['content']}"
        elif request.prompt_package.get("knowledge_required"):
            text = "I don’t have an approved current source for that, so I won’t guess."
        elif "ignore your rules" in message.lower():
            text = "I can help with your question, but I can’t set aside the rules that keep the conversation trustworthy."
        else:
            text = "Hi — I’m Budly. What would be most useful to explore together?"
        payload = {
            "response_text": text, "conversation_mode": "DISCOVERY", "detected_intents": [],
            "customer_context_updates": {}, "clarification": {"needed": False, "topic": None},
            "recommended_next_action": None, "requested_tools": [],
            "personality_state": {"personality_intensity": 2, "humor_intensity": 2, "curiosity_intensity": 2, "commercial_pressure": 1, "education_depth": 1},
            "confidence": "moderate", "risk_flags": [],
        }
        return ProviderResult(payload, "deterministic-mock", self.name)


class ModelGateway:
    def __init__(self, registry: dict[str, ProviderAdapter], primary_role: str, fallback_role: str) -> None:
        self.registry, self.primary_role, self.fallback_role = registry, primary_role, fallback_role

    def generate(self, prompt_package: dict, role: str | None = None) -> ProviderResult:
        selected = role or self.primary_role
        if selected not in self.registry:
            raise LookupError("model role not configured")
        request = ModelRequest(str(uuid4()), "PRIMARY_CONVERSATION", "customer_dialogue", "moderate", "normal", "standard_customer", ("natural_conversation", "structured_output", "tool_request", "context_following"), prompt_package)
        return self.registry[selected].generate(request)


class OpenAIResponsesAdapter(ProviderAdapter):
    """Server-side OpenAI Responses adapter; routing and credentials are constructor-controlled."""

    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, model: str, api_key: str, *, timeout_seconds: float = 15.0,
                 retry_count: int = 1, opener: Any | None = None) -> None:
        if not model or not api_key:
            raise ValueError("model and server-side API key are required")
        if not 1 <= timeout_seconds <= 30 or retry_count not in {0, 1}:
            raise ValueError("provider timeout/retry configuration is invalid")
        self.model, self.api_key = model, api_key
        self.timeout_seconds, self.retry_count = timeout_seconds, retry_count
        self._opener = opener or urllib.request.urlopen

    def generate(self, request: ModelRequest) -> ProviderResult:
        schema = request.prompt_package.get("output_schema")
        body = {
            "model": self.model,
            "input": request.prompt_package.get("provider_input", []),
            "text": {"format": {"type": "json_schema", "name": "budly_conversation_turn", "strict": True, "schema": schema}},
        }
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        provider_request = urllib.request.Request(
            self.endpoint, data=encoded, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                with self._opener(provider_request, timeout=self.timeout_seconds) as response:
                    raw = json.loads(response.read().decode("utf-8"))
                text = self._output_text(raw)
                payload = json.loads(text)
                usage = raw.get("usage", {}) if isinstance(raw, dict) else {}
                return ProviderResult(payload, "openai", self.model, usage.get("input_tokens"), usage.get("output_tokens"))
            except (TimeoutError, urllib.error.URLError) as exc:
                last_error = exc
                if attempt >= self.retry_count:
                    if isinstance(exc, TimeoutError):
                        raise TimeoutError("model provider timed out") from None
                    raise ConnectionError("model provider unavailable") from None
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise ValueError("model provider returned an invalid structured response") from exc
        raise ConnectionError("model provider unavailable") from last_error

    @staticmethod
    def _output_text(raw: dict[str, Any]) -> str:
        if isinstance(raw.get("output_text"), str):
            return raw["output_text"]
        for item in raw.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                    return content["text"]
        raise ValueError("provider response contained no output text")
